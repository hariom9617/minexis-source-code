"""
Serialization helpers for converting MINEXIS pipeline outputs to
JSON-safe Python dictionaries suitable for WebSocket/REST responses.

Rules:
- Raw sensor images (ThermalFrame.image numpy arrays) are NOT included.
- All numpy scalar types are converted to native Python floats/ints.
- All Enum values are converted to their string representations.
- Nested dataclasses are converted recursively via dataclasses.asdict().
- The result contains only plain Python primitives (str, int, float,
  bool, list, dict, None) and is safe to pass to json.dumps().
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

import numpy as np

# FrameResult imported lazily inside frame_result_to_dict to avoid a
# circular import if this module is ever imported from pipeline.py.


def _sanitize(value: Any) -> Any:
    """
    Recursively convert a value produced by dataclasses.asdict() into
    JSON-safe Python primitives.

    - numpy scalars  -> float or int
    - numpy arrays   -> list (should not appear after excluding image fields)
    - Enum instances -> their .value string
    - tuples         -> lists (JSON has no tuples)
    - dicts/lists    -> recurse
    - everything else -> unchanged
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    if isinstance(value, np.ndarray):
        # Should only happen for non-image arrays (e.g. small numeric arrays).
        # Images are excluded at the FrameResult level, not here.
        return value.tolist()
    if isinstance(value, tuple):
        return [_sanitize(v) for v in value]
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    return value


def _fused_object_to_dict(obj: Any) -> dict:
    """
    Convert a FusedObject to a dict, excluding the nested ThermalDetection
    and RadarCluster source references (they duplicate data already
    present in thermal_detections/radar_clusters) to keep payloads small.
    """
    d = dataclasses.asdict(obj)
    # Remove the nested source objects -- they contain image-space coords
    # that are redundant when the client already has the detection list.
    d.pop("source_thermal", None)
    d.pop("source_radar", None)
    return _sanitize(d)


def frame_result_to_dict(result: Any) -> dict:
    """
    Convert a ``FrameResult`` into a JSON-safe dictionary.

    Excludes raw numpy image arrays.  All enum values become strings.
    All numpy scalars become native Python floats/ints.

    Parameters
    ----------
    result:
        A ``FrameResult`` instance from ``Pipeline.step()``.

    Returns
    -------
    dict
        A plain Python dict safe for ``json.dumps()`` or WebSocket send.
    """
    return {
        "timestamp":          float(result.timestamp),
        "frame_number":       int(result.frame_number),
        "sync_skew_s":        float(result.sync_skew_s),
        "thermal_quality":    float(result.thermal_quality),
        "radar_quality":      float(result.radar_quality),
        "highest_risk":       result.highest_risk.value,      # str
        "scenario":           str(getattr(result, "scenario", "DEFAULT")),
        "latency":            {k: float(v) for k, v in result.latency.items()},

        # -- perception outputs -----------------------------------------------
        "thermal_detections": [
            _sanitize(dataclasses.asdict(d)) for d in result.thermal_detections
        ],
        "radar_clusters": [
            _sanitize(dataclasses.asdict(c)) for c in result.radar_clusters
        ],

        # -- fusion -----------------------------------------------------------
        "fused_objects": [
            _fused_object_to_dict(f) for f in result.fused_objects
        ],

        # -- tracking ---------------------------------------------------------
        "tracks": [
            _sanitize(dataclasses.asdict(t)) for t in result.tracks
        ],

        # -- risk / alerts ----------------------------------------------------
        "risks": [
            _sanitize(dataclasses.asdict(r)) for r in result.risks
        ],
        "alerts": [
            _sanitize(dataclasses.asdict(a)) for a in result.alerts
        ],
    }
