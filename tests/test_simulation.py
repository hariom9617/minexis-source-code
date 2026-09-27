"""
Tests for the simulation layer.

Verifies:
- All scenario configs are structurally valid
- SimulationController get/set/list behaviour
- SyntheticRadarSource generates correct returns per scenario
- SyntheticThermalSource generates frames per scenario
- CRITICAL scenario produces stronger closing than WARNING
- MULTI_TARGET produces multiple independent radar clusters
- Scenario switching takes effect immediately
"""

from __future__ import annotations

import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.scenarios import SCENARIOS, ALL_SCENARIO_NAMES, TargetSpec, ScenarioConfig
from simulation.controller import SimulationController
from sensors.radar_source import SyntheticRadarSource
from sensors.thermal_source import SyntheticThermalSource
from perception.radar_branch import RadarBranch


# ---------------------------------------------------------------------------
# Scenario definition tests
# ---------------------------------------------------------------------------

def test_all_scenario_names_present():
    for name in ALL_SCENARIO_NAMES:
        assert name in SCENARIOS, f"Scenario {name!r} missing from SCENARIOS dict"


def test_scenario_configs_have_at_least_one_target():
    for name, cfg in SCENARIOS.items():
        assert len(cfg.targets) >= 1, f"{name} has no targets"


def test_scenario_configs_fields():
    for name, cfg in SCENARIOS.items():
        assert isinstance(cfg.name, str)
        assert isinstance(cfg.description, str)
        assert 0.0 <= cfg.fog_severity <= 1.0
        for t in cfg.targets:
            assert t.initial_range_m > 0
            assert t.closing_speed_mps >= 0
            assert t.snr_db > 0
            assert 0.0 < t.thermal_intensity <= 1.0
            assert t.blob_size_px > 0
            assert t.reset_range_m >= 0


def test_multi_target_has_multiple_targets():
    cfg = SCENARIOS["MULTI_TARGET"]
    assert len(cfg.targets) >= 2, "MULTI_TARGET must have at least 2 targets"


def test_critical_scenario_range_closer_than_warning():
    crit = SCENARIOS["CRITICAL"].targets[0]
    warn = SCENARIOS["WARNING"].targets[0]
    assert crit.initial_range_m < warn.initial_range_m, (
        "CRITICAL initial range must be closer than WARNING"
    )


def test_critical_scenario_speed_faster_than_warning():
    crit = SCENARIOS["CRITICAL"].targets[0]
    warn = SCENARIOS["WARNING"].targets[0]
    assert crit.closing_speed_mps > warn.closing_speed_mps, (
        "CRITICAL closing speed must be higher than WARNING"
    )


def test_safe_target_is_off_path():
    """SAFE scenario target should be at large azimuth (outside corridor)."""
    safe_target = SCENARIOS["SAFE"].targets[0]
    # Path half-width is 3 m; at 55 m range, azimuth >3° puts target outside corridor.
    assert abs(safe_target.azimuth_deg) > 5.0, (
        "SAFE target should be well off to the side"
    )


# ---------------------------------------------------------------------------
# SimulationController tests
# ---------------------------------------------------------------------------

def test_controller_default_scenario():
    ctrl = SimulationController()
    assert ctrl.get_current_scenario() == "SAFE"


def test_controller_set_valid_scenario():
    ctrl = SimulationController()
    ctrl.set_scenario("CRITICAL")
    assert ctrl.get_current_scenario() == "CRITICAL"


def test_controller_set_case_insensitive():
    ctrl = SimulationController()
    ctrl.set_scenario("critical")
    assert ctrl.get_current_scenario() == "CRITICAL"


def test_controller_set_invalid_raises():
    ctrl = SimulationController()
    try:
        ctrl.set_scenario("NONEXISTENT")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_controller_get_available_scenarios():
    ctrl = SimulationController()
    available = ctrl.get_available_scenarios()
    names = [s["name"] for s in available]
    for expected in ALL_SCENARIO_NAMES:
        assert expected in names


def test_controller_get_current_config():
    ctrl = SimulationController()
    ctrl.set_scenario("WARNING")
    cfg = ctrl.get_current_config()
    assert cfg.name == "WARNING"
    assert len(cfg.targets) >= 1


def test_controller_initial_validation():
    try:
        SimulationController(initial="BOGUS")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# SyntheticRadarSource scenario mode
# ---------------------------------------------------------------------------

def test_radar_source_default_mode_unchanged():
    """Without a controller, radar source behaves as before."""
    src = SyntheticRadarSource()
    scan = src.read()
    assert scan is not None
    assert len(scan.returns) >= 1


def test_radar_source_scenario_mode_produces_returns():
    ctrl = SimulationController()
    src = SyntheticRadarSource(controller=ctrl)
    scan = src.read()
    assert scan is not None
    assert len(scan.returns) >= 1


def test_radar_source_multi_target_produces_multiple_returns():
    """MULTI_TARGET should produce as many real returns as targets."""
    ctrl = SimulationController()
    ctrl.set_scenario("MULTI_TARGET")
    src = SyntheticRadarSource(controller=ctrl, clutter_returns=0)
    scan = src.read()
    n_targets = len(SCENARIOS["MULTI_TARGET"].targets)
    # With no clutter, all returns are target returns
    assert len(scan.returns) >= n_targets


