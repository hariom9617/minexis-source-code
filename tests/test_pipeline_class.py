"""
Tests for the Pipeline class and FrameResult.

Verifies that:
- Pipeline.step() returns None when no pair is available yet, then a
  FrameResult once a pair forms.
- FrameResult exposes all required fields with correct types.
- Repeated calls preserve tracker and RiskEngine state (track IDs stable).
- Fog degradation reduces thermal quality while radar still contributes.
- The serialization helper produces a JSON-safe dict.
- Pipeline.close() does not raise.

Run:
    python -m pytest tests/ -v
  or:
    python tests/test_pipeline_class.py
"""

from __future__ import annotations

import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import Pipeline, FrameResult
from common.types import RiskState, FusedObject, Track, RiskAssessment, AlertEvent, ThermalDetection, RadarCluster
from common.serialization import frame_result_to_dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_until_frame(pipeline: Pipeline, max_steps: int = 200) -> FrameResult:
    """Drive the pipeline until the first FrameResult is returned."""
    for _ in range(max_steps):
        result = pipeline.step()
        if result is not None:
            return result
        time.sleep(0.001)
    raise AssertionError(f"No FrameResult after {max_steps} steps")


def _make_pipeline(**kwargs) -> Pipeline:
    """Create a Pipeline with logging disabled (no file I/O in tests)."""
    return Pipeline(log_path=None, **kwargs)


# ---------------------------------------------------------------------------
# Basic step() behaviour
# ---------------------------------------------------------------------------

def test_pipeline_step_returns_none_then_frame():
    """First few calls may return None; eventually a FrameResult is returned."""
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)
    assert isinstance(result, FrameResult)
    pipe.close()


def test_frame_result_has_all_required_fields():
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)

    assert isinstance(result.timestamp, float)
    assert isinstance(result.frame_number, int) and result.frame_number >= 1
    assert isinstance(result.sync_skew_s, float)
    assert isinstance(result.thermal_quality, float), "thermal_quality must be a float"
    assert isinstance(result.radar_quality, float), "radar_quality must be a float"
    assert isinstance(result.thermal_detections, list)
    assert isinstance(result.radar_clusters, list)
    assert isinstance(result.fused_objects, list)
    assert isinstance(result.tracks, list)
    assert isinstance(result.risks, list)
    assert isinstance(result.alerts, list)
    assert isinstance(result.highest_risk, RiskState)
    assert isinstance(result.latency, dict)

    pipe.close()


def test_frame_result_quality_scores_in_range():
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)
    assert 0.0 <= result.thermal_quality <= 1.0
    assert 0.0 <= result.radar_quality <= 1.0
    pipe.close()


def test_frame_result_latency_keys():
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)
    required_keys = {"perception", "fusion", "tracking", "risk", "alerts", "total"}
    assert required_keys.issubset(result.latency.keys()), (
        f"Missing latency keys: {required_keys - result.latency.keys()}"
    )
    for k, v in result.latency.items():
        assert v >= 0.0, f"Latency '{k}' must be non-negative, got {v}"
    pipe.close()


# ---------------------------------------------------------------------------
# Tracker and RiskEngine state preservation across calls
# ---------------------------------------------------------------------------

def test_tracker_state_preserved_across_steps():
    """
    Running multiple step() calls should grow the frame_count and produce
    stable track IDs for a persistent simulated object.
    """
    pipe = _make_pipeline()

    # collect several FrameResults
    results = []
    while len(results) < 15:
        r = pipe.step()
        if r is not None:
            results.append(r)
        else:
            time.sleep(0.005)

    assert pipe.frame_count == len(results)

    # gather all track IDs across frames
    all_ids = set()
    for r in results:
        for t in r.tracks:
            all_ids.add(t.track_id)

    # the synthetic target should produce at least one consistent track ID
    # (i.e. the tracker persists state, not spawning a fresh ID each frame)
    assert len(all_ids) >= 1, "Expected at least one tracked object"

    # verify that a track_id seen in an early frame reappears in a later frame
    early_ids = {t.track_id for r in results[:5] for t in r.tracks}
    late_ids  = {t.track_id for r in results[5:] for t in r.tracks}
    # at least one ID should appear in both halves (stable tracking)
    overlap = early_ids & late_ids
    assert len(overlap) >= 1, (
        f"No track IDs survived across frames. Early={early_ids}, Late={late_ids}"
    )

    pipe.close()


