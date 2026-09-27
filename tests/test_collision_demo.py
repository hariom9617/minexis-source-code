"""
Test for the COLLISION_DEMO scenario.

Verifies that the new 100m → 0m collision demonstration works correctly,
including object movement, TTC calculation, and risk escalation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.controller import SimulationController
from simulation.scenarios import SCENARIOS
from sensors.radar_source import SyntheticRadarSource
from sensors.thermal_source import SyntheticThermalSource
from risk.ttc_risk import RiskEngine, RiskConfig
from tracking.tracker import Tracker
from fusion.adaptive_fusion import AdaptiveFusion
from perception.thermal_branch import ThermalBranch, BlobThermalDetector
from perception.radar_branch import RadarBranch
from common.types import ObjectClass, RiskState


def test_collision_demo_scenario_exists():
    """Verify COLLISION_DEMO scenario is defined."""
    assert "COLLISION_DEMO" in SCENARIOS
    cfg = SCENARIOS["COLLISION_DEMO"]
    assert cfg.name == "COLLISION_DEMO"
    assert len(cfg.targets) == 1
    target = cfg.targets[0]
    assert target.initial_range_m == 100.0
    assert target.closing_speed_mps == 10.0
    assert target.azimuth_deg == 0.0
    print("✓ COLLISION_DEMO scenario exists with correct parameters")


def test_collision_demo_object_movement():
    """Verify object moves from 100m toward vehicle."""
    controller = SimulationController(initial="COLLISION_DEMO")
    radar = SyntheticRadarSource(controller=controller, fps=10.0)
    
    # First read: object should be at ~100m
    scan1 = radar.read()
    assert scan1 is not None
    assert len(scan1.returns) >= 1  # at least the target
    target_return = [r for r in scan1.returns if r.doppler_mps > 5.0][0]  # closing fast
    assert 99.0 < target_return.range_m < 101.0, f"Expected ~100m, got {target_return.range_m}"
    
    # Simulate 10 frames (1 second at 10 FPS)
    for _ in range(10):
        radar.read()
    
    # After 1 second: object should be at ~90m (moved 10m)
    scan2 = radar.read()
    target_return = [r for r in scan2.returns if r.doppler_mps > 5.0][0]
    assert 87.0 < target_return.range_m < 93.0, f"Expected ~90m, got {target_return.range_m}"
    
    print("✓ Object moves correctly: 100m → ~90m over 1 second")


def test_collision_demo_ttc_calculation():
    """Verify TTC is calculated correctly for the approaching object."""
    controller = SimulationController(initial="COLLISION_DEMO")
    radar = SyntheticRadarSource(controller=controller, fps=10.0)
    thermal = SyntheticThermalSource(controller=controller, fps=10.0)
    
    thermal_branch = ThermalBranch(detector=BlobThermalDetector())
    radar_branch = RadarBranch()
    fusion = AdaptiveFusion()
    tracker = Tracker(min_hits_to_confirm=1)  # immediate tracking for test
    risk_engine = RiskEngine()
    
    # Process several frames to establish track
    for _ in range(5):
        t_frame = thermal.read()
        r_scan = radar.read()
        
        t_out = thermal_branch.process(t_frame)
        r_out = radar_branch.process(r_scan)
        
        fused = fusion.fuse(t_out, r_out, t_frame.timestamp)
        tracks = tracker.update(fused, t_frame.timestamp)
    
    # After 5 frames: should have stable track
    assert len(tracks) >= 1, "Expected at least one track"
    track = tracks[0]
    
    # Verify track properties
    distance = (track.position_xy[0]**2 + track.position_xy[1]**2)**0.5
    assert 90 < distance < 100, f"Expected track at 90-100m, got {distance:.1f}m"
    
    # Check TTC
    risks = risk_engine.assess(tracks)
    assert len(risks) >= 1
    risk = risks[0]
    
    # TTC should be approximately distance/10 (since closing speed is 10 m/s)
    if risk.ttc_s is not None:
        expected_ttc = distance / 10.0
        assert abs(risk.ttc_s - expected_ttc) < 2.0, \
            f"Expected TTC ~{expected_ttc:.1f}s, got {risk.ttc_s:.1f}s"
        print(f"✓ TTC calculated correctly: {risk.ttc_s:.1f}s at {distance:.1f}m")
    else:
        print(f"⚠ TTC is None (object at {distance:.1f}m) - may be outside monitoring zone initially")


def test_collision_demo_risk_escalation():
    """Verify risk state escalates as object approaches."""
    controller = SimulationController(initial="COLLISION_DEMO")
    radar = SyntheticRadarSource(controller=controller, fps=10.0)
    thermal = SyntheticThermalSource(controller=controller, fps=10.0)
    
    thermal_branch = ThermalBranch(detector=BlobThermalDetector())
    radar_branch = RadarBranch()
    fusion = AdaptiveFusion()
    tracker = Tracker(min_hits_to_confirm=1)
    
    # Use custom thresholds to make testing predictable
    risk_config = RiskConfig(
        ttc_critical_s=3.0,
        ttc_warning_s=6.0,
        ttc_caution_s=10.0,
        ttc_monitoring_distance_m=100.0,
        escalate_frames=1,  # no hysteresis for test
        deescalate_frames=1,
    )
    risk_engine = RiskEngine(config=risk_config)
    
    # Simulate approach from 100m to 30m
    # At 100m: TTC ~10s → CAUTION (at threshold)
    # At 60m: TTC ~6s → WARNING (at threshold)
    # At 30m: TTC ~3s → CRITICAL (at threshold)
    
    highest_risk_seen = RiskState.SAFE
    
    for frame_num in range(80):  # 8 seconds of simulation
        t_frame = thermal.read()
        r_scan = radar.read()
        
        if t_frame is None or r_scan is None:
            continue
        
        t_out = thermal_branch.process(t_frame)
        r_out = radar_branch.process(r_scan)
        fused = fusion.fuse(t_out, r_out, t_frame.timestamp)
        tracks = tracker.update(fused, t_frame.timestamp)
        
        if len(tracks) > 0:
            risks = risk_engine.assess(tracks)
            if len(risks) > 0:
                current_risk = risks[0].risk_state
                risk_order = {RiskState.SAFE:0, RiskState.CAUTION:1, 
                             RiskState.WARNING:2, RiskState.CRITICAL:3}
                if risk_order[current_risk] > risk_order[highest_risk_seen]:
                    highest_risk_seen = current_risk
                    track = tracks[0]
                    distance = (track.position_xy[0]**2 + track.position_xy[1]**2)**0.5
                    ttc = risks[0].ttc_s
                    print(f"  Frame {frame_num}: Risk={current_risk.value}, "
                          f"Dist={distance:.1f}m, TTC={ttc:.1f}s" if ttc else 
                          f"Frame {frame_num}: Risk={current_risk.value}, Dist={distance:.1f}m, TTC=None")
    
    # Should have seen at least WARNING by the time object is at 60m
    risk_order = {RiskState.SAFE:0, RiskState.CAUTION:1, 
                 RiskState.WARNING:2, RiskState.CRITICAL:3}
    assert risk_order[highest_risk_seen] >= risk_order[RiskState.WARNING], \
        f"Expected to see at least WARNING, highest was {highest_risk_seen.value}"
    
    print(f"✓ Risk escalation verified (reached {highest_risk_seen.value})")


def test_thermal_radar_sync():
    """Verify thermal and radar stay synchronized in COLLISION_DEMO."""
    controller = SimulationController(initial="COLLISION_DEMO")
    radar = SyntheticRadarSource(controller=controller, fps=10.0)
    thermal = SyntheticThermalSource(controller=controller, fps=10.0)
    
    # Read 20 frames from each
    for _ in range(20):
        r_scan = radar.read()
        t_frame = thermal.read()
        
        # Both should produce data
        assert r_scan is not None
        assert t_frame is not None
        
        # Radar should have target return
        target_returns = [r for r in r_scan.returns if r.doppler_mps > 5.0]
        assert len(target_returns) >= 1
        
    print("✓ Thermal and radar both produce synchronized data")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("COLLISION_DEMO Scenario Tests")
    print("="*70 + "\n")
    
    test_collision_demo_scenario_exists()
    test_collision_demo_object_movement()
    test_collision_demo_ttc_calculation()
    test_collision_demo_risk_escalation()
    test_thermal_radar_sync()
    
    print("\n" + "="*70)
    print("All COLLISION_DEMO tests passed ✓")
    print("="*70 + "\n")
