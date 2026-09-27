"""
Backend demo/scenario API tests.

Tests:
- GET /api/scenarios returns all scenarios + current
- POST /api/scenario switches scenario (valid)
- POST /api/scenario returns HTTP 400 for invalid name
- GET /api/status includes 'scenario' field
- WebSocket frame payload includes 'scenario' field
- Scenario change is reflected in subsequent frames
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional
from unittest.mock import patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from pipeline import FrameResult
from common.types import (
    RiskState, ObjectClass, AgreementState,
    ThermalDetection, RadarCluster, FusedObject,
    Track, RiskAssessment, AlertEvent,
)
from simulation.scenarios import ALL_SCENARIO_NAMES


# ---------------------------------------------------------------------------
# FakePipeline (scenario-aware)
# ---------------------------------------------------------------------------

def _make_fake_frame(n: int = 1, scenario: str = "SAFE") -> FrameResult:
    return FrameResult(
        timestamp=float(n) * 0.1,
        frame_number=n,
        sync_skew_s=0.005,
        thermal_quality=0.75,
        radar_quality=0.60,
        thermal_detections=[
            ThermalDetection(box_xyxy=(100.0, 80.0, 140.0, 130.0),
                             cls=ObjectClass.PERSON, confidence=0.85, image_quality=0.75)
        ],
        radar_clusters=[
            RadarCluster(range_m=30.0, azimuth_deg=1.5, elevation_deg=0.0,
                         doppler_mps=3.2, rcs_dbsm=8.0, snr_db=18.0,
                         point_count=2, persistence=0.6)
        ],
        fused_objects=[
            FusedObject(timestamp=float(n) * 0.1, position_xy=(0.8, 29.9),
                        velocity_xy=(-0.09, -3.2), cls=ObjectClass.PERSON,
                        confidence=0.72, thermal_weight=0.55, radar_weight=0.45,
                        agreement=AgreementState.AGREEMENT,
                        source_thermal=None, source_radar=None)
        ],
        tracks=[
            Track(track_id=1, position_xy=(0.8, 29.9), velocity_xy=(-0.09, -3.2),
                  cls=ObjectClass.PERSON, confidence=0.72, age_frames=n,
                  missed_frames=0, history=[(0.8, 30.0)])
        ],
        risks=[
            RiskAssessment(track_id=1, ttc_s=9.3, distance_m=29.9,
                           risk_state=RiskState.CAUTION, path_overlap=0.73)
        ],
        alerts=[
            AlertEvent(timestamp=float(n) * 0.1, risk_state=RiskState.CAUTION,
                       track_id=1, message="Object detected ahead", direction_hint="ahead")
        ],
        highest_risk=RiskState.CAUTION,
        latency={"perception": 1.2, "fusion": 0.3, "tracking": 0.1,
                 "risk": 0.05, "alerts": 0.02, "total": 1.67},
        scenario=scenario,
    )


class FakePipeline:
    def __init__(self, max_frames: int = 20, step_delay_s: float = 0.005,
                 scenario: str = "SAFE"):
        self._n = 0
        self._max = max_frames
        self._delay = step_delay_s
        self._scenario = scenario
        self.closed = False

    def step(self) -> Optional[FrameResult]:
        time.sleep(self._delay)
        if self._n >= self._max:
            time.sleep(0.02)
            return None
        self._n += 1
        return _make_fake_frame(self._n, self._scenario)

    def close(self) -> None:
        self.closed = True

    @property
    def frame_count(self) -> int:
        return self._n

    @property
    def fog_severity(self) -> float:
        return 0.0

    @property
    def scenario(self) -> str:
        return self._scenario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_frame(ws, timeout: float = 5.0) -> Optional[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") == "ping":
            continue
        return msg
    return None


# ---------------------------------------------------------------------------
# GET /api/scenarios
# ---------------------------------------------------------------------------

def test_get_scenarios_returns_all():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert "scenarios" in body
    assert "current" in body
    names = [s["name"] for s in body["scenarios"]]
    for expected in ALL_SCENARIO_NAMES:
        assert expected in names, f"Missing scenario: {expected}"


def test_get_scenarios_current_is_valid():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/api/scenarios")
    body = resp.json()
    assert body["current"] in ALL_SCENARIO_NAMES


def test_get_scenarios_has_description():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/api/scenarios")
    for s in resp.json()["scenarios"]:
        assert "description" in s
        assert len(s["description"]) > 0


# ---------------------------------------------------------------------------
# POST /api/scenario — valid
# ---------------------------------------------------------------------------

def test_post_scenario_valid():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.post("/api/scenario", json={"scenario": "CRITICAL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"] == "CRITICAL"
    assert body["status"] == "ok"


def test_post_scenario_case_insensitive():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.post("/api/scenario", json={"scenario": "warning"})
    assert resp.status_code == 200
    assert resp.json()["scenario"] == "WARNING"


def test_post_all_valid_scenarios():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            for name in ALL_SCENARIO_NAMES:
                resp = client.post("/api/scenario", json={"scenario": name})
                assert resp.status_code == 200, f"Failed for scenario {name}"
                assert resp.json()["scenario"] == name


# ---------------------------------------------------------------------------
# POST /api/scenario — invalid
# ---------------------------------------------------------------------------

def test_post_scenario_invalid_returns_400():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.post("/api/scenario", json={"scenario": "NONEXISTENT"})
    assert resp.status_code == 400


def test_post_scenario_empty_string_returns_400():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.post("/api/scenario", json={"scenario": ""})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/status includes scenario
# ---------------------------------------------------------------------------

def test_status_includes_scenario_field():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            resp = client.get("/api/status")
    body = resp.json()
    assert "scenario" in body, "status response must include 'scenario' field"
    assert isinstance(body["scenario"], str)


def test_status_scenario_reflects_post():
    import backend.app as backend_app
    fake = FakePipeline()
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            client.post("/api/scenario", json={"scenario": "MULTI_TARGET"})
            time.sleep(0.05)
            resp = client.get("/api/status")
    assert resp.json()["scenario"] == "MULTI_TARGET"


# ---------------------------------------------------------------------------
# WebSocket frame includes scenario
# ---------------------------------------------------------------------------

def test_websocket_frame_includes_scenario():
    import backend.app as backend_app
    fake = FakePipeline(max_frames=20, step_delay_s=0.005, scenario="WARNING")
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                payload = _first_frame(ws)

    assert payload is not None
    assert "scenario" in payload, "WS frame must contain 'scenario' key"
    assert isinstance(payload["scenario"], str)


def test_websocket_scenario_value_matches_fake():
    import backend.app as backend_app
    fake = FakePipeline(max_frames=20, step_delay_s=0.005, scenario="CRITICAL")
    with patch.object(backend_app, "Pipeline", return_value=fake):
        with TestClient(backend_app.app) as client:
            with client.websocket_connect("/ws/live") as ws:
                payload = _first_frame(ws)

    assert payload is not None
    assert payload["scenario"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Scenario change affects subsequent pipeline data (real pipeline)
# ---------------------------------------------------------------------------

def test_scenario_change_reflected_in_real_pipeline():
    """
    Start real pipeline in SAFE, switch to CRITICAL, confirm scenario field
    in WS frames changes from SAFE to CRITICAL.
    """
    import backend.app as backend_app

    seen_safe = False
    seen_critical = False

    with TestClient(backend_app.app) as client:
        with client.websocket_connect("/ws/live") as ws:
            deadline = time.monotonic() + 12.0

            # Collect a few SAFE frames
            while time.monotonic() < deadline and not seen_safe:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    continue
                if msg.get("scenario") == "SAFE":
                    seen_safe = True

            # Switch to CRITICAL
            client.post("/api/scenario", json={"scenario": "CRITICAL"})

            # Collect frames until we see CRITICAL
            while time.monotonic() < deadline and not seen_critical:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    continue
                if msg.get("scenario") == "CRITICAL":
                    seen_critical = True

    assert seen_safe, "Did not see any SAFE frames before switch"
    assert seen_critical, "Did not see CRITICAL frames after POST /api/scenario"


# ---------------------------------------------------------------------------
# Direct runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import inspect, traceback
    mod = sys.modules[__name__]
    fns = [f for name, f in inspect.getmembers(mod, inspect.isfunction) if name.startswith("test_")]
    passed = failed = 0
    for fn in fns:
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
