"""
Multi-object tracking.

Implements the doc's section 8: constant-velocity Kalman filter per
track, Hungarian algorithm for detection-to-track association, giving
each object a stable ID and a smoothed position/velocity estimate across
frames -- which is what makes TTC meaningful (a single noisy frame isn't
enough to estimate closing speed reliably).

Uses scipy.optimize.linear_sum_assignment for the Hungarian algorithm and
a hand-rolled constant-velocity Kalman filter (no filterpy dependency
needed for a 4-state CV model).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import FusedObject, Track, ObjectClass


class _KalmanCV:
    """Constant-velocity Kalman filter, state = [x, y, vx, vy]."""

    def __init__(self, x0: float, y0: float, vx0: float = 0.0, vy0: float = 0.0):
        self.x = np.array([x0, y0, vx0, vy0], dtype=np.float64)
        self.P = np.eye(4) * 5.0

        # process noise: allow some acceleration uncertainty
        self.Q = np.diag([0.05, 0.05, 0.5, 0.5])
        # measurement noise: position-only observations (radar/thermal fused position)
        self.R = np.diag([0.5, 0.5])
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float64)

    def predict(self, dt: float) -> None:
        F = np.array(
            [
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ]
        )
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q

    def update(self, z: np.ndarray) -> None:
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

    @property
    def position(self) -> tuple[float, float]:
        return (float(self.x[0]), float(self.x[1]))

    @property
    def velocity(self) -> tuple[float, float]:
        return (float(self.x[2]), float(self.x[3]))


class _TrackState:
    def __init__(self, track_id: int, obj: FusedObject):
        self.track_id = track_id
        self.kf = _KalmanCV(obj.position_xy[0], obj.position_xy[1], *obj.velocity_xy)
        self.cls = obj.cls
        self.confidence = obj.confidence
        self.age_frames = 1
        self.missed_frames = 0
        self.history: list[tuple[float, float]] = [obj.position_xy]

    def to_track(self) -> Track:
        return Track(
            track_id=self.track_id,
            position_xy=self.kf.position,
            velocity_xy=self.kf.velocity,
            cls=self.cls,
            confidence=self.confidence,
            age_frames=self.age_frames,
            missed_frames=self.missed_frames,
            history=list(self.history[-20:]),
        )


class Tracker:
    def __init__(
        self,
        max_association_dist_m: float = 5.0,
        max_missed_frames: int = 5,
        min_hits_to_confirm: int = 2,
    ):
        self.max_association_dist_m = max_association_dist_m
        self.max_missed_frames = max_missed_frames
        self.min_hits_to_confirm = min_hits_to_confirm
        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 1
        self._last_timestamp: float | None = None

    def update(self, detections: list[FusedObject], timestamp: float) -> list[Track]:
        dt = 0.1 if self._last_timestamp is None else max(1e-3, timestamp - self._last_timestamp)
        self._last_timestamp = timestamp

        for t in self._tracks.values():
            t.kf.predict(dt)

        track_ids = list(self._tracks.keys())
        if track_ids and detections:
            cost = np.zeros((len(track_ids), len(detections)))
            for i, tid in enumerate(track_ids):
                tx, ty = self._tracks[tid].kf.position
                for j, det in enumerate(detections):
                    dx, dy = det.position_xy
                    cost[i, j] = np.hypot(tx - dx, ty - dy)

            row_idx, col_idx = linear_sum_assignment(cost)
            matched_tracks: set[int] = set()
            matched_dets: set[int] = set()

            for r, c in zip(row_idx, col_idx):
                if cost[r, c] <= self.max_association_dist_m:
                    tid = track_ids[r]
                    det = detections[c]
                    self._tracks[tid].kf.update(np.array(det.position_xy))
                    self._tracks[tid].confidence = det.confidence
                    self._tracks[tid].cls = det.cls
                    self._tracks[tid].age_frames += 1
                    self._tracks[tid].missed_frames = 0
                    self._tracks[tid].history.append(det.position_xy)
                    matched_tracks.add(tid)
                    matched_dets.add(c)

            for tid in track_ids:
                if tid not in matched_tracks:
                    self._tracks[tid].missed_frames += 1

            for j, det in enumerate(detections):
                if j not in matched_dets:
                    self._spawn_track(det)

        elif detections:
            for det in detections:
                self._spawn_track(det)
        else:
            for t in self._tracks.values():
                t.missed_frames += 1

        # prune stale tracks
        self._tracks = {
            tid: t for tid, t in self._tracks.items() if t.missed_frames <= self.max_missed_frames
        }

        # only report tracks that have been confirmed (reduces spurious
        # single-frame noise from becoming a driver-facing alert)
        return [
            t.to_track() for t in self._tracks.values() if t.age_frames >= self.min_hits_to_confirm
        ]

    def _spawn_track(self, det: FusedObject) -> None:
        tid = self._next_id
        self._next_id += 1
        self._tracks[tid] = _TrackState(tid, det)
