"""
Sensor source factory.

This is the ONLY place in MINEXIS that decides which sensor implementation
is used.  All other code receives a source object that satisfies the
ThermalSource / RadarSource interface — it never needs to know whether
the data is synthetic or real.

Usage
-----
    from sensors.factory import create_thermal_source, create_radar_source, SensorMode

    thermal = create_thermal_source(config)   # config from hardware.yaml
    radar   = create_radar_source(config)

The ``config`` argument is a plain dict (e.g. from yaml.safe_load):

    {
        "mode":    {"thermal": "synthetic", "radar": "synthetic"},
        "thermal": {"fps": 8, "bus": 1, "address": 0x33, ...},
        "radar":   {"port": "COM3", "baudrate": 256000, ...},
    }

If mode.thermal / mode.radar is absent or unrecognised it defaults to
"synthetic", so the application always starts safely.

Simulation controller integration
----------------------------------
When synthetic mode is active and a SimulationController is provided, it
is passed through to the synthetic sources.  In real-hardware mode the
controller is ignored — you cannot mix demo scenario inputs with real
sensor data.

Safety: never mix synthetic and real data
-----------------------------------------
The factory enforces that both thermal and radar modes are consistent with
each other from a labelling perspective.  The returned ``sensor_mode``
string is:
    "SYNTHETIC"          — both sources are synthetic
    "REAL"               — both sources are hardware
    "MIXED (thermal=X, radar=Y)"  — one of each (allowed but flagged)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.controller import SimulationController


# Canonical mode string values
MODE_SYNTHETIC = "synthetic"
MODE_REAL      = "real"


def _thermal_mode(config: dict) -> str:
    return str(config.get("mode", {}).get("thermal", MODE_SYNTHETIC)).lower()


def _radar_mode(config: dict) -> str:
    return str(config.get("mode", {}).get("radar", MODE_SYNTHETIC)).lower()


def sensor_mode_label(config: dict) -> str:
    """
    Return a human-readable sensor mode label for display in the dashboard.

    Returns one of:
        "SYNTHETIC"
        "REAL"
        "MIXED (thermal=real, radar=synthetic)"   (or vice-versa)
    """
    tm = _thermal_mode(config)
    rm = _radar_mode(config)
    if tm == MODE_SYNTHETIC and rm == MODE_SYNTHETIC:
        return "SYNTHETIC"
    if tm == MODE_REAL and rm == MODE_REAL:
        return "REAL"
    return f"MIXED (thermal={tm}, radar={rm})"


def create_thermal_source(
    config: dict,
    controller: Optional["SimulationController"] = None,
):
    """
    Create and return a thermal source based on ``config``.

    Parameters
    ----------
    config : dict
        Full hardware config dict (loaded from hardware.yaml).
    controller : SimulationController | None
        Simulation controller for demo scenarios.  Only used when
        mode.thermal == "synthetic".  Ignored for real hardware.

    Returns
    -------
    ThermalSource-compatible object.
    """
    mode = _thermal_mode(config)

    if mode == MODE_REAL:
        from sensors.mlx90640_source import MLX90640Source
        tc = config.get("thermal", {})
        return MLX90640Source(
            i2c_bus=int(tc.get("bus", 1)),
            address=int(tc.get("address", 0x33)),
            fps=int(tc.get("fps", 8)),
            rotation=int(tc.get("rotation", 0)),
            width=int(tc.get("width", 32)),
            height=int(tc.get("height", 24)),
        )

    # Default / "synthetic"
    from sensors.thermal_source import SyntheticThermalSource
    return SyntheticThermalSource(controller=controller)


def create_radar_source(
    config: dict,
    controller: Optional["SimulationController"] = None,
):
    """
    Create and return a radar source based on ``config``.

    Parameters
    ----------
    config : dict
        Full hardware config dict (loaded from hardware.yaml).
    controller : SimulationController | None
        Simulation controller for demo scenarios.  Only used when
        mode.radar == "synthetic".  Ignored for real hardware.

    Returns
    -------
    RadarSource-compatible object.
    """
    mode = _radar_mode(config)

    if mode == MODE_REAL:
        from sensors.rd03d_source import RealRadarSource
        rc = config.get("radar", {})
        return RealRadarSource(
            port=str(rc.get("port", "COM3")),
            baudrate=int(rc.get("baudrate", 256_000)),
            timeout=float(rc.get("timeout", 1.0)),
        )

    # Default / "synthetic"
    from sensors.radar_source import SyntheticRadarSource
    return SyntheticRadarSource(controller=controller)


def load_hardware_config(path: Optional[str] = None) -> dict:
    """
    Load hardware.yaml and return a plain dict.

    Falls back to a synthetic-only config if the file cannot be read,
    so the application always starts safely.
    """
    import os

    if path is None:
        # Resolve relative to the repository root (parent of sensors/)
        _this_dir = os.path.dirname(os.path.abspath(__file__))
        _repo_root = os.path.dirname(_this_dir)
        path = os.path.join(_repo_root, "config", "hardware.yaml")

    try:
        import yaml  # type: ignore[import-untyped]
        with open(path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        return cfg if isinstance(cfg, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