def test_radar_source_critical_closer_than_warning():
    """After one step, CRITICAL range should be much shorter than WARNING."""
    ctrl_c = SimulationController()
    ctrl_c.set_scenario("CRITICAL")
    src_c = SyntheticRadarSource(controller=ctrl_c, clutter_returns=0, seed=1)

    ctrl_w = SimulationController()
    ctrl_w.set_scenario("WARNING")
    src_w = SyntheticRadarSource(controller=ctrl_w, clutter_returns=0, seed=1)

    scan_c = src_c.read()
    scan_w = src_w.read()

    # First return is the target return (no clutter)
    range_c = scan_c.returns[0].range_m
    range_w = scan_w.returns[0].range_m
    assert range_c < range_w, (
        f"CRITICAL range ({range_c:.1f} m) should be less than WARNING ({range_w:.1f} m)"
    )


def test_radar_source_scenario_switch_takes_effect():
    """Switching scenario mid-stream changes subsequent returns."""
    ctrl = SimulationController()
    ctrl.set_scenario("SAFE")
    src = SyntheticRadarSource(controller=ctrl, clutter_returns=0, seed=42)

    scan_safe = src.read()
    range_safe = scan_safe.returns[0].range_m

    ctrl.set_scenario("CRITICAL")
    # After switch, next read should reset to CRITICAL initial range
    scan_crit = src.read()
    range_crit = scan_crit.returns[0].range_m

    # CRITICAL initial_range_m (4.5) << SAFE initial_range_m (55.0)
    assert range_crit < range_safe, (
        f"After switch to CRITICAL range {range_crit:.1f} should be < SAFE range {range_safe:.1f}"
    )


# ---------------------------------------------------------------------------
# SyntheticThermalSource scenario mode
# ---------------------------------------------------------------------------

def test_thermal_source_default_mode_unchanged():
    src = SyntheticThermalSource()
    frame = src.read()
    assert frame is not None
    assert frame.image.shape == (256, 320)
    assert 0.0 <= frame.image.min() and frame.image.max() <= 1.0


def test_thermal_source_scenario_mode_produces_frame():
    ctrl = SimulationController()
    src = SyntheticThermalSource(controller=ctrl)
    frame = src.read()
    assert frame is not None
    assert frame.image.ndim == 2
    assert frame.meta.get("scenario") == "SAFE"


def test_thermal_source_multi_target_has_multiple_blobs():
    """MULTI_TARGET should produce a brighter image than SAFE."""
    ctrl_m = SimulationController()
    ctrl_m.set_scenario("MULTI_TARGET")
    src_m = SyntheticThermalSource(controller=ctrl_m, seed=1)

    ctrl_s = SimulationController()
    ctrl_s.set_scenario("SAFE")
    src_s = SyntheticThermalSource(controller=ctrl_s, seed=1)

    import numpy as np
    frame_m = src_m.read()
    frame_s = src_s.read()

    # MULTI_TARGET has 4 bright blobs — mean intensity should be higher
    assert float(frame_m.image.mean()) > float(frame_s.image.mean()), (
        "MULTI_TARGET frame should be brighter than SAFE"
    )


# ---------------------------------------------------------------------------
# Full pipeline scenario integration
# ---------------------------------------------------------------------------

def test_critical_scenario_pipeline_reaches_critical():
    """
    Drive the real pipeline with CRITICAL scenario for enough frames
    that RiskEngine (with hysteresis) escalates to CRITICAL.
    """
    from pipeline import Pipeline

    ctrl = SimulationController()
    ctrl.set_scenario("CRITICAL")

    pipe = Pipeline(controller=ctrl, log_path=None)
    results = []
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and len(results) < 60:
        r = pipe.step()
        if r is not None:
            results.append(r)
        else:
            time.sleep(0.01)
    pipe.close()

    risk_states = [r.highest_risk.value for r in results]
    assert "critical" in risk_states, (
        f"CRITICAL scenario never reached 'critical' risk. States seen: {set(risk_states)}"
    )


def test_multi_target_pipeline_produces_multiple_tracks():
    """
    Drive the real pipeline with MULTI_TARGET scenario and confirm the
    tracker maintains at least 2 separate track IDs across frames.
    """
    from pipeline import Pipeline

    ctrl = SimulationController()
    ctrl.set_scenario("MULTI_TARGET")

    pipe = Pipeline(controller=ctrl, log_path=None)
    all_track_ids: set[int] = set()
    deadline = time.monotonic() + 8.0
    frame_count = 0
    while time.monotonic() < deadline and frame_count < 60:
        r = pipe.step()
        if r is not None:
            frame_count += 1
            for t in r.tracks:
                all_track_ids.add(t.track_id)
        else:
            time.sleep(0.01)
    pipe.close()

    assert len(all_track_ids) >= 2, (
        f"MULTI_TARGET should produce ≥2 track IDs, got: {all_track_ids}"
    )


def test_scenario_field_on_frame_result():
    from pipeline import Pipeline

    ctrl = SimulationController()
    ctrl.set_scenario("WARNING")
    pipe = Pipeline(controller=ctrl, log_path=None)

    result = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        result = pipe.step()
        if result is not None:
            break
        time.sleep(0.01)
    pipe.close()

    assert result is not None
    assert result.scenario == "WARNING"


# ---------------------------------------------------------------------------
# Direct runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import inspect
    import traceback

    mod = sys.modules[__name__]
    fns = [f for name, f in inspect.getmembers(mod, inspect.isfunction) if name.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
