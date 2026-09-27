"""
Sanity tests for each pipeline stage. Not exhaustive -- these exist to
catch integration breakage (wrong shapes, crashed imports, obviously
wrong values) as the team builds on top of this skeleton, not to prove
correctness on real sensor data.

Run: python -m pytest tests/ -v
  or: python tests/test_pipeline.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from sensors.thermal_source import SyntheticThermalSource
from sensors.radar_source import SyntheticRadarSource
from sync.synchronizer import Synchronizer
from perception.thermal_branch import ThermalBranch, BlobThermalDetector, compute_image_quality
from perception.radar_branch import RadarBranch
from fusion.adaptive_fusion import AdaptiveFusion
from tracking.tracker import Tracker
from risk.ttc_risk import RiskEngine, RiskConfig
from alerts.alert_manager import AlertManager
from common.types import (
    RadarScan, RadarReturn, FusedObject, Track, ObjectClass, RiskState,
)


def test_thermal_source_produces_frames():
    src = SyntheticThermalSource()
    frame = src.read()
    assert frame is not None
    assert frame.image.ndim == 2
    assert 0.0 <= frame.image.min() and frame.image.max() <= 1.0


def test_radar_source_produces_returns():
    src = SyntheticRadarSource()
    scan = src.read()
    assert scan is not None
    assert len(scan.returns) >= 1


def test_synchronizer_pairs_close_timestamps():
    sync = Synchronizer(max_skew_s=0.1)
    from common.types import ThermalFrame
    t = ThermalFrame(timestamp=1.00, image=np.zeros((10, 10), dtype=np.float32), frame_id=0)
    r = RadarScan(timestamp=1.02, returns=[], scan_id=0)
    sync.push_thermal(t)
    sync.push_radar(r)
    pair = sync.try_pair(now=1.02)
    assert pair is not None
    assert abs(pair.time_skew_s - 0.02) < 1e-6


def test_synchronizer_rejects_large_skew():
    sync = Synchronizer(max_skew_s=0.05)
    from common.types import ThermalFrame
    t = ThermalFrame(timestamp=1.00, image=np.zeros((10, 10), dtype=np.float32), frame_id=0)
    r = RadarScan(timestamp=1.50, returns=[], scan_id=0)
    sync.push_thermal(t)
    sync.push_radar(r)
    pair = sync.try_pair(now=1.50)
    assert pair is None


def test_image_quality_bounds():
    flat = np.full((50, 50), 0.5, dtype=np.float32)
    q_flat = compute_image_quality(flat)
    assert 0.0 <= q_flat <= 1.0

    noisy = np.random.default_rng(0).normal(0.5, 0.2, (50, 50)).astype(np.float32)
    noisy = np.clip(noisy, 0, 1)
    q_noisy = compute_image_quality(noisy)
    assert 0.0 <= q_noisy <= 1.0
    # a flat image should score lower contrast/sharpness than a varied one
    assert q_noisy >= q_flat


def test_radar_branch_suppresses_clutter():
    branch = RadarBranch(doppler_static_thresh=0.4)
    returns = [
        RadarReturn(range_m=20, azimuth_deg=0, elevation_deg=0, doppler_mps=5.0, rcs_dbsm=8, snr_db=15),
        RadarReturn(range_m=25, azimuth_deg=10, elevation_deg=0, doppler_mps=0.05, rcs_dbsm=2, snr_db=12),  # static clutter
    ]
    scan = RadarScan(timestamp=0.0, returns=returns, scan_id=0)
    out = branch.process(scan)
    # the moving return should survive, the static one should be suppressed
    assert len(out.clusters) == 1
    assert abs(out.clusters[0].doppler_mps - 5.0) < 0.5


def test_thermal_branch_detects_synthetic_blob():
    branch = ThermalBranch(detector=BlobThermalDetector())
    src = SyntheticThermalSource()
    # step forward several frames so the object is visible
    frame = None
    for _ in range(5):
        frame = src.read()
    out = branch.process(frame)
    assert isinstance(out.frame_quality, float)
    # not asserting detections is non-empty every time (blob may be mid-reset),
    # just that it runs without error and returns a valid structure
    assert isinstance(out.detections, list)


def test_fusion_produces_valid_objects():
    from common.types import ThermalPerceptionOutput, RadarPerceptionOutput, ThermalDetection, RadarCluster
    t_out = ThermalPerceptionOutput(
        timestamp=0.0,
        detections=[
            ThermalDetection(box_xyxy=(150, 100, 170, 130), cls=ObjectClass.PERSON, confidence=0.9, image_quality=0.8)
        ],
        frame_quality=0.8,
    )
    r_out = RadarPerceptionOutput(
        timestamp=0.0,
        clusters=[
            RadarCluster(range_m=30, azimuth_deg=0.5, elevation_deg=0, doppler_mps=3.0, rcs_dbsm=8, snr_db=18, point_count=2, persistence=0.6)
        ],
        scan_quality=0.7,
    )
    fusion = AdaptiveFusion()
    fused = fusion.fuse(t_out, r_out, timestamp=0.0)
    assert len(fused) == 1
    obj = fused[0]
    assert 0.0 <= obj.confidence <= 1.0
    assert abs(obj.thermal_weight + obj.radar_weight - 1.0) < 1e-6


def test_tracker_assigns_stable_id_across_frames():
    tracker = Tracker(max_association_dist_m=5.0, min_hits_to_confirm=1)
    obj1 = FusedObject(
        timestamp=0.0, position_xy=(0.0, 30.0), velocity_xy=(0.0, -3.0), cls=ObjectClass.PERSON,
        confidence=0.8, thermal_weight=0.6, radar_weight=0.4, agreement="agreement",
    )
    tracks1 = tracker.update([obj1], timestamp=0.0)
    assert len(tracks1) == 1
    tid = tracks1[0].track_id

    obj2 = FusedObject(
        timestamp=0.1, position_xy=(0.0, 29.7), velocity_xy=(0.0, -3.0), cls=ObjectClass.PERSON,
        confidence=0.8, thermal_weight=0.6, radar_weight=0.4, agreement="agreement",
    )
    tracks2 = tracker.update([obj2], timestamp=0.1)
    assert len(tracks2) == 1
    assert tracks2[0].track_id == tid  # same object -> same ID


def test_ttc_decreases_as_object_approaches():
    risk_engine = RiskEngine(RiskConfig())
    far_track = Track(track_id=1, position_xy=(0.0, 40.0), velocity_xy=(0.0, -3.0), cls=ObjectClass.PERSON,
                       confidence=0.8, age_frames=3, missed_frames=0)
    near_track = Track(track_id=1, position_xy=(0.0, 10.0), velocity_xy=(0.0, -3.0), cls=ObjectClass.PERSON,
                        confidence=0.8, age_frames=3, missed_frames=0)

    far_risk = risk_engine.assess([far_track])[0]
    near_risk = risk_engine.assess([near_track])[0]

    assert far_risk.ttc_s is not None and near_risk.ttc_s is not None
    assert near_risk.ttc_s < far_risk.ttc_s


def test_risk_hysteresis_prevents_single_frame_flicker():
    config = RiskConfig(escalate_frames=3, deescalate_frames=3)
    risk_engine = RiskEngine(config)

    safe_track = Track(track_id=1, position_xy=(0.0, 40.0), velocity_xy=(0.0, 0.0), cls=ObjectClass.PERSON,
                        confidence=0.8, age_frames=1, missed_frames=0)
    critical_track = Track(track_id=1, position_xy=(0.0, 2.0), velocity_xy=(0.0, -3.0), cls=ObjectClass.PERSON,
                            confidence=0.8, age_frames=1, missed_frames=0)

    r1 = risk_engine.assess([safe_track])[0]
    assert r1.risk_state == RiskState.SAFE

    # a single critical-looking frame should NOT immediately jump to CRITICAL
    r2 = risk_engine.assess([critical_track])[0]
    assert r2.risk_state != RiskState.CRITICAL  # still climbing due to hysteresis


def test_alert_manager_skips_safe_state():
    am = AlertManager()
    from common.types import RiskAssessment
    safe = RiskAssessment(track_id=1, ttc_s=None, distance_m=50, risk_state=RiskState.SAFE, path_overlap=0.0)
    events = am.generate([safe], {}, timestamp=0.0)
    assert events == []


if __name__ == "__main__":
    import inspect
    current_module = sys.modules[__name__]
    test_fns = [f for name, f in inspect.getmembers(current_module, inspect.isfunction) if name.startswith("test_")]
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
            print(f"ERROR {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
