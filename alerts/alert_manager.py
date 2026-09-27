"""
Driver alert generation.

Maps risk assessments to concrete visual/audio/haptic alert events, with
a simple direction hint derived from the track's lateral position. Kept
deliberately simple per the doc's guidance: "keep message simple,
directional and non-distracting."
"""

from __future__ import annotations

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import RiskAssessment, Track, RiskState, AlertEvent


_MESSAGES = {
    RiskState.SAFE: "Clear",
    RiskState.CAUTION: "Object detected ahead",
    RiskState.WARNING: "Warning: object in path",
    RiskState.CRITICAL: "CRITICAL: collision risk",
}


def _direction_hint(track: Track) -> str:
    x, y = track.position_xy
    lateral = "ahead"
    if x < -0.75:
        lateral = "ahead-left"
    elif x > 0.75:
        lateral = "ahead-right"
    return lateral


class AlertManager:
    def __init__(self):
        self._last_states: dict[int, RiskState] = {}

    def generate(
        self,
        assessments: list[RiskAssessment],
        tracks_by_id: dict[int, Track],
        timestamp: float,
    ) -> list[AlertEvent]:
        events = []
        for a in assessments:
            if a.risk_state == RiskState.SAFE:
                self._last_states[a.track_id] = a.risk_state
                continue

            track = tracks_by_id.get(a.track_id)
            direction = _direction_hint(track) if track else None
            ttc_note = f" (TTC {a.ttc_s:.1f}s)" if a.ttc_s is not None else ""

            events.append(
                AlertEvent(
                    timestamp=timestamp,
                    risk_state=a.risk_state,
                    track_id=a.track_id,
                    message=f"{_MESSAGES[a.risk_state]}{ttc_note}",
                    direction_hint=direction,
                )
            )
            self._last_states[a.track_id] = a.risk_state
        return events

    @staticmethod
    def highest_state(assessments: list[RiskAssessment]) -> RiskState:
        order = {RiskState.SAFE: 0, RiskState.CAUTION: 1, RiskState.WARNING: 2, RiskState.CRITICAL: 3}
        if not assessments:
            return RiskState.SAFE
        return max((a.risk_state for a in assessments), key=lambda s: order[s])
