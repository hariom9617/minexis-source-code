"""
Pydantic response schemas for the MINEXIS REST endpoints.

WebSocket frames are plain dicts produced by
``common.serialization.frame_result_to_dict()`` — Pydantic is not in
the hot path for WebSocket streaming.
"""

from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class HealthResponse(BaseModel):
    status: str
    service: str


class StatusResponse(BaseModel):
    running: bool
    frame_number: int
    highest_risk: str          # RiskState string value, e.g. "safe"
    last_timestamp: Optional[float]
    connected_clients: int
    scenario: str              # active demo scenario name, e.g. "CRITICAL"


class ScenarioInfo(BaseModel):
    name: str
    description: str


class ScenariosResponse(BaseModel):
    scenarios: list[ScenarioInfo]
    current: str


class ScenarioRequest(BaseModel):
    scenario: str


class ScenarioResponse(BaseModel):
    scenario: str
    status: str                # "ok"


class SensorModeResponse(BaseModel):
    thermal: str               # "synthetic" | "real"
    radar: str                 # "synthetic" | "real"
    label: str                 # "SYNTHETIC" | "REAL" | "MIXED (...)"
