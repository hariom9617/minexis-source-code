"""
Radar source.

SyntheticRadarSource generates plausible radar returns for the same
simulated approaching object used by SyntheticThermalSource (roughly
matched in time/motion so fusion has something real to agree on), plus
clutter/multipath noise returns so the radar branch has something to
suppress.

When the real 4D/mmWave radar arrives, implement `LiveRadarSource` with
the same `read()` interface and swap it in `main.py`.

Demo/simulation mode
--------------------
Pass a SimulationController to the constructor.  Each call to read() will
look up the active scenario and generate returns that match its target
specifications.  When no controller is provided the original default
behaviour is preserved exactly.
"""

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import RadarScan, RadarReturn

if TYPE_CHECKING:
    from simulation.controller import SimulationController


class RadarSource:
    def read(self) -> Optional[RadarScan]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class SyntheticRadarSource(RadarSource):
    """
    Simulates a 4D radar scan.

    Default mode (controller=None):
        One real closing target plus clutter/ghost returns — identical to
        the original implementation.

    Demo mode (controller=<SimulationController>):
        Uses the active scenario's TargetSpec list to generate returns.
        Each target maintains independent range state.  Clutter is always
        added.  Scenario changes take effect on the next read() call.
    """

    def __init__(
        self,
        fps: float = 10.0,
        clutter_returns: int = 12,
        ghost_probability: float = 0.15,
        seed: int = 7,
        controller: Optional["SimulationController"] = None,
    ):
        self.dt = 1.0 / fps
        self.clutter_returns = clutter_returns
        self.ghost_probability = ghost_probability
        self._rng = np.random.default_rng(seed)
        self._scan_id = 0
        self._t0 = time.monotonic()
        self._controller = controller

        # --- Default (no-controller) target state --------------------------
        # Mirrors the original implementation exactly.
        self._target_range = 45.0
        self._target_azimuth = 1.5
        self._target_closing_speed = 3.2

        # --- Per-scenario target range state --------------------------------
        # Indexed by target position in the scenario's target list.
        # Reset when the scenario changes.
        self._scenario_ranges: list[float] = []
        self._last_scenario: str = ""

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _sync_scenario_state(self, scenario_name: str, num_targets: int) -> None:
        """Re-initialise per-target range state if the scenario changed."""
        if scenario_name != self._last_scenario or len(self._scenario_ranges) != num_targets:
            self._last_scenario = scenario_name
            # Import here to avoid circular import at module load time.
            from simulation.scenarios import SCENARIOS
            cfg = SCENARIOS[scenario_name]
            self._scenario_ranges = [t.initial_range_m for t in cfg.targets]

    def _build_target_return(
        self,
        target_range: float,
        azimuth_deg: float,
        closing_speed: float,
        rcs_dbsm: float,
        snr_db: float,
    ) -> RadarReturn:
        return RadarReturn(
            range_m=target_range + float(self._rng.normal(0, 0.15)),
            azimuth_deg=azimuth_deg + float(self._rng.normal(0, 0.4)),
            elevation_deg=float(self._rng.normal(0, 0.3)),
            doppler_mps=closing_speed + float(self._rng.normal(0, 0.2)),
            rcs_dbsm=float(self._rng.normal(rcs_dbsm, 1.0)),
            snr_db=float(self._rng.normal(snr_db, 1.5)),
        )

    def _build_clutter(self) -> list[RadarReturn]:
        clutter = []
        for _ in range(self.clutter_returns):
            clutter.append(
                RadarReturn(
                    range_m=float(self._rng.uniform(2, 60)),
                    azimuth_deg=float(self._rng.uniform(-40, 40)),
                    elevation_deg=float(self._rng.normal(0, 1.0)),
                    doppler_mps=float(self._rng.normal(0, 0.15)),
                    rcs_dbsm=float(self._rng.normal(-2.0, 3.0)),
                    snr_db=float(self._rng.normal(6.0, 2.0)),
                )
            )
        return clutter

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def read(self) -> Optional[RadarScan]:
        t = time.monotonic() - self._t0
        returns: list[RadarReturn] = []

        if self._controller is not None:
            # ---- Demo / scenario mode ------------------------------------
            from simulation.scenarios import SCENARIOS
            scenario_name = self._controller.get_current_scenario()
            cfg = SCENARIOS[scenario_name]
            targets = cfg.targets

            self._sync_scenario_state(scenario_name, len(targets))

            for i, spec in enumerate(targets):
                # Advance range each tick
                self._scenario_ranges[i] -= spec.closing_speed_mps * self.dt
                if self._scenario_ranges[i] < spec.reset_range_m:
                    self._scenario_ranges[i] = spec.initial_range_m

                returns.append(
                    self._build_target_return(
                        target_range=self._scenario_ranges[i],
                        azimuth_deg=spec.azimuth_deg,
                        closing_speed=spec.closing_speed_mps,
                        rcs_dbsm=spec.rcs_dbsm,
                        snr_db=spec.snr_db,
                    )
                )

        else:
            # ---- Default mode (original behaviour) -----------------------
            self._target_range -= self._target_closing_speed * self.dt
            if self._target_range < 3.0:
                self._target_range = 45.0

            returns.append(
                RadarReturn(
                    range_m=self._target_range + self._rng.normal(0, 0.15),
                    azimuth_deg=self._target_azimuth + self._rng.normal(0, 0.4),
                    elevation_deg=self._rng.normal(0, 0.3),
                    doppler_mps=self._target_closing_speed + self._rng.normal(0, 0.2),
                    rcs_dbsm=self._rng.normal(8.0, 1.5),
                    snr_db=self._rng.normal(18.0, 2.0),
                )
            )

            # Clutter + ghost only in default mode
            returns.extend(self._build_clutter())
            if self._rng.uniform() < self.ghost_probability:
                returns.append(
                    RadarReturn(
                        range_m=self._target_range * float(self._rng.uniform(1.3, 1.8)),
                        azimuth_deg=self._target_azimuth + float(self._rng.uniform(-15, 15)),
                        elevation_deg=float(self._rng.normal(0, 0.5)),
                        doppler_mps=self._target_closing_speed * float(self._rng.uniform(-1.5, -0.5)),
                        rcs_dbsm=float(self._rng.normal(4.0, 2.0)),
                        snr_db=float(self._rng.normal(10.0, 2.0)),
                    )
                )
            scan = RadarScan(
                timestamp=t,
                returns=returns,
                scan_id=self._scan_id,
                meta={"health_ok": True},
            )
            self._scan_id += 1
            return scan

        # Add clutter in demo mode too (gives the radar branch real work)
        returns.extend(self._build_clutter())

        scan = RadarScan(
            timestamp=t,
            returns=returns,
            scan_id=self._scan_id,
            meta={"health_ok": True},
        )
        self._scan_id += 1
        return scan
