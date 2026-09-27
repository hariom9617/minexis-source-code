"""
Tests for the MINEXIS FastAPI backend.

Strategy
--------
- We use FastAPI's built-in TestClient (httpx-backed) for REST endpoints.
- For WebSocket tests we use the same TestClient in context-manager mode,
  which spins up the full lifespan (startup + shutdown) so the real
  Pipeline worker runs.
- A small FakePipeline is injected where we need deterministic, fast
  behaviour (e.g. confirming payload shape without waiting for the
  synthetic sensors to sync).
- For tests that exercise the REAL pipeline (e.g. "receives a live frame"),
  we drive the actual Pipeline with synthetic sources and a short timeout.

Run:
    python -m pytest tests/test_backend.py -v
  or:
    python tests/test_backend.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import threading
from typing import Optional
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure minexis root is on sys.path
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# FakePipeline — deterministic stand-in for fast / isolated tests
# ---------------------------------------------------------------------------

from common.types import (
    RiskState, ObjectClass, AgreementState,
    ThermalDetection, RadarCluster, FusedObject,
    Track, RiskAssessment, AlertEvent,
)
from pipeline import FrameResult


def _make_fake_frame(n: int = 1) -> FrameResult:
    """Return a minimal but structurally complete FrameResult."""
    return FrameResult(
        timestamp=float(n) * 0.1,
        frame_number=n,
        sync_skew_s=0.005,
        thermal_quality=0.75,
        radar_quality=0.60,
        thermal_detections=[
            ThermalDetection(
                box_xyxy=(100.0, 80.0, 140.0, 130.0),
                cls=ObjectClass.PERSON,
                confidence=0.85,
                image_quality=0.75,
            )
        ],
        radar_clusters=[
            RadarCluster(
                range_m=30.0,
                azimuth_deg=1.5,
                elevation_deg=0.0,
                doppler_mps=3.2,
                rcs_dbsm=8.0,
                snr_db=18.0,
                point_count=2,
                persistence=0.6,
            )
        ],
        fused_objects=[
            FusedObject(
                timestamp=float(n) * 0.1,
                position_xy=(0.8, 29.9),
                velocity_xy=(-0.09, -3.2),
                cls=ObjectClass.PERSON,
                confidence=0.72,
                thermal_weight=0.55,
                radar_weight=0.45,
                agreement=AgreementState.AGREEMENT,
                source_thermal=None,
                source_radar=None,
            )
        ],
        tracks=[
            Track(
                track_id=1,
                position_xy=(0.8, 29.9),
                velocity_xy=(-0.09, -3.2),
                cls=ObjectClass.PERSON,
                confidence=0.72,
                age_frames=n,
                missed_frames=0,
                history=[(0.8, 30.0 - i * 0.32) for i in range(min(n, 5))],
            )
        ],
        risks=[
            RiskAssessment(
                track_id=1,
                ttc_s=9.3,
                distance_m=29.9,
                risk_state=RiskState.CAUTION,
                path_overlap=0.73,
            )
        ],
        alerts=[
            AlertEvent(
                timestamp=float(n) * 0.1,
                risk_state=RiskState.CAUTION,
                track_id=1,
                message="Object detected ahead",
                direction_hint="ahead",
            )
        ],
        highest_risk=RiskState.CAUTION,
        latency={
            "perception": 1.2,
            "fusion": 0.3,
            "tracking": 0.1,
            "risk": 0.05,
            "alerts": 0.02,
            "total": 1.67,
        },
    )


class FakePipeline:
    """
    Deterministic pipeline that returns pre-built FrameResult objects.
    After ``max_frames`` results it keeps returning None so the worker
    loop doesn't spin at 100 % CPU in tests.
    """

    def __init__(self, max_frames: int = 5, step_delay_s: float = 0.01):
        self._n = 0
        self._max = max_frames
        self._delay = step_delay_s
        self.closed = False

    def step(self) -> Optional[FrameResult]:
        time.sleep(self._delay)
        if self._n >= self._max:
            time.sleep(0.02)   # idle so the worker doesn't spin
            return None
        self._n += 1
        return _make_fake_frame(self._n)

    def close(self) -> None:
        self.closed = True

    @property
    def frame_count(self) -> int:
        return self._n

    @property
    def fog_severity(self) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# Helpers to build a TestClient using a FakePipeline
# ---------------------------------------------------------------------------

def _make_test_client(fake_pipeline: Optional[FakePipeline] = None) -> TestClient:
    """
    Return an httpx TestClient with the backend app, optionally injecting a
    FakePipeline so tests do not depend on real sensor timing.
    """
    # Import here so the module-level ``app`` and ``_state`` objects are
    # accessible for patching.
    import backend.app as backend_app

    if fake_pipeline is not None:
        # Patch Pipeline() constructor to return our fake.
        # We need to patch it where the app module looks it up.
        with patch.object(backend_app, "Pipeline", return_value=fake_pipeline):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
    else:
        client = TestClient(backend_app.app, raise_server_exceptions=False)

    return client


# ---------------------------------------------------------------------------
# Import test
# ---------------------------------------------------------------------------

def test_backend_app_imports():
    """The backend module must import without error."""
    import backend.app  # noqa: F401
    from backend.app import app
    assert app is not None


def test_schemas_import():
    from backend.schemas import HealthResponse, StatusResponse
    h = HealthResponse(status="ok", service="test")
    assert h.status == "ok"


# ---------------------------------------------------------------------------
# REST: /health
# ---------------------------------------------------------------------------

def test_health_endpoint():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "MINEXIS backend"


# ---------------------------------------------------------------------------
# REST: /api/status
# ---------------------------------------------------------------------------

def test_status_endpoint_returns_valid_shape():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "running" in body
    assert "frame_number" in body
    assert "highest_risk" in body
    assert "last_timestamp" in body
    assert "connected_clients" in body
    assert isinstance(body["running"], bool)
    assert isinstance(body["frame_number"], int)
    assert isinstance(body["highest_risk"], str)


def test_status_highest_risk_is_valid_state():
    import backend.app as backend_app
    fake = FakePipeline(max_frames=3)
    valid = {"safe", "caution", "warning", "critical"}
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            # Give the worker a moment to process a few frames.
            time.sleep(0.15)
            resp = client.get("/api/status")
    assert resp.json()["highest_risk"] in valid


# ---------------------------------------------------------------------------
# WebSocket: connection accepted
# ---------------------------------------------------------------------------

def test_websocket_accepts_connection():
    import backend.app as backend_app
    fake = FakePipeline(max_frames=10)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                # connection accepted — no exception means success
                assert ws is not None


# ---------------------------------------------------------------------------
# WebSocket: receives at least one valid JSON frame
# ---------------------------------------------------------------------------

_REQUIRED_PAYLOAD_KEYS = {
    "frame_number",
    "timestamp",
    "thermal_quality",
    "radar_quality",
    "fused_objects",
    "tracks",
    "risks",
    "alerts",
    "highest_risk",
    "latency",
}


def test_websocket_receives_frame_payload():
    """
    Connect to /ws/live, wait for the first non-ping message, and verify
    the payload contains all required keys.
    """
    import backend.app as backend_app
    fake = FakePipeline(max_frames=20, step_delay_s=0.005)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                deadline = time.monotonic() + 5.0   # up to 5 s to get a frame
                payload = None
                while time.monotonic() < deadline:
                    try:
                        raw = ws.receive_text()
                        msg = json.loads(raw)
                        if msg.get("type") == "ping":
                            continue
                        payload = msg
                        break
                    except Exception:
                        break

    assert payload is not None, "Did not receive a frame payload within 5 s"
    missing = _REQUIRED_PAYLOAD_KEYS - payload.keys()
    assert not missing, f"Payload missing keys: {missing}"


def test_websocket_payload_key_types():
    """Verify types of the key fields in the first received frame."""
    import backend.app as backend_app
    fake = FakePipeline(max_frames=20, step_delay_s=0.005)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                deadline = time.monotonic() + 5.0
                payload = None
                while time.monotonic() < deadline:
                    raw = ws.receive_text()
                    msg = json.loads(raw)
                    if msg.get("type") == "ping":
                        continue
                    payload = msg
                    break

    assert payload is not None
    assert isinstance(payload["frame_number"], int)
    assert isinstance(payload["timestamp"], float)
    assert isinstance(payload["thermal_quality"], float)
    assert isinstance(payload["radar_quality"], float)
    assert isinstance(payload["highest_risk"], str)
    assert payload["highest_risk"] in {"safe", "caution", "warning", "critical"}
    assert isinstance(payload["fused_objects"], list)
    assert isinstance(payload["tracks"], list)
    assert isinstance(payload["risks"], list)
    assert isinstance(payload["alerts"], list)
    assert isinstance(payload["latency"], dict)


def test_websocket_payload_is_json_serializable():
    """The payload received over the wire must round-trip through json.loads."""
    import backend.app as backend_app
    fake = FakePipeline(max_frames=20, step_delay_s=0.005)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                deadline = time.monotonic() + 5.0
                payload = None
                while time.monotonic() < deadline:
                    raw = ws.receive_text()
                    msg = json.loads(raw)
                    if msg.get("type") == "ping":
                        continue
                    payload = msg
                    break

    assert payload is not None
    # Re-serialize — must not raise
    re_serialized = json.dumps(payload)
    assert len(re_serialized) > 0


def test_websocket_multiple_frames_received():
    """Verify that frame_number increments across successive payloads."""
    import backend.app as backend_app
    fake = FakePipeline(max_frames=20, step_delay_s=0.005)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                frames = []
                deadline = time.monotonic() + 5.0
                while len(frames) < 3 and time.monotonic() < deadline:
                    raw = ws.receive_text()
                    msg = json.loads(raw)
                    if msg.get("type") == "ping":
                        continue
                    frames.append(msg)

    assert len(frames) >= 2, f"Expected at least 2 frames, got {len(frames)}"
    # frame_numbers should be strictly increasing
    nums = [f["frame_number"] for f in frames]
    assert nums == sorted(nums), f"frame_numbers not increasing: {nums}"
    assert len(set(nums)) == len(nums), f"Duplicate frame_numbers: {nums}"


# ---------------------------------------------------------------------------
# WebSocket: multiple clients
# ---------------------------------------------------------------------------

def test_multiple_clients_connect_simultaneously():
    """
    Two WebSocket clients can connect simultaneously without crashing the
    pipeline or each other.
    """
    import backend.app as backend_app
    fake = FakePipeline(max_frames=30, step_delay_s=0.005)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws1:
                with client.websocket_connect("/ws/live") as ws2:
                    # Both clients should receive at least one frame.
                    got1, got2 = False, False
                    deadline = time.monotonic() + 5.0
                    while (not got1 or not got2) and time.monotonic() < deadline:
                        if not got1:
                            try:
                                raw = ws1.receive_text()
                                msg = json.loads(raw)
                                if msg.get("type") != "ping":
                                    got1 = True
                            except Exception:
                                pass
                        if not got2:
                            try:
                                raw = ws2.receive_text()
                                msg = json.loads(raw)
                                if msg.get("type") != "ping":
                                    got2 = True
                            except Exception:
                                pass

    assert got1, "Client 1 did not receive a frame"
    assert got2, "Client 2 did not receive a frame"


# ---------------------------------------------------------------------------
# Lifecycle / shutdown
# ---------------------------------------------------------------------------

def test_startup_and_shutdown_do_not_hang():
    """
    The TestClient context manager covers the full lifespan cycle.
    If startup or shutdown hangs, this test will time out.
    """
    import backend.app as backend_app
    fake = FakePipeline(max_frames=3)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
    # reaching here means shutdown completed without hanging


def test_pipeline_close_called_on_shutdown():
    """Pipeline.close() must be called during server shutdown."""
    import backend.app as backend_app
    fake = FakePipeline(max_frames=2)
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app):
            pass  # enter + exit triggers full lifespan

    assert fake.closed, "FakePipeline.close() was not called on shutdown"


# ---------------------------------------------------------------------------
# Real pipeline smoke test (no mocking)
# ---------------------------------------------------------------------------

def test_real_pipeline_streams_frame():
    """
    End-to-end: use the real Pipeline (synthetic sources) and confirm that
    at least one valid FrameResult is received over the WebSocket within a
    reasonable timeout.
    """
    import backend.app as backend_app

    with TestClient(backend_app.app) as client:
        with client.websocket_connect("/ws/live") as ws:
            deadline = time.monotonic() + 10.0  # real sensors need a moment to sync
            payload = None
            while time.monotonic() < deadline:
                try:
                    raw = ws.receive_text()
                    msg = json.loads(raw)
                    if msg.get("type") == "ping":
                        continue
                    payload = msg
                    break
                except Exception:
                    break

    assert payload is not None, "Did not receive a real pipeline frame within 10 s"
    missing = _REQUIRED_PAYLOAD_KEYS - payload.keys()
    assert not missing, f"Real pipeline payload missing keys: {missing}"


# ---------------------------------------------------------------------------
# Direct runner (mirrors test_pipeline.py pattern)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import inspect
    import traceback

    current_module = sys.modules[__name__]
    test_fns = [
        f
        for name, f in inspect.getmembers(current_module, inspect.isfunction)
        if name.startswith("test_")
    ]
    passed, failed = 0, 0
    for fn in test_fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
