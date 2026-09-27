"""
Real radar adapter — Ai-Thinker RD-03D / RD-03D V2.

Reads raw UART bytes from the sensor, reassembles complete frames using a
streaming ring buffer, and delegates packet parsing to ``rd03d_parser``
(which is separately unit-testable without physical hardware).

IMPORTANT — PROTOCOL STATUS
============================
See sensors/rd03d_parser.py for the full protocol disclaimer.
The parser is a best-effort placeholder; update _parse_target_block()
once the official Ai-Thinker protocol PDF is obtained.

Hardware requirements
---------------------
- RD-03D connected via USB-to-UART adapter or direct UART pins
- Serial port configured at 256 000 baud, 8N1
- ``pyserial`` installed: pip install pyserial

Dependency
----------
``pyserial`` is deliberately NOT in the core requirements.txt.
See requirements-hardware.txt.

The import happens lazily inside __init__ so that:
  - ``from sensors.rd03d_source import RealRadarSource`` works on any machine
  - The RuntimeError is raised only when the class is actually instantiated
  - Existing tests using synthetic sources are completely unaffected

Output contract
---------------
Each ``read()`` call returns a ``RadarScan`` with:
  - ``returns``:   list[RadarReturn], 0-3 entries from the current frame
  - ``timestamp``: monotonic seconds since source creation
  - ``scan_id``:   monotonically increasing integer
  - ``meta``:      {"sensor": "RD03D", "port": ..., "health_ok": bool}

Returns None if no new complete frame has arrived since the last call
(the UART read thread may still be filling the buffer).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import RadarScan, RadarReturn
from sensors.radar_source import RadarSource
from sensors.rd03d_parser import find_frame, parse_frame, FRAME_HEADER, FRAME_TAIL


class RealRadarSource(RadarSource):
    """
    Real radar source wrapping the RD-03D mmWave module.

    A background daemon thread reads raw bytes from the UART port and
    pushes complete frames into a small deque.  ``read()`` pops the
    latest frame, parses it, and returns a RadarScan.  This keeps
    Pipeline.step() non-blocking even when the UART is slow.

    Parameters
    ----------
    port : str
        Serial port name (e.g. "COM3" on Windows, "/dev/ttyUSB0" on Linux).
    baudrate : int
        UART baud rate (default 256 000 — RD-03D factory setting).
    timeout : float
        Serial read timeout in seconds.
    """

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 256_000,
        timeout: float = 1.0,
    ) -> None:
        # Lazy import — only fail when hardware mode is actually selected.
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "RealRadarSource requires the pyserial package.\n"
                "Install it with:\n"
                "    pip install pyserial\n"
                "See requirements-hardware.txt.\n"
                "On development machines without hardware, use mode.radar=synthetic.\n"
                f"Original import error: {exc}"
            ) from exc

        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to open serial port {port!r} at {baudrate} baud.\n"
                f"Check that the RD-03D is connected and the port is correct.\n"
                f"Error: {exc}"
            ) from exc

        self._port      = port
        self._scan_id   = 0
        self._t0        = time.monotonic()
        self._health_ok = True

        # Latest complete raw frame (bytes between header and tail, inclusive)
        # A deque of length 1 means we always have the most recent frame
        # and older unread frames are discarded automatically.
        self._frame_queue: deque[bytes] = deque(maxlen=4)
        self._buf        = b""
        self._lock       = threading.Lock()
        self._stop_event = threading.Event()

        # Background reader thread
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
            name="rd03d-reader",
        )
        self._reader_thread.start()

    # -----------------------------------------------------------------------
    # Background reader
    # -----------------------------------------------------------------------

    def _reader_loop(self) -> None:
        """
        Continuously reads bytes from the UART and reassembles complete
        frames.  Runs in a daemon thread so it dies automatically if the
        main process exits.
        """
        while not self._stop_event.is_set():
            try:
                chunk = self._serial.read(64)   # non-blocking at timeout=1s
            except Exception:
                self._health_ok = False
                time.sleep(0.1)
                continue

            if not chunk:
                continue

            with self._lock:
                self._buf += chunk
                # Extract as many complete frames as possible
                while True:
                    payload, remainder = find_frame(self._buf)
                    if payload is None:
                        self._buf = remainder
                        break
                    # Reconstruct the full framed packet for the queue
                    full_frame = FRAME_HEADER + payload + FRAME_TAIL
                    self._frame_queue.append(full_frame)
                    self._buf = remainder

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def read(self) -> Optional[RadarScan]:
        """
        Return the latest radar scan if a new frame is available, else None.

        Never blocks.  The background reader thread feeds frames
        asynchronously; this method simply pops and parses.
        """
        with self._lock:
            if not self._frame_queue:
                return None
            raw = self._frame_queue.popleft()

        returns: list[RadarReturn] = parse_frame(raw, strip_header=True)

        t = time.monotonic() - self._t0
        scan = RadarScan(
            timestamp=t,
            returns=returns,
            scan_id=self._scan_id,
            meta={
                "sensor":   "RD03D",
                "port":     self._port,
                "health_ok": self._health_ok,
            },
        )
        self._scan_id += 1
        return scan

    def close(self) -> None:
        """Stop the reader thread and close the serial port."""
        self._stop_event.set()
        self._reader_thread.join(timeout=2.0)
        try:
            self._serial.close()
        except Exception:
            pass
