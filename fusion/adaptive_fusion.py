"""
Evidence-aware adaptive fusion.

Implements the doc's section 7 procedure:
  1. Match thermal boxes to radar clusters (spatial + time gating)
  2. Compute per-modality reliability (evidence module)
  3. Identify agreement / partial agreement / conflict
  4. Calculate adaptive weights
  5. Fuse compatible observations at decision level
  6. Preserve uncertainty for unresolved conflicts near the driving corridor

Coordinate note: thermal detections are in pixel space, radar clusters are
in (range, azimuth) polar space. Matching them requires a projection from
one frame to the other. For the prototype we use a simple calibrated
mapping (a linear azimuth<->pixel-x relationship); replace
`pixel_to_azimuth` / `azimuth_to_pixel` with your real camera-radar
extrinsic calibration once hardware is mounted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import (
    ThermalDetection,
    ThermalPerceptionOutput,
    RadarCluster,
    RadarPerceptionOutput,
    FusedObject,
    AgreementState,
    ObjectClass,
)
from evidence.evidence_module import (
    thermal_reliability,
    radar_reliability,
    estimate_environmental_severity,
)


@dataclass
class CalibrationConfig:
    """Simple pinhole-ish calibration: maps thermal pixel-x to azimuth degrees.

    Replace with your real calibrated intrinsics/extrinsics once the
    thermal camera and radar are physically mounted and calibrated
    together (per the doc's "calibrate rotation/translation" step).
    """
    image_width_px: int = 320
    horizontal_fov_deg: float = 50.0

    def pixel_center_to_azimuth(self, box_xyxy: tuple[float, float, float, float]) -> float:
        x0, _, x1, _ = box_xyxy
        cx = (x0 + x1) / 2.0
        # map [0, width] -> [-fov/2, +fov/2]
        frac = (cx / self.image_width_px) - 0.5
        return frac * self.horizontal_fov_deg


class AdaptiveFusion:
    def __init__(
        self,
        calibration: CalibrationConfig | None = None,
        azimuth_gate_deg: float = 8.0,
        conflict_azimuth_deg: float = 15.0,
    ):
        self.calib = calibration or CalibrationConfig()
        self.azimuth_gate_deg = azimuth_gate_deg
        self.conflict_azimuth_deg = conflict_azimuth_deg

    def fuse(
        self,
        thermal_output: ThermalPerceptionOutput,
        radar_output: RadarPerceptionOutput,
        timestamp: float,
    ) -> list[FusedObject]:
        severity = estimate_environmental_severity(thermal_output, radar_output)

        matched_thermal_idx: set[int] = set()
        matched_radar_idx: set[int] = set()
        fused: list[FusedObject] = []

        # -- Step 1-5: match + score + fuse compatible pairs -----------------
        for ti, tdet in enumerate(thermal_output.detections):
            t_az = self.calib.pixel_center_to_azimuth(tdet.box_xyxy)
            best_ri, best_diff = None, None

            for ri, rcl in enumerate(radar_output.clusters):
                if ri in matched_radar_idx:
                    continue
                diff = abs(rcl.azimuth_deg - t_az)
                if diff <= self.azimuth_gate_deg and (best_diff is None or diff < best_diff):
                    best_ri, best_diff = ri, diff

            if best_ri is not None:
                rcl = radar_output.clusters[best_ri]
                fused_obj = self._fuse_pair(
                    tdet, rcl, thermal_output.frame_quality, radar_output.scan_quality, timestamp, best_diff
                )
                fused.append(fused_obj)
                matched_thermal_idx.add(ti)
                matched_radar_idx.add(best_ri)

        # -- unmatched thermal detections: thermal-only fused objects --------
        for ti, tdet in enumerate(thermal_output.detections):
            if ti in matched_thermal_idx:
                continue
            rel = thermal_reliability(tdet, thermal_output.frame_quality)
            # Only surface thermal-only objects if reliability is reasonable;
            # otherwise it's likely noise with no corroborating evidence.
            if rel.reliability < 0.25:
                continue
            t_az = self.calib.pixel_center_to_azimuth(tdet.box_xyxy)
            approx_range = self._rough_range_from_box(tdet)
            fused.append(
                FusedObject(
                    timestamp=timestamp,
                    position_xy=self._polar_to_xy(approx_range, t_az),
                    velocity_xy=(0.0, 0.0),  # no radar => no velocity estimate yet
                    cls=tdet.cls,
                    confidence=rel.reliability,
                    thermal_weight=1.0,
                    radar_weight=0.0,
                    agreement=AgreementState.THERMAL_ONLY,
                    source_thermal=tdet,
                    source_radar=None,
                )
            )

        # -- unmatched radar clusters: radar-only fused objects ---------------
        for ri, rcl in enumerate(radar_output.clusters):
            if ri in matched_radar_idx:
                continue
            rel = radar_reliability(rcl, radar_output.scan_quality)
            if rel.reliability < 0.25:
                continue
            fused.append(
                FusedObject(
                    timestamp=timestamp,
                    position_xy=self._polar_to_xy(rcl.range_m, rcl.azimuth_deg),
                    velocity_xy=self._doppler_to_xy_velocity(rcl.doppler_mps, rcl.azimuth_deg),
                    cls=ObjectClass.UNKNOWN,  # radar alone can't classify well
                    confidence=rel.reliability,
                    thermal_weight=0.0,
                    radar_weight=1.0,
                    agreement=AgreementState.RADAR_ONLY,
                    source_thermal=None,
                    source_radar=rcl,
                )
            )

        return fused

    # -- helpers --------------------------------------------------------------

    def _fuse_pair(
        self,
        tdet: ThermalDetection,
        rcl: RadarCluster,
        frame_quality: float,
        scan_quality: float,
        timestamp: float,
        azimuth_diff: float,
    ) -> FusedObject:
        t_rel = thermal_reliability(tdet, frame_quality)
        r_rel = radar_reliability(rcl, scan_quality)

        # Agreement classification: how close is the spatial match?
        if azimuth_diff <= self.azimuth_gate_deg * 0.4:
            agreement = AgreementState.AGREEMENT
        elif azimuth_diff <= self.conflict_azimuth_deg:
            agreement = AgreementState.PARTIAL
        else:
            agreement = AgreementState.CONFLICT

        # Adaptive weighting: proportional to relative reliability, per
        # doc step 5 ("reliable thermal + weak radar -> more thermal
        # weight, and vice versa"). Add epsilon to avoid divide-by-zero
        # when both are near-zero.
        total_rel = t_rel.reliability + r_rel.reliability + 1e-6
        thermal_weight = t_rel.reliability / total_rel
        radar_weight = r_rel.reliability / total_rel

        fused_confidence = float(
            np.clip(
                thermal_weight * t_rel.reliability + radar_weight * r_rel.reliability,
                0.0,
                1.0,
            )
        )
        # Penalize confidence when modalities actively conflict, per doc
        # step 7 ("maintain a cautious risk state rather than silently
        # dropping the hazard" -- don't drop it, but don't over-trust it).
        if agreement == AgreementState.CONFLICT:
            fused_confidence *= 0.6

        position = self._polar_to_xy(rcl.range_m, rcl.azimuth_deg)
        velocity = self._doppler_to_xy_velocity(rcl.doppler_mps, rcl.azimuth_deg)

        return FusedObject(
            timestamp=timestamp,
            position_xy=position,
            velocity_xy=velocity,
            cls=tdet.cls,
            confidence=fused_confidence,
            thermal_weight=float(thermal_weight),
            radar_weight=float(radar_weight),
            agreement=agreement,
            source_thermal=tdet,
            source_radar=rcl,
        )

    @staticmethod
    def _polar_to_xy(range_m: float, azimuth_deg: float) -> tuple[float, float]:
        rad = math.radians(azimuth_deg)
        x = range_m * math.sin(rad)   # lateral
        y = range_m * math.cos(rad)   # forward
        return (x, y)

    @staticmethod
    def _doppler_to_xy_velocity(doppler_mps: float, azimuth_deg: float) -> tuple[float, float]:
        """Approximate: assume closing velocity is roughly along the
        line-of-sight (a simplification -- a real system would need
        multiple radar returns or track-derived velocity for a true
        2D velocity vector)."""
        rad = math.radians(azimuth_deg)
        vx = -doppler_mps * math.sin(rad)
        vy = -doppler_mps * math.cos(rad)  # negative doppler convention: closing = negative range-rate
        return (vx, vy)

    @staticmethod
    def _rough_range_from_box(tdet: ThermalDetection) -> float:
        """Very rough monocular range estimate from box size -- placeholder
        until radar corroborates. Bigger box = closer. Calibrate the
        constant against your actual camera/lens once mounted."""
        x0, y0, x1, y1 = tdet.box_xyxy
        box_h = max(1.0, y1 - y0)
        return float(np.clip(800.0 / box_h, 3.0, 80.0))
