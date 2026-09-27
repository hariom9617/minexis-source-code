"""
RD-03D radar packet parser.

IMPORTANT — PROTOCOL STATUS
============================
The Ai-Thinker RD-03D / RD-03D V2 mmWave radar module communicates over
UART at 256 000 baud.  As of the time of writing, the complete binary
packet specification for this specific module has not been independently
confirmed from an official datasheet or SDK in this repository.

What IS known from publicly available community documentation:
  - Communication: UART, 8N1, 256 000 baud
  - Frame header:  0xAA 0xFF 0x03 0x00  (4 bytes)
  - Frame tail:    0x55 0xCC             (2 bytes)
  - The payload between header and tail contains target data
  - The module can report 0–3 simultaneous targets
  - Each target block contains at least: x, y, speed (16-bit signed integers)

What is NOT confirmed in this repository:
  - Exact byte order within each target block
  - Whether elevation is reported (likely not — this is a 2D radar)
  - Whether RCS / SNR are reported (likely not; mapped to defaults below)
  - CRC / checksum byte locations

Action required before production use:
  1. Obtain the RD-03D V2 communication protocol PDF from Ai-Thinker or
     a verified community source.
  2. Capture raw UART output from a live module.
  3. Update ``_parse_target_block()`` with the confirmed field offsets.
  4. Add representative captured packet bytes as test fixtures below.

Design: ``parse_frame(data: bytes) -> list[RadarReturn]``
  - Takes a complete frame (header-stripped or full, see argument ``strip_header``).
  - Returns a list of ``RadarReturn`` objects.
  - Returns an empty list for any structurally invalid packet.
  - Never raises; malformed packets are silently dropped.
  - Suitable for unit testing without physical hardware.

Default fallback values
-----------------------
Fields not provided by the sensor are set to clearly documented defaults:
  elevation_deg = 0.0     (RD-03D is a flat 2D radar; elevation not measured)
  rcs_dbsm      = 0.0     (not reported; neutral placeholder)
  snr_db        = 15.0    (not reported; reasonable placeholder for a detected target)

Coordinate convention
---------------------
The RD-03D reports targets in a Cartesian (x, y) frame where:
  x = lateral offset (metres, +ve = right)
  y = forward distance (metres, +ve = forward)

The pipeline uses (range_m, azimuth_deg) polar coordinates.
Conversion: range = hypot(x, y), azimuth = degrees(atan2(x, y))
"""

from __future__ import annotations

import math
import struct
from typing import Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.types import RadarReturn


# ---------------------------------------------------------------------------
# Known / assumed packet constants
# ---------------------------------------------------------------------------

# Frame header and tail bytes (best-effort from community documentation)
FRAME_HEADER = bytes([0xAA, 0xFF, 0x03, 0x00])
FRAME_TAIL   = bytes([0x55, 0xCC])

# Assumed: each target block is 8 bytes: x(int16), y(int16), speed(int16), 2 reserved
# THIS IS UNCONFIRMED — update when official protocol is available.
TARGET_BLOCK_SIZE = 8

# Maximum number of targets the module is documented to report
MAX_TARGETS = 3

# Fallback values for fields the RD-03D does not report
_DEFAULT_ELEVATION_DEG = 0.0   # flat 2D radar — no elevation measurement
_DEFAULT_RCS_DBSM      = 0.0   # not reported by RD-03D
_DEFAULT_SNR_DB        = 15.0  # not reported; chosen as a mid-range plausible value


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------

def _xy_to_polar(x_m: float, y_m: float) -> tuple[float, float]:
    """
    Convert RD-03D Cartesian (x, y) to polar (range_m, azimuth_deg).

    x_m: lateral offset metres (+ve = right)
    y_m: forward distance metres (+ve = forward)
    Returns: (range_m, azimuth_deg) where azimuth 0 = dead ahead
    """
    range_m    = math.hypot(x_m, y_m)
    azimuth_deg = math.degrees(math.atan2(x_m, y_m))   # atan2(x, y) → 0 = straight ahead
    return range_m, azimuth_deg


# ---------------------------------------------------------------------------
# Per-target block parser (placeholder — update when protocol confirmed)
# ---------------------------------------------------------------------------

