"""
MINEXIS FastAPI backend.

Architecture
------------
One Pipeline instance (with an attached SimulationController) lives for
the lifetime of the server.  A single background thread runs Pipeline.step()
and broadcasts each FrameResult to all connected WebSocket clients.

The async event loop is NEVER blocked by Pipeline.step().

Endpoints
---------
GET  /health              — liveness probe
GET  /api/status          — runtime summary incl. active scenario
GET  /api/scenarios       — available demo scenarios + current selection
POST /api/scenario        — switch active scenario {"scenario": "CRITICAL"}
WS   /ws/live             — real-time FrameResult JSON stream (incl. scenario)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Ensure the minexis package root is on sys.path
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline import Pipeline, FrameResult
from common.serialization import frame_result_to_dict
from simulation.controller import SimulationController
from sensors.factory import load_hardware_config, sensor_mode_label, _thermal_mode, _radar_mode
from backend.schemas import (
    HealthResponse,
    StatusResponse,
    ScenariosResponse,
    ScenarioInfo,
    ScenarioRequest,
    ScenarioResponse,
    SensorModeResponse,
)

logger = logging.getLogger("minexis.backend")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Shared runtime state
# ---------------------------------------------------------------------------

class _BackendState:
    """
    Lightweight mutable state shared between the worker thread and the
    async broadcast coroutine.  Plain Python attribute writes are GIL-safe
    for reads from the async side.
    """

    def __init__(self) -> None:
        self.running: bool = False
        self.frame_number: int = 0
        self.highest_risk: str = "safe"
        self.last_timestamp: Optional[float] = None
        self.scenario: str = "SAFE"

        # Hardware config (loaded at startup, never changes at runtime)
        self.hw_config: dict = {}

        self.result_queue: Optional[asyncio.Queue] = None
        self.client_queues: set[asyncio.Queue] = set()

        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._pipeline: Optional[Pipeline] = None
        self._controller: Optional[SimulationController] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def add_client(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=30)
        self.client_queues.add(q)
        logger.info("WS client connected. Total: %d", len(self.client_queues))
        return q

    def remove_client(self, q: asyncio.Queue) -> None:
        self.client_queues.discard(q)
        logger.info("WS client disconnected. Total: %d", len(self.client_queues))

    @property
    def connected_clients(self) -> int:
        return len(self.client_queues)


_state = _BackendState()


# ---------------------------------------------------------------------------
# Background pipeline worker
# ---------------------------------------------------------------------------

def _pipeline_worker(
    pipeline: Pipeline,
    state: _BackendState,
    loop: asyncio.AbstractEventLoop,
    result_queue: asyncio.Queue,
    stop_event: threading.Event,
) -> None:
    logger.info("Pipeline worker thread started.")
    state.running = True

    while not stop_event.is_set():
        try:
            result: Optional[FrameResult] = pipeline.step()
        except Exception as exc:          # noqa: BLE001
            logger.exception("Pipeline.step() raised: %s", exc)
            time.sleep(0.05)
            continue

        if result is None:
            time.sleep(0.01)
            continue

        # Update lightweight status (GIL-safe plain assignments)
        state.frame_number = result.frame_number
        state.highest_risk = result.highest_risk.value
        state.last_timestamp = result.timestamp
        state.scenario = result.scenario

        try:
            payload = frame_result_to_dict(result)
        except Exception as exc:          # noqa: BLE001
            logger.exception("Serialization failed: %s", exc)
            continue

        try:
            loop.call_soon_threadsafe(result_queue.put_nowait, payload)
        except asyncio.QueueFull:
            logger.warning("Result queue full — dropping frame %d", result.frame_number)

    state.running = False
    logger.info("Pipeline worker thread stopped.")


# ---------------------------------------------------------------------------
# Async broadcaster
# ---------------------------------------------------------------------------

async def _broadcaster(state: _BackendState, result_queue: asyncio.Queue) -> None:
    logger.info("Broadcaster started.")
    while True:
        try:
            payload: dict = await asyncio.wait_for(result_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            logger.info("Broadcaster cancelled.")
            break

        dead: list[asyncio.Queue] = []
        for cq in list(state.client_queues):
            try:
                cq.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(cq)

        for cq in dead:
            logger.warning("Evicting slow/dead WS client.")
            state.remove_client(cq)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    result_queue: asyncio.Queue = asyncio.Queue(maxsize=60)

    _state._loop = loop
    _state.result_queue = result_queue

    # Load hardware configuration (defaults to synthetic if file missing)
    from sensors.factory import load_hardware_config, create_thermal_source, create_radar_source
    hw_config = load_hardware_config()
    _state.hw_config = hw_config
    logger.info(
        "Hardware mode — thermal: %s  radar: %s",
        hw_config.get("mode", {}).get("thermal", "synthetic"),
        hw_config.get("mode", {}).get("radar",   "synthetic"),
    )

    # Create SimulationController (starts in SAFE scenario)
    # Only wired to sources when both sensors are synthetic.
    controller = SimulationController(initial="SAFE")
    _state._controller = controller
    _state.scenario = controller.get_current_scenario()

    # Determine whether simulation controller should be passed to sources.
    # In real-hardware mode the controller is ignored — never mix demo data
    # with real sensor measurements.
    thermal_is_synthetic = hw_config.get("mode", {}).get("thermal", "synthetic") == "synthetic"
    radar_is_synthetic   = hw_config.get("mode", {}).get("radar",   "synthetic") == "synthetic"

    thermal_source = create_thermal_source(
        hw_config,
        controller=controller if thermal_is_synthetic else None,
    )
    radar_source = create_radar_source(
        hw_config,
        controller=controller if radar_is_synthetic else None,
    )

    # Pipeline with injected sources — step() logic unchanged
    pipeline = Pipeline(
        thermal_source=thermal_source,
        radar_source=radar_source,
        log_path="logs/backend_pipeline_log.jsonl",
        controller=controller if (thermal_is_synthetic and radar_is_synthetic) else None,
    )
    _state._pipeline = pipeline

    stop_event = threading.Event()
    _state._stop_event = stop_event

    worker = threading.Thread(
        target=_pipeline_worker,
        args=(pipeline, _state, loop, result_queue, stop_event),
        daemon=True,
        name="minexis-pipeline-worker",
    )
    worker.start()
    _state._worker_thread = worker

    broadcaster_task = asyncio.create_task(
        _broadcaster(_state, result_queue), name="minexis-broadcaster"
    )

    logger.info(
        "MINEXIS backend started. Sensor mode: %s  Scenario: %s",
        sensor_mode_label(hw_config),
        controller.get_current_scenario(),
    )

    try:
        yield
    finally:
        logger.info("Shutting down...")
        stop_event.set()

        broadcaster_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(broadcaster_task), timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        worker.join(timeout=3.0)
        if worker.is_alive():
            logger.warning("Worker did not stop within timeout.")

        try:
            pipeline.close()
        except Exception as exc:          # noqa: BLE001
            logger.warning("pipeline.close() raised: %s", exc)

        for cq in list(_state.client_queues):
            _state.remove_client(cq)

        logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MINEXIS Backend",
    description="Real-time multi-sensor collision warning — WebSocket + REST API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", service="MINEXIS backend")


@app.get("/api/status", response_model=StatusResponse, tags=["meta"])
async def status() -> StatusResponse:
    """Current pipeline runtime summary including active scenario."""
    # Read scenario directly from the controller (not the worker-updated cache)
    # so it reflects POST /api/scenario immediately, before the next frame.
    ctrl = _state._controller
    current_scenario = ctrl.get_current_scenario() if ctrl is not None else _state.scenario
    return StatusResponse(
        running=_state.running,
        frame_number=_state.frame_number,
        highest_risk=_state.highest_risk,
        last_timestamp=_state.last_timestamp,
        connected_clients=_state.connected_clients,
        scenario=current_scenario,
    )


@app.get("/api/config/mode", response_model=SensorModeResponse, tags=["config"])
async def get_sensor_mode() -> SensorModeResponse:
    """
    Return the current sensor mode for each modality.

    This reflects what is configured in config/hardware.yaml at startup.
    The mode cannot be changed at runtime without restarting the server.

    Response example (default / development):
        {"thermal": "synthetic", "radar": "synthetic", "label": "SYNTHETIC"}
    """
    hw = _state.hw_config
    return SensorModeResponse(
        thermal=_thermal_mode(hw),
        radar=_radar_mode(hw),
        label=sensor_mode_label(hw),
    )


@app.get("/api/scenarios", response_model=ScenariosResponse, tags=["demo"])
async def get_scenarios() -> ScenariosResponse:
    """Return all available demo scenarios and the currently active one."""
    ctrl = _state._controller
    if ctrl is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")
    items = [ScenarioInfo(**s) for s in ctrl.get_available_scenarios()]
    return ScenariosResponse(scenarios=items, current=ctrl.get_current_scenario())


@app.post("/api/scenario", response_model=ScenarioResponse, tags=["demo"])
async def set_scenario(body: ScenarioRequest) -> ScenarioResponse:
    """
    Switch the active demo scenario.

    The change takes effect immediately on the next Pipeline.step() call —
    no restart required.  Returns HTTP 400 for unknown scenario names.
    """
    ctrl = _state._controller
    if ctrl is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")
    try:
        ctrl.set_scenario(body.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_name = ctrl.get_current_scenario()
    _state.scenario = new_name
    logger.info("Scenario changed to: %s", new_name)
    return ScenarioResponse(scenario=new_name, status="ok")


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    """Stream real-time FrameResult JSON (includes 'scenario' field)."""
    await websocket.accept()
    client_queue: asyncio.Queue = _state.add_client()

    try:
        while True:
            try:
                payload: dict = await asyncio.wait_for(client_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                continue

            try:
                await websocket.send_text(json.dumps(payload))
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        _state.remove_client(client_queue)


# ---------------------------------------------------------------------------
# Development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
