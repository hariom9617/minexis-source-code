"""
Sensor synchronization.

Buffers the most recent thermal frame and radar scan and pairs them when
their timestamps are close enough. This is the module the doc calls out
as essential: "a fast-moving vehicle seen by two unsynchronized sensors
can appear in different locations."

Design: simple latest-value buffering with a max staleness gate. This is
enough for a prototype; a production system would want interpolation or
a proper synchronized capture trigger at the hardware level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import ThermalFrame, RadarScan


@dataclass
class SyncedPair:
    timestamp: float           # midpoint timestamp of the pair
    thermal: ThermalFrame
    radar: RadarScan
    time_skew_s: float         # |thermal.timestamp - radar.timestamp|


class Synchronizer:
    def __init__(self, max_skew_s: float = 0.08, max_staleness_s: float = 0.5):
        """
        max_skew_s: maximum allowed timestamp difference between a thermal
            frame and radar scan for them to be considered a valid pair.
        max_staleness_s: if a buffered frame/scan is older than this
            relative to "now", discard it rather than pairing it.
        """
        self.max_skew_s = max_skew_s
        self.max_staleness_s = max_staleness_s
        self._last_thermal: Optional[ThermalFrame] = None
        self._last_radar: Optional[RadarScan] = None
        self.rejected_count = 0
        self.paired_count = 0

    def push_thermal(self, frame: ThermalFrame) -> None:
        self._last_thermal = frame

    def push_radar(self, scan: RadarScan) -> None:
        self._last_radar = scan

    def try_pair(self, now: float) -> Optional[SyncedPair]:
        """Attempt to produce a synced pair from the latest buffered data."""
        t, r = self._last_thermal, self._last_radar
        if t is None or r is None:
            return None

        if (now - t.timestamp) > self.max_staleness_s:
            return None
        if (now - r.timestamp) > self.max_staleness_s:
            return None

        skew = abs(t.timestamp - r.timestamp)
        if skew > self.max_skew_s:
            self.rejected_count += 1
            return None

        self.paired_count += 1
        return SyncedPair(
            timestamp=(t.timestamp + r.timestamp) / 2.0,
            thermal=t,
            radar=r,
            time_skew_s=skew,
        )