def _parse_target_block(block: bytes) -> Optional[RadarReturn]:
    """
    Parse one TARGET_BLOCK_SIZE-byte target block into a RadarReturn.

    PLACEHOLDER IMPLEMENTATION.
    The byte layout assumed here is:
      bytes 0-1: x position  (int16, little-endian, centimetres)
      bytes 2-3: y position  (int16, little-endian, centimetres)
      bytes 4-5: speed       (int16, little-endian, cm/s; +ve = closing)
      bytes 6-7: reserved / ignored

    This is based on best-effort community documentation.  If the captured
    UART output from a real module differs, update the struct.unpack format
    and field indices here.

    Returns None if the block is too short or all values are zero
    (commonly used by the module to indicate an empty/unused target slot).
    """
    if len(block) < TARGET_BLOCK_SIZE:
        return None

    try:
        x_cm, y_cm, speed_cms = struct.unpack_from("<hhh", block, 0)
    except struct.error:
        return None

    # All-zero target slot = no detection (module fills unused slots with zeros)
    if x_cm == 0 and y_cm == 0 and speed_cms == 0:
        return None

    x_m     = x_cm   / 100.0
    y_m     = y_cm   / 100.0
    speed_m = speed_cms / 100.0   # closing speed m/s; +ve = approaching

    range_m, azimuth_deg = _xy_to_polar(x_m, y_m)

    # Guard against implausible values (sensor firmware glitches)
    if range_m < 0.05 or range_m > 10.0:
        return None
    if abs(azimuth_deg) > 60.0:
        return None

    return RadarReturn(
        range_m=range_m,
        azimuth_deg=azimuth_deg,
        elevation_deg=_DEFAULT_ELEVATION_DEG,
        doppler_mps=speed_m,
        rcs_dbsm=_DEFAULT_RCS_DBSM,
        snr_db=_DEFAULT_SNR_DB,
    )


# ---------------------------------------------------------------------------
# Frame-level parser
# ---------------------------------------------------------------------------

def find_frame(buf: bytes) -> tuple[Optional[bytes], bytes]:
    """
    Search ``buf`` for a complete frame delimited by FRAME_HEADER / FRAME_TAIL.

    Returns:
        (frame_payload, remaining_buf)
        - frame_payload: bytes between header and tail (exclusive), or None
          if no complete frame is found.
        - remaining_buf: unconsumed bytes after the frame (for streaming use).
    """
    start = buf.find(FRAME_HEADER)
    if start == -1:
        # No header found; discard everything except the last few bytes
        # (they might be the beginning of a header split across reads).
        keep = min(len(FRAME_HEADER) - 1, len(buf))
        return None, buf[-keep:] if keep else b""

    # Trim everything before the header
    buf = buf[start:]

    end = buf.find(FRAME_TAIL, len(FRAME_HEADER))
    if end == -1:
        # Header found but tail not yet received — keep buffer as-is
        return None, buf

    payload     = buf[len(FRAME_HEADER) : end]
    remaining   = buf[end + len(FRAME_TAIL) :]
    return payload, remaining


def parse_frame(data: bytes, strip_header: bool = True) -> list[RadarReturn]:
    """
    Parse a complete RD-03D UART frame into a list of RadarReturn objects.

    Parameters
    ----------
    data : bytes
        Either the full frame (including header/tail) or just the payload.
    strip_header : bool
        True  → call ``find_frame()`` first to extract the payload.
        False → treat ``data`` as the raw payload directly (for testing).

    Returns
    -------
    list[RadarReturn]
        Zero or more detections.  Empty list for any invalid packet.
        Never raises.
    """
    try:
        if strip_header:
            payload, _ = find_frame(data)
            if payload is None:
                return []
        else:
            payload = data

        returns: list[RadarReturn] = []
        for i in range(MAX_TARGETS):
            offset = i * TARGET_BLOCK_SIZE
            if offset + TARGET_BLOCK_SIZE > len(payload):
                break
            block  = payload[offset : offset + TARGET_BLOCK_SIZE]
            result = _parse_target_block(block)
            if result is not None:
                returns.append(result)

        return returns

    except Exception:  # noqa: BLE001
        # Swallow any unexpected parsing error — a bad frame must not
        # crash the pipeline worker thread.
        return []
