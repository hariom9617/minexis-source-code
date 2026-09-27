"""
Structured pipeline logger.

Writes one JSON line per processed frame with every stage's key outputs
(sync skew, per-modality quality, fusion weights/agreement, tracks, TTC,
risk state, alert). This is what you'll parse for the doc's section 11-12
experimental plan / ablation study / results table -- without this log,
you can't produce real numbers, only claims.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import FusedObject, Track, RiskAssessment, AlertEvent


class PipelineLogger:
    def __init__(self, log_path: str = "logs/pipeline_log.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.log_path, "a", buffering=1)  # line-buffered

    def log_frame(
        self,
        timestamp: float,
        sync_skew_s: float,
        thermal_quality: float,
        radar_quality: float,
        fused_objects: list[FusedObject],
        tracks: list[Track],
        risks: list[RiskAssessment],
        alerts: list[AlertEvent],
        stage_latencies_ms: dict[str, float],
    ) -> None:
        record = {
            "wall_time": time.time(),
            "timestamp": timestamp,
            "sync_skew_s": sync_skew_s,
            "thermal_quality": thermal_quality,
            "radar_quality": radar_quality,
            "fused_objects": [self._fused_to_dict(f) for f in fused_objects],
            "tracks": [asdict(t) for t in tracks],
            "risks": [asdict(r) for r in risks],
            "alerts": [asdict(a) for a in alerts],
            "stage_latencies_ms": stage_latencies_ms,
        }
        self._fh.write(json.dumps(record, default=str) + "\n")

    @staticmethod
    def _fused_to_dict(f: FusedObject) -> dict:
        d = asdict(f)
        # source_thermal/source_radar are nested dataclasses with enums;
        # asdict handles them, but keep this explicit in case fields change.
        return d

    def close(self) -> None:
        self._fh.close()
