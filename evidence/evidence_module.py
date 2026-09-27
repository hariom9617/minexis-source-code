"""
Evidence-aware reliability scoring.

Implements the doc's section 7 evidence-sufficiency table: reliability is
computed from quality + model-output confidence + temporal consistency
per modality, separately from raw detector confidence. This is the
module that lets adaptive fusion say "trust radar more this frame because
thermal contrast collapsed," instead of always doing a fixed 50/50 blend.
"""

from __future__ import annotations

import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import (
    ThermalDetection,
    ThermalPerceptionOutput,
    RadarCluster,
    RadarPerceptionOutput,
    ModalityReliability,
)


def thermal_reliability(
    detection: ThermalDetection,
    frame_quality: float,
) -> ModalityReliability:
    """
    Combine detector confidence with image quality and box plausibility.
    A high-confidence detection on a low-quality (foggy/washed-out) frame
    should NOT be treated as fully reliable -- this is the doc's point
    that "a thermal network can output a high score even when the image
    is nearly featureless."
    """
    conf = detection.confidence
    quality = detection.image_quality if detection.image_quality else frame_quality

    # Box-size plausibility: extremely tiny boxes are noisier estimates.
    x0, y0, x1, y1 = detection.box_xyxy
    box_area = max(1.0, (x1 - x0) * (y1 - y0))
    size_conf = float(np.clip(box_area / 150.0, 0.2, 1.0))  # saturates for reasonably sized boxes

    reliability = float(np.clip(0.45 * conf + 0.4 * quality + 0.15 * size_conf, 0.0, 1.0))
    uncertainty = float(np.clip(1.0 - reliability, 0.0, 1.0))
    health_ok = quality > 0.15  # near-zero quality implies a degraded/blocked sensor

    return ModalityReliability(reliability=reliability, uncertainty=uncertainty, health_ok=health_ok)


def radar_reliability(
    cluster: RadarCluster,
    scan_quality: float,
) -> ModalityReliability:
    """
    Combine SNR, cluster point density, and temporal persistence.
    A strong-but-brand-new (never seen before) cluster is more likely a
    transient multipath ghost than a real, persistent hazard, so
    persistence matters as much as instantaneous signal strength.
    """
    snr_conf = float(np.clip((cluster.snr_db - 8.0) / 15.0, 0.0, 1.0))
    density_conf = float(np.clip(cluster.point_count / 4.0, 0.0, 1.0))
    persistence_conf = cluster.persistence  # already 0-1

    reliability = float(
        np.clip(
            0.35 * snr_conf + 0.2 * density_conf + 0.25 * persistence_conf + 0.2 * scan_quality,
            0.0,
            1.0,
        )
    )
    uncertainty = float(np.clip(1.0 - reliability, 0.0, 1.0))
    health_ok = scan_quality > 0.15

    return ModalityReliability(reliability=reliability, uncertainty=uncertainty, health_ok=health_ok)


def estimate_environmental_severity(
    thermal_output: ThermalPerceptionOutput,
    radar_output: RadarPerceptionOutput,
) -> float:
    """
    0 (clear) - 1 (severe fog/dust) estimate from available quality
    signals across both modalities, per the doc's instruction to not
    depend on a single contrast value.
    """
    thermal_signal = thermal_output.frame_quality
    radar_signal = radar_output.scan_quality
    combined_quality = 0.5 * thermal_signal + 0.5 * radar_signal
    severity = float(np.clip(1.0 - combined_quality, 0.0, 1.0))
    return severity
