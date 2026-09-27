"""
SimulationController — thread-safe scenario selector.

The controller holds the currently active scenario name.  Both the
sensor sources and the FastAPI layer reference the same controller
instance; changing the scenario via the REST API is immediately visible
to the sensor sources on the next read() call without restarting anything.

Design:
- Decoupled from FastAPI: the controller knows nothing about HTTP.
- Thread-safe: a threading.Lock protects the mutable scenario name so the
  worker thread and the async API handler can access it concurrently.
- The default scenario is "SAFE" so the pipeline starts in a benign state.
"""

from __future__ import annotations

import threading
from typing import Optional

from simulation.scenarios import (
    ALL_SCENARIO_NAMES,
    SCENARIOS,
    ScenarioConfig,
)

DEFAULT_SCENARIO = "SAFE"


class SimulationController:
    """
    Thread-safe manager for the active demo scenario.

    Usage
    -----
    controller = SimulationController()
    controller.set_scenario("CRITICAL")   # from any thread
    name = controller.get_current_scenario()
    config = controller.get_current_config()
    """

    def __init__(self, initial: str = DEFAULT_SCENARIO) -> None:
        if initial not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {initial!r}. Valid: {ALL_SCENARIO_NAMES}")
        self._scenario: str = initial
        self._lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------------

    def get_current_scenario(self) -> str:
        with self._lock:
            return self._scenario

    def get_current_config(self) -> ScenarioConfig:
        with self._lock:
            return SCENARIOS[self._scenario]

    def get_available_scenarios(self) -> list[dict]:
        """Return list of {name, description} dicts for all scenarios."""
        return [
            {"name": name, "description": cfg.description}
            for name, cfg in SCENARIOS.items()
        ]

    # -----------------------------------------------------------------------
    # Mutation
    # -----------------------------------------------------------------------

    def set_scenario(self, name: str) -> None:
        """
        Switch to the named scenario.

        Raises ValueError for unknown names so the API layer can convert
        that to an HTTP 400.
        """
        name = name.upper()
        if name not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario: {name!r}. "
                f"Valid names: {ALL_SCENARIO_NAMES}"
            )
        with self._lock:
            self._scenario = name
