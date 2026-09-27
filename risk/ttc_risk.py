"""
TTC calculation and risk classification.

Implements the doc's section 8 TTC/risk logic and section 9's requirement
for hysteresis so a single noisy frame doesn't flip the alert state.
Thresholds are intentionally centralized in RiskConfig / config/thresholds.yaml
per the doc's warning that these "must be configured from vehicle braking
capability, speed, grade, load and mine safety rules" -- not hardcoded
magic numbers scattered through the code.

100-METER TTC MONITORING ZONE
------------------------------
TTC is only computed when the object is within `ttc_monitoring_distance_m`
(default 100 m). Beyond that distance, TTC remains None and no TTC-based
risk levels are raised. This prevents distant but closing objects from
generating spurious collision warnings.

Within the monitoring zone, TTC is computed only when the radial closing
speed exceeds `min_closing_speed_mps` (a small configurable epsilon that
avoids division by near-zero and filters out stationary / receding objects).
Stationary and receding objects get TTC = None and are not escalated via
TTC-based thresholds. They may still receive a proximity-based CAUTION
via the distance fallback if they are genuinely very close.

Closing speed derivation
------------------------
`track.velocity_xy` is the Kalman-filtered object velocity in the vehicle
frame (x = lateral-right, y = forward), already expressed relative to the
vehicle (radar Doppler accounts for relative motion). The radial closing
speed toward the vehicle origin is:

    closing_speed = -(pos · vel) / ‖pos‖

A positive result means the object is approaching; negative means receding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import Track, RiskAssessment, RiskState


@dataclass
class RiskConfig:
    # Path corridor: how wide (meters, lateral) around dead-ahead counts as "in path"
    path_half_width_m: float = 3.0

    # TTC thresholds (seconds) -- placeholders, MUST be validated against
    # actual vehicle braking distance, speed and mine safety rules before
    # any real deployment.
    ttc_critical_s: float = 3.0
    ttc_warning_s: float = 6.0
    ttc_caution_s: float = 10.0

    # Distance-only fallback thresholds (meters) applied when TTC is not
    # available (stationary/receding/outside monitoring zone objects). These
    # handle the genuine close-proximity danger case without requiring the
    # object to be approaching.
    dist_critical_m: float = 5.0
    dist_warning_m: float = 12.0
    dist_caution_m: float = 25.0

    # --- 100-METER TTC MONITORING ZONE ---
    # Objects farther than this distance are outside the TTC monitoring zone.
    # TTC is not computed for them and they will not generate TTC-based alerts.
    ttc_monitoring_distance_m: float = 100.0

    # Minimum radial closing speed (m/s) required before TTC is computed.
    # This epsilon prevents division by near-zero and suppresses TTC for
    # objects that are essentially stationary or very slowly approaching.
    # Any closing speed at or below this value → TTC = None.
    min_closing_speed_mps: float = 0.1

    # Hysteresis: number of consecutive frames required before escalating
    # or de-escalating the reported risk state, to avoid alert flicker.
    escalate_frames: int = 2
    deescalate_frames: int = 4


@dataclass
class _TrackRiskHistory:
    current_state: RiskState = RiskState.SAFE
    candidate_state: RiskState = RiskState.SAFE
    candidate_count: int = 0


_STATE_ORDER = {
    RiskState.SAFE: 0,
    RiskState.CAUTION: 1,
    RiskState.WARNING: 2,
    RiskState.CRITICAL: 3,
}


class RiskEngine:
    def __init__(
        self,
        config: RiskConfig | None = None,
        ttc_monitoring_distance_m: float | None = None,
    ):
        """
        Parameters
        ----------
        config:
            Full RiskConfig dataclass. If None, defaults are used.
        ttc_monitoring_distance_m:
            Override for the 100 m TTC monitoring zone distance. If provided,
            takes precedence over config.ttc_monitoring_distance_m. Provided
            as a convenience constructor argument so callers can set it
            without constructing a full RiskConfig.
        """
        self.config = config or RiskConfig()

        # Allow explicit constructor override of the monitoring distance
        # so callers don't have to rebuild the whole RiskConfig just for this.
        if ttc_monitoring_distance_m is not None:
            self.config.ttc_monitoring_distance_m = float(ttc_monitoring_distance_m)

        self._history: dict[int, _TrackRiskHistory] = {}

    def assess(self, tracks: list[Track]) -> list[RiskAssessment]:
        results = []
        seen_ids = set()

        for track in tracks:
            seen_ids.add(track.track_id)
            distance = math.hypot(*track.position_xy)
            ttc = self._compute_ttc(track, distance)
            path_overlap = self._path_overlap(track)
            raw_state = self._classify(ttc, distance, path_overlap)
            stable_state = self._apply_hysteresis(track.track_id, raw_state)

            results.append(
                RiskAssessment(
                    track_id=track.track_id,
                    ttc_s=ttc,
                    distance_m=distance,
                    risk_state=stable_state,
                    path_overlap=path_overlap,
                )
            )

        # clean up history for tracks that no longer exist
        stale = [tid for tid in self._history if tid not in seen_ids]
        for tid in stale:
            del self._history[tid]

        return results

    # -- TTC ---------------------------------------------------------------

    def _compute_ttc(self, track: Track, distance: float) -> float | None:
        """
        Compute time-to-collision in seconds, or None when not applicable.

        Returns None when any of the following are true:
          - Object is outside the TTC monitoring zone (distance > monitoring_distance_m)
          - Object is at the vehicle origin (degenerate case)
          - Object is stationary or receding (closing_speed <= min_closing_speed_mps)

        Closing speed formula:
          closing_speed = -(pos · vel) / ‖pos‖

        A positive closing speed means the object is moving toward the vehicle.
        `velocity_xy` in the Track is already in vehicle frame and accounts for
        relative motion (derived from radar Doppler), so no own-vehicle velocity
        subtraction is needed.
        """
        cfg = self.config

        # Gate 1: Only monitor objects within the configured distance.
        # Objects beyond the monitoring zone do not get a TTC value, so
        # they cannot trigger TTC-based CAUTION / WARNING / CRITICAL alerts.
        if distance > cfg.ttc_monitoring_distance_m:
            return None

        # Gate 2: Degenerate case — object is essentially at the vehicle origin.
        if distance < 1e-3:
            return 0.0

        x, y = track.position_xy
        vx, vy = track.velocity_xy

        # Radial closing speed: positive = approaching, negative = receding.
        # Formula: d(distance)/dt = (pos · vel) / distance
        # closing_speed = -d(distance)/dt = -(pos · vel) / distance
        closing_speed = -((x * vx + y * vy) / distance)

        # Gate 3: Object is stationary or moving away.
        # Use a configurable epsilon to avoid division by near-zero and to
        # suppress TTC for objects that are not meaningfully approaching.
        if closing_speed <= cfg.min_closing_speed_mps:
            return None

        return float(distance / closing_speed)

    # -- path overlap --------------------------------------------------------

    def _path_overlap(self, track: Track) -> float:
        """0-1: how directly the object's lateral position sits in the
        vehicle's forward driving corridor. 1.0 = dead ahead, 0 = far to
        the side."""
        x, _y = track.position_xy
        lateral = abs(x)
        overlap = 1.0 - min(1.0, lateral / max(self.config.path_half_width_m, 0.1))
        return max(0.0, overlap)

    # -- classification -------------------------------------------------------

    def _classify(self, ttc: float | None, distance: float, path_overlap: float) -> RiskState:
        """
        Classify risk state based on TTC, distance, and path overlap.

        Priority order:
          1. TTC-based classification (only when object is inside monitoring
             zone AND actively approaching — guaranteed by _compute_ttc returning
             a non-None value only for those cases).
          2. Distance-based proximity fallback for objects that are close but
             stationary/receding/outside the monitoring zone. Capped at WARNING
             (not CRITICAL) to avoid false critical alerts for stationary objects.
        """
        cfg = self.config
        in_corridor = path_overlap > 0.3  # loosely "on or near predicted path"

        # --- TTC-based classification ---
        # ttc is not None only when the object is:
        #   (a) inside the ttc_monitoring_distance_m zone, AND
        #   (b) actively approaching (closing_speed > min_closing_speed_mps)
        # So this block never fires for distant, stationary, or receding objects.
        if ttc is not None and in_corridor:
            if ttc <= cfg.ttc_critical_s:
                return RiskState.CRITICAL
            if ttc <= cfg.ttc_warning_s:
                return RiskState.WARNING
            if ttc <= cfg.ttc_caution_s:
                return RiskState.CAUTION
            return RiskState.SAFE

        # --- Distance-based proximity fallback ---
        # Applied when TTC is unavailable (stationary, receding, or outside
        # monitoring zone). Per doc: "don't ignore a nearby object just because
        # velocity is noisy/unavailable, but don't treat it as imminent either."
        # Capped at WARNING (not CRITICAL) since we cannot confirm approach intent.
        if distance <= cfg.dist_critical_m and in_corridor:
            return RiskState.WARNING   # close + in-path, but not confirmed approaching
        if distance <= cfg.dist_warning_m and in_corridor:
            return RiskState.CAUTION
        if distance <= cfg.dist_caution_m and path_overlap > 0.1:
            return RiskState.CAUTION
        return RiskState.SAFE

    # -- hysteresis -------------------------------------------------------------

    def _apply_hysteresis(self, track_id: int, raw_state: RiskState) -> RiskState:
        cfg = self.config
        hist = self._history.setdefault(track_id, _TrackRiskHistory())

        if raw_state == hist.current_state:
            hist.candidate_state = raw_state
            hist.candidate_count = 0
            return hist.current_state

        if raw_state != hist.candidate_state:
            hist.candidate_state = raw_state
            hist.candidate_count = 1
        else:
            hist.candidate_count += 1

        escalating = _STATE_ORDER[raw_state] > _STATE_ORDER[hist.current_state]
        required = cfg.escalate_frames if escalating else cfg.deescalate_frames

        if hist.candidate_count >= required:
            hist.current_state = raw_state
            hist.candidate_count = 0

        return hist.current_state
