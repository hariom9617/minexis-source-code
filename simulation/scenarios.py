"""
MINEXIS demo scenario definitions.

Each ScenarioConfig describes the *sensor-level physics* that should be
simulated — target range, closing speed, azimuth, number of targets, etc.
These values are injected into the synthetic sensor sources so the REAL
perception → fusion → tracking → TTC → risk → alert pipeline evaluates
them naturally and produces the appropriate output.

IMPORTANT: The final risk state is NEVER hardcoded here.  The thresholds
come from RiskConfig in risk/ttc_risk.py.  The numbers below are chosen
so the real pipeline will produce the described risk level, but it is the
RiskEngine that makes that determination.

Threshold reference (from RiskConfig defaults):
  ttc_critical_s  = 3.0 s
  ttc_warning_s   = 6.0 s
  ttc_caution_s   = 10.0 s
  dist_critical_m = 5.0 m
  dist_warning_m  = 12.0 m
  dist_caution_m  = 25.0 m
  path_half_width = 3.0 m   (lateral boundary of the driving corridor)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Canonical scenario names
# ---------------------------------------------------------------------------

ScenarioName = Literal[
    "SAFE",
    "CAUTION",
    "WARNING",
    "CRITICAL",
    "PEDESTRIAN_APPROACH",
    "MULTI_TARGET",
    "COLLISION_DEMO",
]

ALL_SCENARIO_NAMES: list[str] = [
    "SAFE",
    "CAUTION",
    "WARNING",
    "CRITICAL",
    "PEDESTRIAN_APPROACH",
    "MULTI_TARGET",
    "COLLISION_DEMO",
]


# ---------------------------------------------------------------------------
# Single-target descriptor
# ---------------------------------------------------------------------------

@dataclass
class TargetSpec:
    """Parameters for one simulated radar/thermal target."""

    # Radar-side parameters
    initial_range_m:      float   # starting range (metres)
    closing_speed_mps:    float   # positive = approaching; negative = receding
    azimuth_deg:          float   # lateral angle from vehicle heading (0 = dead ahead)
    rcs_dbsm:             float   # radar cross-section — affects detection reliability
    snr_db:               float   # signal-to-noise — higher → more reliable cluster

    # Thermal-side parameters (normalised 0-1 intensity)
    thermal_intensity:    float   # hot-blob brightness (1.0 = full contrast)
    blob_size_px:         float   # initial hot-blob radius in synthetic image pixels

    # Reset range: when the target passes this, restart at initial_range_m
    reset_range_m:        float = 3.0


# ---------------------------------------------------------------------------
# Full scenario config
# ---------------------------------------------------------------------------

@dataclass
class ScenarioConfig:
    name:        str
    description: str
    targets:     list[TargetSpec]

    # Thermal fog severity for this scenario (0 = clear, 1 = dense)
    fog_severity: float = 0.0


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, ScenarioConfig] = {

    # ------------------------------------------------------------------ SAFE
    # Target far away, moving slowly, not on path.
    "SAFE": ScenarioConfig(
        name="SAFE",
        description="No dangerous object on path. System remains in SAFE state.",
        fog_severity=0.0,
        targets=[
            TargetSpec(
                initial_range_m=55.0,
                closing_speed_mps=0.5,   # barely approaching
                azimuth_deg=22.0,        # well off to the side — outside the corridor
                rcs_dbsm=3.0,
                snr_db=12.0,
                thermal_intensity=0.4,
                blob_size_px=8.0,
                reset_range_m=45.0,      # reset before it ever gets close
            )
        ],
    ),

    # --------------------------------------------------------------- CAUTION
    # Target at moderate range, closing at walking speed, on or near path.
    # TTC ≈ 30/1.5 = 20 s → CAUTION (ttc_caution_s=10, so 20 s > 10 s …
    # but distance ≈ 28 m is within dist_caution_m=25 as it approaches).
    # Pipeline will enter CAUTION via the distance-based fallback.
    "CAUTION": ScenarioConfig(
        name="CAUTION",
        description="Object at moderate distance, approaching slowly. CAUTION state.",
        fog_severity=0.0,
        targets=[
            TargetSpec(
                initial_range_m=24.0,    # just inside dist_caution_m=25 m
                closing_speed_mps=2.0,
                azimuth_deg=1.0,         # near dead-ahead → high path_overlap
                rcs_dbsm=6.0,
                snr_db=16.0,
                thermal_intensity=0.7,
                blob_size_px=14.0,
                reset_range_m=18.0,
            )
        ],
    ),

    # --------------------------------------------------------------- WARNING
    # Target inside warning distance, closing at moderate speed.
    # TTC ≈ 10/2.8 ≈ 3.6 s → WARNING (ttc_warning_s=6 s).
    "WARNING": ScenarioConfig(
        name="WARNING",
        description="Object closing at moderate speed in the driving corridor. WARNING state.",
        fog_severity=0.0,
        targets=[
            TargetSpec(
                initial_range_m=10.0,   # well inside warning zone
                closing_speed_mps=2.8,  # TTC ≈ 10/2.8 ≈ 3.6 s → ≤ ttc_warning_s=6 s
                azimuth_deg=0.5,        # dead ahead
                rcs_dbsm=8.0,
                snr_db=18.0,
                thermal_intensity=0.85,
                blob_size_px=18.0,
                reset_range_m=4.0,
            )
        ],
    ),

    # -------------------------------------------------------------- CRITICAL
    # Close-range target, high closing velocity.
    # TTC ≈ 4/5.5 ≈ 0.73 s → CRITICAL (ttc_critical_s=3.0 s).
    "CRITICAL": ScenarioConfig(
        name="CRITICAL",
        description="Imminent collision — object very close with high closing speed. CRITICAL.",
        fog_severity=0.0,
        targets=[
            TargetSpec(
                initial_range_m=4.5,    # inside critical zone
                closing_speed_mps=5.5,  # TTC ≈ 4.5/5.5 ≈ 0.82 s → CRITICAL
                azimuth_deg=0.3,        # essentially dead ahead
                rcs_dbsm=12.0,          # strong, reliable return
                snr_db=22.0,
                thermal_intensity=0.95,
                blob_size_px=22.0,
                reset_range_m=2.5,
            )
        ],
    ),

    # ----------------------------------------------- PEDESTRIAN_APPROACH
    # Thermal detects a person (strong hot blob), radar sees corresponding
    # closing target.  Scenario holds steady in CAUTION→WARNING region so
    # the fusion evidence and escalation are both visible.
    "PEDESTRIAN_APPROACH": ScenarioConfig(
        name="PEDESTRIAN_APPROACH",
        description="Thermal detects pedestrian, radar corroborates. Risk escalates as person approaches.",
        fog_severity=0.0,
        targets=[
            TargetSpec(
                initial_range_m=18.0,
                closing_speed_mps=1.8,   # slow walking pace
                azimuth_deg=0.8,         # slightly right of centre, in corridor
                rcs_dbsm=5.0,            # small RCS for person
                snr_db=15.0,
                thermal_intensity=0.90,  # bright person hot-spot
                blob_size_px=10.0,       # small blob = person not vehicle
                reset_range_m=5.0,
            )
        ],
    ),

    # --------------------------------------------------------------- MULTI_TARGET
    # 4 targets at different ranges/azimuths/speeds.  Tracker must maintain
    # separate IDs.  Dashboard shows multiple fused objects and tracks.
    "MULTI_TARGET": ScenarioConfig(
        name="MULTI_TARGET",
        description="Multiple simultaneous targets. Tracker maintains separate IDs for each.",
        fog_severity=0.0,
        targets=[
            # Target A — dead ahead, moderate range, closing
            TargetSpec(
                initial_range_m=20.0,
                closing_speed_mps=3.0,
                azimuth_deg=0.5,
                rcs_dbsm=8.0,
                snr_db=18.0,
                thermal_intensity=0.85,
                blob_size_px=16.0,
                reset_range_m=5.0,
            ),
            # Target B — right side, closer, slower
            TargetSpec(
                initial_range_m=14.0,
                closing_speed_mps=1.5,
                azimuth_deg=12.0,
                rcs_dbsm=6.0,
                snr_db=15.0,
                thermal_intensity=0.70,
                blob_size_px=12.0,
                reset_range_m=6.0,
            ),
            # Target C — left side, far, not immediately threatening
            TargetSpec(
                initial_range_m=35.0,
                closing_speed_mps=2.2,
                azimuth_deg=-10.0,
                rcs_dbsm=5.0,
                snr_db=13.0,
                thermal_intensity=0.60,
                blob_size_px=10.0,
                reset_range_m=15.0,
            ),
            # Target D — slightly off-path, vehicle-like large RCS
            TargetSpec(
                initial_range_m=28.0,
                closing_speed_mps=4.0,
                azimuth_deg=5.0,
                rcs_dbsm=14.0,
                snr_db=20.0,
                thermal_intensity=0.80,
                blob_size_px=20.0,
                reset_range_m=8.0,
            ),
        ],
    ),

    # --------------------------------------------------------- COLLISION_DEMO
    # Realistic approaching object demonstration for 100-meter TTC monitoring.
    # One person-sized object starts at 100m dead ahead and approaches at 10 m/s,
    # reaching the vehicle in exactly 10 seconds.  The object then resets and
    # repeats the approach.  The TTC should naturally progress:
    #   100m → TTC ~10s (SAFE)
    #   75m  → TTC ~7.5s (CAUTION via TTC or distance fallback)
    #   60m  → TTC ~6s (WARNING, inside ttc_warning_s=6s threshold)
    #   30m  → TTC ~3s (CRITICAL, inside ttc_critical_s=3s threshold)
    #   0m   → CRITICAL, then reset
    # Reset occurs when range falls below 2m (to avoid sensor near-field issues).
    "COLLISION_DEMO": ScenarioConfig(
        name="COLLISION_DEMO",
        description="100m → 0m approach over 10s. Demonstrates TTC monitoring zone, risk escalation, and alerts.",
        fog_severity=0.0,
        targets=[
            TargetSpec(
                initial_range_m=100.0,  # Start at exactly 100 meters
                closing_speed_mps=10.0,  # Approach at 10 m/s → reach vehicle in 10 seconds
                azimuth_deg=0.0,         # Dead ahead → maximum path_overlap
                rcs_dbsm=5.0,            # Person-sized radar cross-section
                snr_db=16.0,             # Good signal quality
                thermal_intensity=0.90,  # Bright thermal signature (person/vehicle)
                blob_size_px=12.0,       # Moderate blob size
                reset_range_m=2.0,       # Reset when very close (avoiding sensor near-field)
            )
        ],
    ),
}
