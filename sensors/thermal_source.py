"""
Thermal camera source.

SyntheticThermalSource generates plausible thermal frames with a moving
"hot" object (simulating a person or vehicle) plus configurable noise/fog
degradation.

Demo/simulation mode
--------------------
Pass a SimulationController to the constructor.  Each call to read() will
look up the active scenario's TargetSpec list and render one hot-blob per
target at positions derived from the per-target range state maintained by
the radar source.  Because both sources share the same controller instance
they automatically stay in sync: when the scenario changes both sources
switch simultaneously.

When no controller is provided the original default behaviour is preserved
exactly — the existing pipeline, CLI and tests are unaffected.
"""

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import ThermalFrame

if TYPE_CHECKING:
    from simulation.controller import SimulationController


class ThermalSource:
    """Interface every thermal source must implement."""

    def read(self) -> Optional[ThermalFrame]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class SyntheticThermalSource(ThermalSource):
    """
    Generates synthetic thermal frames.

    Default mode (controller=None):
        Moving hot blob against a noisy background — identical to the
        original implementation.

    Demo mode (controller=<SimulationController>):
        Renders one hot-blob per target in the active scenario.
        Blob horizontal position is derived from the target's azimuth_deg
        (mapped through the same linear calibration used by AdaptiveFusion),
        so thermal and radar returns point to the same spatial location and
        fusion will match them.
        Fog severity is read from ScenarioConfig.fog_severity each frame.
    """

    def __init__(
        self,
        width: int = 320,
        height: int = 256,
        fps: float = 10.0,
        fog_severity: float = 0.0,
        seed: int = 42,
        controller: Optional["SimulationController"] = None,
    ):
        self.width = width
        self.height = height
        self.dt = 1.0 / fps
        self.fog_severity = fog_severity   # only used in default (no-controller) mode
        self._rng = np.random.default_rng(seed)
        self._frame_id = 0
        self._t0 = time.monotonic()
        self._controller = controller

        # --- Default mode object state (original implementation) ------------
        self._obj_x = width * 0.5
        self._obj_y = height * 0.85
        self._obj_size = 14.0
        self._obj_vy = -1.6
        self._obj_temp = 0.85

        # --- Per-scenario target range state (mirrors radar source) ---------
        self._scenario_ranges: list[float] = []
        self._last_scenario: str = ""

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _sync_scenario_state(self, scenario_name: str, num_targets: int) -> None:
        """Re-initialise per-target range state if the scenario changed."""
        if scenario_name != self._last_scenario or len(self._scenario_ranges) != num_targets:
            self._last_scenario = scenario_name
            from simulation.scenarios import SCENARIOS
            cfg = SCENARIOS[scenario_name]
            self._scenario_ranges = [t.initial_range_m for t in cfg.targets]

    def _azimuth_to_pixel_x(self, azimuth_deg: float) -> float:
        """
        Linear azimuth → pixel-x mapping matching CalibrationConfig in
        fusion/adaptive_fusion.py (horizontal_fov_deg=50, width=320).
        """
        frac = azimuth_deg / 50.0           # 50° total FOV
        return self.width * (0.5 + frac)

    def _range_to_pixel_y(self, range_m: float, blob_size_px: float) -> float:
        """
        Map target range to a vertical position in the frame.
        Close targets appear near the top (lower y); far targets near the
        bottom (higher y).  Clamps to stay inside the image.
        """
        # Normalise: range 0 m → y=0.15*height (top), range 60 m → y=0.95*height (bottom)
        frac = min(max(range_m / 60.0, 0.0), 1.0)
        y = self.height * (0.95 - 0.80 * (1.0 - frac))
        return float(np.clip(y, blob_size_px, self.height - blob_size_px))

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def read(self) -> Optional[ThermalFrame]:
        t = time.monotonic() - self._t0

        if self._controller is not None:
            # ---- Demo / scenario mode ------------------------------------
            from simulation.scenarios import SCENARIOS
            scenario_name = self._controller.get_current_scenario()
            cfg = SCENARIOS[scenario_name]
            fog = cfg.fog_severity
        else:
            fog = self.fog_severity

        # Background noise field
        base_contrast = 1.0 - 0.75 * fog
        background = self._rng.normal(
            loc=0.25, scale=0.05 * base_contrast, size=(self.height, self.width)
        ).astype(np.float32)
        img = background.copy()
        yy, xx = np.ogrid[: self.height, : self.width]

        if self._controller is not None:
            # ---- Demo / scenario mode ------------------------------------
            from simulation.scenarios import SCENARIOS
            scenario_name = self._controller.get_current_scenario()
            cfg = SCENARIOS[scenario_name]
            targets = cfg.targets

            self._sync_scenario_state(scenario_name, len(targets))

            # Render one blob per scenario target
            for i, spec in enumerate(targets):
                # Advance range each tick (mirrors radar source exactly)
                self._scenario_ranges[i] -= spec.closing_speed_mps * self.dt
                if self._scenario_ranges[i] < spec.reset_range_m:
                    self._scenario_ranges[i] = spec.initial_range_m

                current_range = self._scenario_ranges[i]
                obj_x = self._azimuth_to_pixel_x(spec.azimuth_deg)
                
                # Calculate vertical position based on current range
                obj_y = self._range_to_pixel_y(current_range, spec.blob_size_px)
                
                # Scale blob size slightly with range (closer = bigger)
                # Range 100m → base size, range 10m → 2x size
                size_scale = 1.0 + (1.0 - min(current_range / 100.0, 1.0))
                obj_size = spec.blob_size_px * size_scale

                dist2 = (xx - obj_x) ** 2 + (yy - obj_y) ** 2
                intensity = (spec.thermal_intensity * base_contrast) * np.exp(
                    -dist2 / (2 * obj_size ** 2)
                )
                img = np.clip(img + intensity, 0.0, 1.0).astype(np.float32)

            meta: dict = {
                "fog_severity": fog,
                "scenario": scenario_name,
            }
        else:
            # ---- Default mode (original behaviour) -----------------------
            self._obj_y += self._obj_vy
            self._obj_size += 0.15
            if self._obj_y < 20:
                self._obj_y = self.height * 0.85
                self._obj_size = 14.0

            dist2 = (xx - self._obj_x) ** 2 + (yy - self._obj_y) ** 2
            blob_intensity = (self._obj_temp * base_contrast) * np.exp(
                -dist2 / (2 * self._obj_size ** 2)
            )
            img = np.clip(img + blob_intensity, 0.0, 1.0).astype(np.float32)

            meta = {
                "fog_severity": fog,
                "obj_center_px": (float(self._obj_x), float(self._obj_y)),
                "obj_size_px": float(self._obj_size),
            }

        frame = ThermalFrame(
            timestamp=t,
            image=img,
            frame_id=self._frame_id,
            meta=meta,
        )
        self._frame_id += 1
        return frame

    def set_fog_severity(self, severity: float) -> None:
        """Live-adjust fog severity (default mode only)."""
        self.fog_severity = max(0.0, min(1.0, severity))