def test_risk_engine_state_preserved_across_steps():
    """
    The hysteresis state inside RiskEngine must survive across step() calls.
    We check that risk_state values are valid RiskState members (not
    KeyError / None) after many frames.
    """
    pipe = _make_pipeline()
    results = []
    while len(results) < 20:
        r = pipe.step()
        if r is not None:
            results.append(r)
        else:
            time.sleep(0.005)

    for r in results:
        for ra in r.risks:
            assert isinstance(ra.risk_state, RiskState), (
                f"Invalid risk_state: {ra.risk_state!r}"
            )

    pipe.close()


# ---------------------------------------------------------------------------
# Fog degradation
# ---------------------------------------------------------------------------

def test_fog_reduces_thermal_quality():
    """
    High fog_severity must produce lower average thermal_quality than
    clear conditions while radar scan_quality should remain comparable.
    """
    clear_pipe = _make_pipeline(fog_severity=0.0)
    foggy_pipe = _make_pipeline(fog_severity=0.9)

    clear_results = []
    foggy_results = []

    while len(clear_results) < 10:
        r = clear_pipe.step()
        if r is not None:
            clear_results.append(r)
        else:
            time.sleep(0.005)

    while len(foggy_results) < 10:
        r = foggy_pipe.step()
        if r is not None:
            foggy_results.append(r)
        else:
            time.sleep(0.005)

    avg_clear_thermal = sum(r.thermal_quality for r in clear_results) / len(clear_results)
    avg_foggy_thermal = sum(r.thermal_quality for r in foggy_results) / len(foggy_results)

    avg_clear_radar = sum(r.radar_quality for r in clear_results) / len(clear_results)
    avg_foggy_radar = sum(r.radar_quality for r in foggy_results) / len(foggy_results)

    assert avg_foggy_thermal < avg_clear_thermal, (
        f"Fog should reduce thermal quality: "
        f"clear={avg_clear_thermal:.3f}, foggy={avg_foggy_thermal:.3f}"
    )

    # radar quality should not be significantly affected by thermal fog
    # (same synthetic radar source, independent of fog_severity)
    # Allow a small delta due to RNG differences between instances
    assert abs(avg_clear_radar - avg_foggy_radar) < 0.4, (
        f"Radar quality unexpectedly diverged: "
        f"clear={avg_clear_radar:.3f}, foggy={avg_foggy_radar:.3f}"
    )

    clear_pipe.close()
    foggy_pipe.close()


def test_foggy_pipeline_still_produces_radar_clusters():
    """
    Even with heavy fog, the radar branch should still produce clusters
    (radar is fog-independent by design).
    """
    pipe = _make_pipeline(fog_severity=1.0)
    results = []
    while len(results) < 5:
        r = pipe.step()
        if r is not None:
            results.append(r)
        else:
            time.sleep(0.005)

    # at least some frames should have radar clusters
    has_clusters = any(len(r.radar_clusters) > 0 for r in results)
    assert has_clusters, "Expected radar clusters even under heavy fog"

    pipe.close()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_frame_result_to_dict_is_json_safe():
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)
    d = frame_result_to_dict(result)
    pipe.close()

    # Must be serializable without error
    serialized = json.dumps(d)
    assert len(serialized) > 0

    # Key fields must be present
    assert "timestamp" in d
    assert "frame_number" in d
    assert "thermal_quality" in d
    assert "radar_quality" in d
    assert "highest_risk" in d
    assert "latency" in d
    assert "thermal_detections" in d
    assert "radar_clusters" in d
    assert "fused_objects" in d
    assert "tracks" in d
    assert "risks" in d
    assert "alerts" in d


