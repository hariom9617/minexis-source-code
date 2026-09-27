"""
Shared data types for the MINEXIS pipeline.

Every stage of the pipeline (sensors -> sync -> perception -> evidence ->
fusion -> tracking -> risk -> alerts) passes data using these dataclasses.
Keeping them centralized means every module can be developed and tested
independently, and swapping synthetic sensors for real hardware later only
requires the sensor-source modules to change -- nothing downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


# ---------------------------------------------------------------------------
# Raw sensor data
# ---------------------------------------------------------------------------

@dataclass
class ThermalFrame:
    """A single thermal camera frame."""
    timestamp: float               # seconds, monotonic clock
    image: np.ndarray              # HxW (grayscale) or HxWx3, float32 normalized [0,1]
    frame_id: int
    meta: dict = field(default_factory=dict)  # e.g. {"sensor_temp_c": 34.2}


@dataclass
class RadarReturn:
    """A single raw radar detection point (post range-Doppler, pre-clustering)."""
    range_m: float
    azimuth_deg: float
    elevation_deg: float
    doppler_mps: float             # radial velocity, +ve = closing
    rcs_dbsm: float                # radar cross section
    snr_db: float


@dataclass
class RadarScan:
    """A full radar scan: many returns captured at ~the same timestamp."""
    timestamp: float
    returns: list[RadarReturn]
    scan_id: int
    meta: dict = field(default_factory=dict)  # e.g. {"health_ok": True}


# ---------------------------------------------------------------------------
# Per-modality perception output
# ---------------------------------------------------------------------------

class ObjectClass(str, Enum):
    PERSON = "person"
    VEHICLE = "vehicle"
    LARGE_OBSTACLE = "large_obstacle"
    UNKNOWN = "unknown"


@dataclass
class ThermalDetection:
    """One bounding-box detection from the thermal branch."""
    box_xyxy: tuple[float, float, float, float]   # pixel coords
    cls: ObjectClass
    confidence: float              # detector confidence, 0-1
    image_quality: float           # 0-1, contrast/sharpness/saturation composite


@dataclass
class ThermalPerceptionOutput:
    timestamp: float
    detections: list[ThermalDetection]
    frame_quality: float           # 0-1, overall frame-level quality


@dataclass
class RadarCluster:
    """One clustered object candidate from the radar branch."""
    range_m: float
    azimuth_deg: float
    elevation_deg: float
    doppler_mps: float
    rcs_dbsm: float
    snr_db: float
    point_count: int               # returns in this cluster
    persistence: float             # 0-1, how consistently this cluster has appeared


@dataclass
class RadarPerceptionOutput:
    timestamp: float
    clusters: list[RadarCluster]
    scan_quality: float            # 0-1, overall scan health/quality


# ---------------------------------------------------------------------------
# Evidence / reliability
# ---------------------------------------------------------------------------

@dataclass
class ModalityReliability:
    """Reliability score for one sensor's evidence about one candidate object."""
    reliability: float             # 0-1, higher = trust more
    uncertainty: float             # 0-1, higher = less certain
    health_ok: bool


class AgreementState(str, Enum):
    AGREEMENT = "agreement"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    THERMAL_ONLY = "thermal_only"
    RADAR_ONLY = "radar_only"


# ---------------------------------------------------------------------------
# Fusion output
# ---------------------------------------------------------------------------

@dataclass
class FusedObject:
    """One object after adaptive fusion of thermal + radar evidence."""
    timestamp: float
    position_xy: tuple[float, float]   # meters, vehicle frame (x=right, y=forward)
    velocity_xy: tuple[float, float]   # m/s, vehicle frame
    cls: ObjectClass
    confidence: float                  # fused confidence, 0-1
    thermal_weight: float              # 0-1, contribution of thermal to this fusion
    radar_weight: float                # 0-1, contribution of radar to this fusion
    agreement: AgreementState
    source_thermal: Optional[ThermalDetection] = None
    source_radar: Optional[RadarCluster] = None


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------

@dataclass
class Track:
    """A tracked object with identity persisted across frames."""
    track_id: int
    position_xy: tuple[float, float]
    velocity_xy: tuple[float, float]
    cls: ObjectClass
    confidence: float
    age_frames: int                # frames since track creation
    missed_frames: int             # consecutive frames without a matched detection
    history: list[tuple[float, float]] = field(default_factory=list)  # recent positions


# ---------------------------------------------------------------------------
# Risk / alerts
# ---------------------------------------------------------------------------

class RiskState(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    track_id: int
    ttc_s: Optional[float]         # None if not closing / not on path
    distance_m: float
    risk_state: RiskState
    path_overlap: float            # 0-1, how directly the object is in the driving corridor


@dataclass
class AlertEvent:
    timestamp: float
    risk_state: RiskState
    track_id: int
    message: str
    direction_hint: Optional[str] = None   # e.g. "ahead-left"
