"""
Radar processing pipeline.

Implements the steps from the doc's section 5:
  CFAR detection -> clutter suppression -> multipath mitigation ->
  point clustering -> feature output.

Working on RadarReturn lists (already past ADC/range-Doppler, which for a
real radar SDK is normally handled by vendor firmware and delivered as
detections/point clouds -- consistent with the doc's "Input acquisition"
note).
"""

from __future__ import annotations

import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import RadarScan, RadarReturn, RadarCluster, RadarPerceptionOutput


class RadarBranch:
    def __init__(
        self,
        snr_threshold_db: float = 10.0,       # CFAR-style: reject weak returns
        doppler_static_thresh: float = 0.4,   # m/s, below this = likely clutter
        cluster_eps_range_m: float = 2.5,     # DBSCAN-like clustering radius (range)
        cluster_eps_azimuth_deg: float = 4.0,
        min_cluster_points: int = 1,
        persistence_history: int = 5,
    ):
        self.snr_threshold_db = snr_threshold_db
        self.doppler_static_thresh = doppler_static_thresh
        self.cluster_eps_range_m = cluster_eps_range_m
        self.cluster_eps_azimuth_deg = cluster_eps_azimuth_deg
        self.min_cluster_points = min_cluster_points

        # Track approximate (range, azimuth) of recent cluster centers to
        # estimate persistence -- a simple stand-in for the doc's
        # "repeated spatially plausible returns" temporal-consistency check.
        self._recent_centers: list[list[tuple[float, float]]] = []
        self._persistence_history = persistence_history

    # -- stage 1: CFAR-style detection -------------------------------------
    def _cfar_filter(self, returns: list[RadarReturn]) -> list[RadarReturn]:
        """Keep only returns whose SNR clears the (constant) threshold.

        A real CFAR implementation computes a local, adaptive noise floor
        per range-Doppler cell. This constant-threshold version is the
        documented simplification for a first working prototype; swap in
        adaptive CFAR (CA-CFAR/OS-CFAR) once real range-Doppler maps are
        available from the radar SDK.
        """
        return [r for r in returns if r.snr_db >= self.snr_threshold_db]

    # -- stage 2: clutter suppression ---------------------------------------
    def _suppress_clutter(self, returns: list[RadarReturn]) -> list[RadarReturn]:
        """Drop near-zero-Doppler returns (static clutter) while keeping
        anything with meaningful radial velocity -- moving hazards."""
        return [r for r in returns if abs(r.doppler_mps) >= self.doppler_static_thresh]

    # -- stage 3: multipath / consistency mitigation -------------------------
    def _mitigate_multipath(self, returns: list[RadarReturn]) -> list[RadarReturn]:
        """Reject returns with implausible range/Doppler combinations.

        Heuristic prototype check: a return whose Doppler direction
        disagrees strongly with what's plausible for its RCS/SNR
        profile (e.g. very high closing speed but very weak, noisy
        signal) is more likely a multipath ghost than a real hazard.
        Down-weight rather than hard-delete when uncertain -- keep as a
        low-confidence cluster instead of silently dropping it, per the
        doc's "cautious rather than dropping the hazard" guidance.
        """
        kept = []
        for r in returns:
            implausible = abs(r.doppler_mps) > 15.0 and r.snr_db < 12.0
            if not implausible:
                kept.append(r)
        return kept

    # -- stage 4: clustering -------------------------------------------------
    def _cluster(self, returns: list[RadarReturn]) -> list[RadarCluster]:
        """Simple greedy clustering by (range, azimuth) proximity.

        This is a lightweight stand-in for DBSCAN, sufficient for a
        prototype with modest point counts. Swap for sklearn.cluster.DBSCAN
        directly on (range, azimuth, elevation) if point density grows.
        """
        unclustered = list(returns)
        clusters: list[list[RadarReturn]] = []

        while unclustered:
            seed = unclustered.pop(0)
            group = [seed]
            remaining = []
            for r in unclustered:
                close_range = abs(r.range_m - seed.range_m) <= self.cluster_eps_range_m
                close_az = abs(r.azimuth_deg - seed.azimuth_deg) <= self.cluster_eps_azimuth_deg
                if close_range and close_az:
                    group.append(r)
                else:
                    remaining.append(r)
            clusters.append(group)
            unclustered = remaining

        results = []
        for group in clusters:
            if len(group) < self.min_cluster_points:
                continue
            ranges = np.array([g.range_m for g in group])
            azs = np.array([g.azimuth_deg for g in group])
            els = np.array([g.elevation_deg for g in group])
            dops = np.array([g.doppler_mps for g in group])
            rcs = np.array([g.rcs_dbsm for g in group])
            snrs = np.array([g.snr_db for g in group])

            center = (float(ranges.mean()), float(azs.mean()))
            persistence = self._estimate_persistence(center)

            results.append(
                RadarCluster(
                    range_m=float(ranges.mean()),
                    azimuth_deg=float(azs.mean()),
                    elevation_deg=float(els.mean()),
                    doppler_mps=float(dops.mean()),
                    rcs_dbsm=float(rcs.mean()),
                    snr_db=float(snrs.mean()),
                    point_count=len(group),
                    persistence=persistence,
                )
            )
        return results

    def _estimate_persistence(self, center: tuple[float, float]) -> float:
        """Fraction of recent scans that had a cluster near this location."""
        if not self._recent_centers:
            return 0.0
        hits = 0
        for scan_centers in self._recent_centers:
            for c in scan_centers:
                if abs(c[0] - center[0]) <= self.cluster_eps_range_m * 1.5 and \
                   abs(c[1] - center[1]) <= self.cluster_eps_azimuth_deg * 1.5:
                    hits += 1
                    break
        return hits / len(self._recent_centers)

    def _update_history(self, clusters: list[RadarCluster]) -> None:
        centers = [(c.range_m, c.azimuth_deg) for c in clusters]
        self._recent_centers.append(centers)
        if len(self._recent_centers) > self._persistence_history:
            self._recent_centers.pop(0)

    # -- public entry point ---------------------------------------------------
    def process(self, scan: RadarScan) -> RadarPerceptionOutput:
        stage1 = self._cfar_filter(scan.returns)
        stage2 = self._suppress_clutter(stage1)
        stage3 = self._mitigate_multipath(stage2)
        clusters = self._cluster(stage3)
        self._update_history(clusters)

        health_ok = scan.meta.get("health_ok", True)
        n_raw = max(len(scan.returns), 1)
        signal_ratio = len(stage3) / n_raw
        scan_quality = float(np.clip(signal_ratio * (1.0 if health_ok else 0.3), 0.0, 1.0))

        return RadarPerceptionOutput(
            timestamp=scan.timestamp,
            clusters=clusters,
            scan_quality=scan_quality,
        )
