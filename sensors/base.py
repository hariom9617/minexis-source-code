"""
Sensor source base interfaces for MINEXIS.

Uses ``typing.Protocol`` so existing classes (SyntheticThermalSource,
SyntheticRadarSource, RealThermalSource, RealRadarSource) satisfy the
interface without inheriting from a common base class — no rewrites needed.

The existing ``ThermalSource`` and ``RadarSource`` classes defined in
thermal_source.py and radar_source.py continue to work exactly as before.
This module provides the typed Protocol definitions that can be used for
static type checking and documentation.

Pipeline.step() only ever calls:
    source.read()     -> Optional[ThermalFrame | RadarScan]
    source.close()    -> None

Any object that provides those two methods is a valid sensor source.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.types import ThermalFrame, RadarScan


@runtime_checkable
class ThermalSourceProtocol(Protocol):
    """
    Protocol satisfied by any thermal camera source.

    read() must return the latest ThermalFrame, or None if no new frame
    is available yet (e.g. the sensor hasn't fired since the last call).

    close() must release hardware resources (file handles, I²C bus,
    threads).  It is safe to call close() more than once.
    """

    def read(self) -> Optional[ThermalFrame]:
        """Return the next ThermalFrame or None."""
        ...

    def close(self) -> None:
        """Release resources."""
        ...


@runtime_checkable
class RadarSourceProtocol(Protocol):
    """
    Protocol satisfied by any radar source.

    read() must return a RadarScan containing zero or more RadarReturn
    objects, or None if the sensor hasn't produced a new scan since the
    last call.

    close() must release UART/USB/socket handles and background threads.
    """

    def read(self) -> Optional[RadarScan]:
        """Return the next RadarScan or None."""
        ...

    def close(self) -> None:
        """Release resources."""
        ...


# Convenience type aliases used throughout the codebase
ThermalSourceType = ThermalSourceProtocol
RadarSourceType   = RadarSourceProtocol