def test_frame_result_to_dict_no_numpy_arrays():
    """The serialized dict must contain no numpy types."""
    import numpy as np
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)
    d = frame_result_to_dict(result)
    pipe.close()

    def _check_no_numpy(obj, path="root"):
        if isinstance(obj, (np.ndarray, np.generic)):
            raise AssertionError(f"numpy type found at {path}: {type(obj)}")
        if isinstance(obj, dict):
            for k, v in obj.items():
                _check_no_numpy(v, f"{path}.{k}")
        if isinstance(obj, list):
            for i, v in enumerate(obj):
                _check_no_numpy(v, f"{path}[{i}]")

    _check_no_numpy(d)


def test_serialized_highest_risk_is_string():
    pipe = _make_pipeline()
    result = _run_until_frame(pipe)
    d = frame_result_to_dict(result)
    pipe.close()
    assert isinstance(d["highest_risk"], str), (
        f"highest_risk should be a string, got {type(d['highest_risk'])}"
    )
    assert d["highest_risk"] in {"safe", "caution", "warning", "critical"}


def test_serialized_fused_objects_no_source_fields():
    """source_thermal and source_radar should be excluded from serialized fused objects."""
    pipe = _make_pipeline()
    results = []
    while len(results) < 5:
        r = pipe.step()
        if r is not None:
            results.append(r)
        else:
            time.sleep(0.005)
    pipe.close()

    for r in results:
        d = frame_result_to_dict(r)
        for fo in d.get("fused_objects", []):
            assert "source_thermal" not in fo, "source_thermal should be excluded from serialized output"
            assert "source_radar" not in fo, "source_radar should be excluded from serialized output"


# ---------------------------------------------------------------------------
# frame_number and close()
# ---------------------------------------------------------------------------

def test_frame_number_increments():
    pipe = _make_pipeline()
    results = []
    while len(results) < 5:
        r = pipe.step()
        if r is not None:
            results.append(r)
        else:
            time.sleep(0.005)
    pipe.close()

    for i, r in enumerate(results):
        assert r.frame_number == i + 1, (
            f"frame_number should be {i+1}, got {r.frame_number}"
        )


def test_pipeline_close_does_not_raise():
    pipe = _make_pipeline()
    _run_until_frame(pipe)
    pipe.close()   # should not raise


def test_pipeline_close_without_any_frames():
    """close() must not raise even if step() was never called."""
    pipe = _make_pipeline()
    pipe.close()


def test_fog_severity_property():
    pipe = _make_pipeline(fog_severity=0.42)
    assert abs(pipe.fog_severity - 0.42) < 1e-6
    pipe.close()


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------

def test_custom_source_injection():
    """
    Verify that the Pipeline accepts custom source objects (the DI hook
    needed for hardware integration later).
    """
    from sensors.thermal_source import SyntheticThermalSource
    from sensors.radar_source import SyntheticRadarSource

    custom_thermal = SyntheticThermalSource(fog_severity=0.5)
    custom_radar = SyntheticRadarSource(fps=15.0)

    pipe = Pipeline(
        thermal_source=custom_thermal,
        radar_source=custom_radar,
        log_path=None,
    )
    result = _run_until_frame(pipe)
    assert isinstance(result, FrameResult)
    pipe.close()


# ---------------------------------------------------------------------------
# Runner for direct execution (mirrors the pattern in test_pipeline.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import inspect

    current_module = sys.modules[__name__]
    test_fns = [
        f
        for name, f in inspect.getmembers(current_module, inspect.isfunction)
        if name.startswith("test_")
    ]
    passed, failed = 0, 0
    for fn in test_fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"ERROR {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
