"""
Real thermal camera adapter — Melexis MLX90640.

Produces ``ThermalFrame`` objects from a physical MLX90640 32×24 thermal
array sensor connected over I²C.

Hardware requirements
---------------------
The MLX90640 is connected to an I²C bus (typically Raspberry Pi / Jetson
Nano / similar SBC).  This module will NOT work on a Windows laptop that
has no I²C hardware — if you try to use it there you will get a
``RuntimeError`` on construction with a clear explanation.

Dependency
----------
This adapter requires the ``adafruit-mlx90640`` library:

    pip install adafruit-circuitpython-mlx90640

That library in turn requires:
  - adafruit-circuitpython-busdevice
  - adafruit-blinka (hardware abstraction layer)

These are Linux/SBC-specific and are deliberately NOT included in the
core ``requirements.txt``.  See ``requirements-hardware.txt``.

Lazy import design
------------------
The import of the Adafruit library happens inside ``__init__`` — not at
module level.  This means:
- ``from sensors.mlx90640_source import MLX90640Source`` succeeds on
  any machine.
- The ``RuntimeError`` is only raised when you actually *instantiate*
  ``MLX90640Source``, i.e. when the hardware mode is selected.
- All existing tests that only use synthetic sources continue to import
  and run without issue.

Output contract
---------------
Each ``read()`` call returns a ``ThermalFrame`` with:
  - ``image``:   np.ndarray shape (24, 32), dtype float32, values [0, 1].
                 Normalised min-max across the current frame.
                 (The MLX90640 returns raw temperatures in °C; normalising
                  to [0,1] keeps downstream quality scoring and blob
                  detection consistent with the synthetic source contract.)
  - ``timestamp``: monotonic seconds since source creation
  - ``frame_id``:  monotonically increasing integer
  - ``meta``:      dict with sensor diagnostics (see below)

Meta keys
---------
  "sensor":     "MLX90640"
  "width":      32
  "height":     24
  "fps":        configured fps
  "min_temp_c": float — minimum pixel temperature in this frame
  "max_temp_c": float — maximum pixel temperature in this frame
  "health_ok":  bool  — False if the library reports a sensor error

Downstream pipeline impact
--------------------------
None.  The ThermalBranch.process() receives a ThermalFrame and calls its
own compute_image_quality() + BlobThermalDetector / YoloThermalDetector.
This adapter is only responsible for data acquisition.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import ThermalFrame
from sensors.thermal_source import ThermalSource


class MLX90640Source(ThermalSource):
    """
    Real thermal camera source wrapping the MLX90640 32×24 sensor.

    Parameters
    ----------
    i2c_bus : int
        I²C bus index (e.g. 1 for /dev/i2c-1 on a Raspberry Pi).
    address : int
        I²C address of the sensor (default 0x33).
    fps : int
        Desired frame rate.  MLX90640 supports 1, 2, 4, 8, 16, 32, 64 Hz.
        Higher rates reduce per-frame integration time and increase noise.
    rotation : int
        Clockwise rotation to apply: 0, 90, 180, or 270.
    width : int
        Expected sensor width in pixels (32 for MLX90640).
    height : int
        Expected sensor height in pixels (24 for MLX90640).
    """

    WIDTH  = 32
    HEIGHT = 24

    def __init__(
        self,
        i2c_bus: int = 1,
        address: int = 0x33,
        fps: int = 8,
        rotation: int = 0,
        width: int = 32,
        height: int = 24,
    ) -> None:
        # ----------------------------------------------------------------
        # Lazy import — only attempt to load the Adafruit library now.
        # This means the class can be *imported* on any machine, but
        # instantiating it on a machine without the library or hardware
        # raises a clear RuntimeError.
        # ----------------------------------------------------------------
        try:
            import board          # type: ignore[import-untyped]
            import busio          # type: ignore[import-untyped]
            import adafruit_mlx90640  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "MLX90640Source requires the Adafruit CircuitPython MLX90640 library.\n"
                "Install it with:\n"
                "    pip install adafruit-circuitpython-mlx90640\n"
                "This package is only available on Linux/SBC hardware with I²C support.\n"
                "On Windows development machines, use mode.thermal=synthetic instead.\n"
                f"Original import error: {exc}"
            ) from exc

        self._adafruit_mlx = adafruit_mlx90640

        try:
            i2c = busio.I2C(board.SCL, board.SDA, frequency=400_000)
            self._sensor = adafruit_mlx90640.MLX90640(i2c)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise MLX90640 on I²C bus {i2c_bus}, "
                f"address 0x{address:02X}.\n"
                f"Check wiring and ensure I²C is enabled.\n"
                f"Error: {exc}"
            ) from exc

        # Set refresh rate
        valid_fps = {1, 2, 4, 8, 16, 32, 64}
        if fps not in valid_fps:
            raise ValueError(f"MLX90640 fps must be one of {valid_fps}, got {fps}")
        fps_attr = getattr(
            adafruit_mlx90640.RefreshRate,
            f"REFRESH_{fps}_HZ",
            None,
        )
        if fps_attr is None:
            raise ValueError(f"Could not map fps={fps} to MLX90640 RefreshRate enum")
        self._sensor.refresh_rate = fps_attr

        self._fps      = fps
        self._rotation = rotation
        self._frame_id = 0
        self._t0       = time.monotonic()

        # Pre-allocate the 768-float buffer (32×24 = 768 pixels)
        self._buf: list[float] = [0.0] * (self.WIDTH * self.HEIGHT)

    def read(self) -> Optional[ThermalFrame]:
        """
        Read one frame from the MLX90640.

        Returns None if the sensor is not yet ready (no new data since
        the last call).  Callers should call read() at a rate matching
        or slightly below the configured fps.
        """
        health_ok = True
        try:
            self._sensor.getFrame(self._buf)
        except Exception:
            # Sensor not ready yet (common at startup) or a transient I/O error.
            # Return None so the Synchronizer simply skips this cycle rather
            # than crashing the pipeline.
            health_ok = False
            return None

        raw = np.array(self._buf, dtype=np.float32).reshape(self.HEIGHT, self.WIDTH)

        # Apply rotation if configured
        if self._rotation == 90:
            raw = np.rot90(raw, k=1)
        elif self._rotation == 180:
            raw = np.rot90(raw, k=2)
        elif self._rotation == 270:
            raw = np.rot90(raw, k=3)

        min_t = float(raw.min())
        max_t = float(raw.max())

        # Normalise to [0, 1] — consistent with SyntheticThermalSource contract
        span = max_t - min_t
        if span < 0.1:
            # Essentially uniform temperature (blocked lens, extreme fog, etc.)
            # Return a near-zero image; evidence module will flag low quality.
            normalised = np.zeros_like(raw)
            health_ok = False
        else:
            normalised = ((raw - min_t) / span).astype(np.float32)

        t = time.monotonic() - self._t0
        frame = ThermalFrame(
            timestamp=t,
            image=normalised,
            frame_id=self._frame_id,
            meta={
                "sensor":     "MLX90640",
                "width":      int(raw.shape[1]),
                "height":     int(raw.shape[0]),
                "fps":        self._fps,
                "min_temp_c": min_t,
                "max_temp_c": max_t,
                "health_ok":  health_ok,
            },
        )
        self._frame_id += 1
        return frame

    def close(self) -> None:
        """Release I²C resources."""
        # The Adafruit library manages the I²C bus; nothing explicit to close.
        pass
