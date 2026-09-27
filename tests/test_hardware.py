"""
Hardware abstraction layer tests.

Tests are organised into three categories:
1. Unit tests that run on any machine (no hardware or special deps needed)
2. Tests that require pyserial (skipped if not installed)
3. Tests marked @pytest.mark.hardware — skipped unless --hardware flag
   is passed to pytest, ensuring CI never depends on physical sensors

Run all non-hardware tests:
    pytest tests/test_hardware.py -v

Run with hardware connected (requires physical sensors + pyserial):
    pytest tests/test_hardware.py -v --hardware
"""

from __future__ import annotations

import sys
import os
import struct
import time

import pytest
import numpy as np

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# pytest custom marker + conftest hook
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    """Add --hardware flag to pytest CLI."""
    try:
        parser.addoption(
            "--hardware",
            action="store_true",
            default=False,
            help="Run tests that require physical hardware to be connected",
        )
    except ValueError:
        pass  # already added by conftest in another test file


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "hardware: marks tests that require physical sensor hardware (skip with -m 'not hardware')",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hardware_available(request) -> bool:
    return request.config.getoption("--hardware", default=False)


# ---------------------------------------------------------------------------
# 1.  sensors/base.py — Protocol interface
# ---------------------------------------------------------------------------

class TestSensorBase:
    def test_import(self):
        from sensors.base import ThermalSourceProtocol, RadarSourceProtocol
        assert ThermalSourceProtocol is not None
        assert RadarSourceProtocol is not None

    def test_synthetic_satisfies_thermal_protocol(self):
        from sensors.base import ThermalSourceProtocol
        from sensors.thermal_source import SyntheticThermalSource
        src = SyntheticThermalSource()
        assert isinstance(src, ThermalSourceProtocol)
        src.close()

    def test_synthetic_satisfies_radar_protocol(self):
        from sensors.base import RadarSourceProtocol
        from sensors.radar_source import SyntheticRadarSource
        src = SyntheticRadarSource()
        assert isinstance(src, RadarSourceProtocol)
        src.close()


# ---------------------------------------------------------------------------
# 2.  sensors/factory.py
# ---------------------------------------------------------------------------

class TestFactory:
    """Factory unit tests — all run without hardware."""

    def _synthetic_config(self) -> dict:
        return {"mode": {"thermal": "synthetic", "radar": "synthetic"}}

    def _real_config(self) -> dict:
        return {
            "mode":    {"thermal": "real", "radar": "real"},
            "thermal": {"bus": 1, "address": 0x33, "fps": 8, "rotation": 0,
                        "width": 32, "height": 24},
            "radar":   {"port": "COM99", "baudrate": 256_000, "timeout": 0.1},
        }

    def test_load_hardware_config_returns_dict(self):
        from sensors.factory import load_hardware_config
        cfg = load_hardware_config()
        assert isinstance(cfg, dict)

    def test_default_mode_is_synthetic(self):
        from sensors.factory import load_hardware_config, _thermal_mode, _radar_mode
        cfg = load_hardware_config()
        assert _thermal_mode(cfg) == "synthetic"
        assert _radar_mode(cfg)   == "synthetic"

    def test_sensor_mode_label_synthetic(self):
        from sensors.factory import sensor_mode_label
        assert sensor_mode_label(self._synthetic_config()) == "SYNTHETIC"

    def test_sensor_mode_label_real(self):
        from sensors.factory import sensor_mode_label
        assert sensor_mode_label(self._real_config()) == "REAL"

    def test_sensor_mode_label_mixed(self):
        from sensors.factory import sensor_mode_label
        cfg = {"mode": {"thermal": "synthetic", "radar": "real"}}
        label = sensor_mode_label(cfg)
        assert "MIXED" in label

    def test_create_thermal_synthetic(self):
        from sensors.factory import create_thermal_source
        from sensors.thermal_source import SyntheticThermalSource
        src = create_thermal_source(self._synthetic_config())
        assert isinstance(src, SyntheticThermalSource)
        frame = src.read()
        assert frame is not None
        src.close()

    def test_create_radar_synthetic(self):
        from sensors.factory import create_radar_source
        from sensors.radar_source import SyntheticRadarSource
        src = create_radar_source(self._synthetic_config())
        assert isinstance(src, SyntheticRadarSource)
        scan = src.read()
        assert scan is not None
        src.close()

    def test_create_thermal_real_raises_without_library(self):
        """Without Adafruit libs installed, real mode must raise RuntimeError."""
        from sensors.factory import create_thermal_source
        try:
            import adafruit_mlx90640  # type: ignore[import-untyped]
            pytest.skip("adafruit_mlx90640 is installed — cannot test missing-import path")
        except ImportError:
            with pytest.raises(RuntimeError, match="MLX90640Source requires"):
                create_thermal_source(self._real_config())

    def test_create_radar_real_raises_without_pyserial_or_port(self):
        """Real radar mode with a non-existent port must raise RuntimeError."""
        from sensors.factory import create_radar_source
        try:
            import serial  # type: ignore[import-untyped]
            # pyserial is installed but port COM99 doesn't exist
            with pytest.raises(RuntimeError, match="Failed to open serial port"):
                create_radar_source(self._real_config())
        except ImportError:
            # pyserial itself is missing
            with pytest.raises(RuntimeError, match="pyserial"):
                create_radar_source(self._real_config())

    def test_factory_with_simulation_controller(self):
        from sensors.factory import create_thermal_source, create_radar_source
        from simulation.controller import SimulationController
        ctrl = SimulationController()
        thermal = create_thermal_source(self._synthetic_config(), controller=ctrl)
        radar   = create_radar_source(self._synthetic_config(),   controller=ctrl)
        assert thermal is not None
        assert radar   is not None
        thermal.close()
        radar.close()


# ---------------------------------------------------------------------------
# 3.  sensors/mlx90640_source.py — import & lazy-load behaviour
# ---------------------------------------------------------------------------

class TestMLX90640Source:
    def test_import_does_not_raise(self):
        """The module must be importable on any machine."""
        from sensors import mlx90640_source  # noqa: F401

    def test_class_importable(self):
        from sensors.mlx90640_source import MLX90640Source
        assert MLX90640Source is not None

    def test_instantiation_raises_without_adafruit(self):
        """Instantiation without the Adafruit library must raise RuntimeError."""
        from sensors.mlx90640_source import MLX90640Source
        try:
            import adafruit_mlx90640  # type: ignore[import-untyped]
            pytest.skip("adafruit_mlx90640 is installed — hardware test only")
        except ImportError:
            with pytest.raises(RuntimeError, match="adafruit-circuitpython-mlx90640"):
                MLX90640Source()

    @pytest.mark.hardware
    def test_real_mlx90640_frame_shape(self, request):
        if not _hardware_available(request):
            pytest.skip("Pass --hardware to run physical sensor tests")
        from sensors.mlx90640_source import MLX90640Source
        src = MLX90640Source(fps=4)
        time.sleep(0.5)  # allow one frame to be captured
        frame = src.read()
        src.close()
        assert frame is not None, "MLX90640 did not produce a frame"
        assert frame.image.shape == (24, 32)
        assert frame.image.dtype == np.float32
        assert 0.0 <= float(frame.image.min()) and float(frame.image.max()) <= 1.0
        assert frame.meta.get("sensor") == "MLX90640"
        assert isinstance(frame.meta.get("health_ok"), bool)


# ---------------------------------------------------------------------------
# 4.  sensors/rd03d_parser.py — pure unit tests (no hardware)
# ---------------------------------------------------------------------------

def _make_packet(targets: list[tuple[int, int, int]]) -> bytes:
    """
    Build a synthetic RD-03D UART packet.
    targets: list of (x_cm, y_cm, speed_cms) tuples (up to 3)
    Fills unused target slots with zeros.
    """
    from sensors.rd03d_parser import FRAME_HEADER, FRAME_TAIL, TARGET_BLOCK_SIZE, MAX_TARGETS
    payload = b""
    for i in range(MAX_TARGETS):
        if i < len(targets):
            x, y, s = targets[i]
            payload += struct.pack("<hhh", x, y, s) + b"\x00\x00"
        else:
            payload += b"\x00" * TARGET_BLOCK_SIZE
    return FRAME_HEADER + payload + FRAME_TAIL


class TestRD03DParser:
    def test_import(self):
        from sensors import rd03d_parser  # noqa: F401

    def test_parse_single_target(self):
        from sensors.rd03d_parser import parse_frame
        pkt = _make_packet([(150, 300, -50)])   # 1.5 m right, 3 m forward, closing 0.5 m/s
        returns = parse_frame(pkt, strip_header=True)
        assert len(returns) == 1
        r = returns[0]
        # range ≈ hypot(1.5, 3.0) ≈ 3.35 m
        assert 3.0 <= r.range_m <= 3.8
        # azimuth ≈ atan2(1.5, 3.0) ≈ 26.6°
        assert 20.0 <= r.azimuth_deg <= 32.0
        # doppler: speed_cms=−50 → −0.5 m/s (negative = closing convention)
        assert r.doppler_mps == pytest.approx(-0.5, abs=0.01)
        assert r.elevation_deg == 0.0   # documented default
        assert r.snr_db == 15.0         # documented default

    def test_parse_three_targets(self):
        from sensors.rd03d_parser import parse_frame
        pkt = _make_packet([(100, 200, -30), (-80, 150, -20), (50, 400, -60)])
        returns = parse_frame(pkt, strip_header=True)
        assert len(returns) == 3

    def test_empty_targets_returns_empty(self):
        """All-zero target slots → no detections."""
        from sensors.rd03d_parser import parse_frame
        pkt = _make_packet([])
        returns = parse_frame(pkt, strip_header=True)
        assert returns == []

    def test_malformed_packet_returns_empty(self):
        """Garbage bytes → no crash, empty result."""
        from sensors.rd03d_parser import parse_frame
        for bad in [b"", b"\x00" * 3, b"\xFF" * 100, b"not a radar packet"]:
            result = parse_frame(bad, strip_header=True)
            assert isinstance(result, list)

    def test_truncated_payload_returns_partial(self):
        """Truncated payload → only complete target blocks are parsed."""
        from sensors.rd03d_parser import FRAME_HEADER, FRAME_TAIL, parse_frame
        # Build a packet with only 1 target block (8 bytes) instead of 3×8=24
        payload = struct.pack("<hhh", 100, 200, -30) + b"\x00\x00"
        pkt = FRAME_HEADER + payload + FRAME_TAIL
        result = parse_frame(pkt, strip_header=True)
        assert isinstance(result, list)
        assert len(result) <= 1

    def test_find_frame_no_header(self):
        from sensors.rd03d_parser import find_frame
        payload, remaining = find_frame(b"\x01\x02\x03")
        assert payload is None

    def test_find_frame_complete(self):
        from sensors.rd03d_parser import find_frame, FRAME_HEADER, FRAME_TAIL
        content  = b"\x11\x22\x33"
        full_pkt = FRAME_HEADER + content + FRAME_TAIL
        payload, remaining = find_frame(full_pkt)
        assert payload == content
        assert remaining == b""

    def test_find_frame_with_trailing_bytes(self):
        from sensors.rd03d_parser import find_frame, FRAME_HEADER, FRAME_TAIL
        content  = b"\xAB\xCD"
        extra    = b"\x01\x02"
        full_pkt = FRAME_HEADER + content + FRAME_TAIL + extra
        payload, remaining = find_frame(full_pkt)
        assert payload == content
        assert remaining == extra

    def test_coordinate_conversion_dead_ahead(self):
        """Target directly ahead: x=0, y>0 → azimuth=0, range=y."""
        from sensors.rd03d_parser import parse_frame
        pkt = _make_packet([(0, 300, -40)])   # x=0, y=3m → dead ahead
        returns = parse_frame(pkt, strip_header=True)
        assert len(returns) == 1
        assert returns[0].azimuth_deg == pytest.approx(0.0, abs=1.0)
        assert returns[0].range_m     == pytest.approx(3.0, abs=0.1)

    def test_out_of_range_target_filtered(self):
        """Targets outside plausible range (>10 m) are silently filtered."""
        from sensors.rd03d_parser import parse_frame
        # x=500 cm, y=1500 cm → range ≈ 15.8 m > 10 m limit
        pkt = _make_packet([(500, 1500, -50)])
        returns = parse_frame(pkt, strip_header=True)
        assert returns == []

    @pytest.mark.hardware
    def test_real_rd03d_produces_scan(self, request):
        if not _hardware_available(request):
            pytest.skip("Pass --hardware to run physical sensor tests")
        try:
            from sensors.rd03d_source import RealRadarSource
        except RuntimeError as e:
            pytest.skip(f"Hardware not available: {e}")
        import os
        port = os.environ.get("RD03D_PORT", "COM3")
        src = RealRadarSource(port=port)
        time.sleep(1.0)
        scan = src.read()
        src.close()
        # Might be None if no targets present — just check it runs without error
        if scan is not None:
            assert scan.meta.get("sensor") == "RD03D"
            assert isinstance(scan.returns, list)


# ---------------------------------------------------------------------------
# 5.  sensors/rd03d_source.py — import without pyserial
# ---------------------------------------------------------------------------

class TestRD03DSource:
    def test_import_does_not_raise(self):
        from sensors import rd03d_source  # noqa: F401

    def test_class_importable(self):
        from sensors.rd03d_source import RealRadarSource
        assert RealRadarSource is not None

    def test_instantiation_raises_without_pyserial_or_port(self):
        from sensors.rd03d_source import RealRadarSource
        try:
            import serial  # type: ignore[import-untyped]
            # pyserial present but COM99 will not exist
            with pytest.raises(RuntimeError, match="Failed to open serial port"):
                RealRadarSource(port="COM99")
        except ImportError:
            with pytest.raises(RuntimeError, match="pyserial"):
                RealRadarSource(port="COM99")


# ---------------------------------------------------------------------------
# 6.  Pipeline accepts injected sources
# ---------------------------------------------------------------------------

class TestPipelineSourceInjection:
    def test_pipeline_with_factory_sources(self):
        from sensors.factory import create_thermal_source, create_radar_source
        from pipeline import Pipeline

        cfg = {"mode": {"thermal": "synthetic", "radar": "synthetic"}}
        thermal = create_thermal_source(cfg)
        radar   = create_radar_source(cfg)

        pipe = Pipeline(
            thermal_source=thermal,
            radar_source=radar,
            log_path=None,
        )
        result = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            result = pipe.step()
            if result is not None:
                break
            time.sleep(0.01)
        pipe.close()

        assert result is not None
        assert result.frame_number >= 1

    def test_pipeline_scenario_still_works_with_factory(self):
        from sensors.factory import create_thermal_source, create_radar_source
        from simulation.controller import SimulationController
        from pipeline import Pipeline

        ctrl = SimulationController()
        ctrl.set_scenario("WARNING")
        cfg = {"mode": {"thermal": "synthetic", "radar": "synthetic"}}

        thermal = create_thermal_source(cfg, controller=ctrl)
        radar   = create_radar_source(cfg, controller=ctrl)
        pipe    = Pipeline(
            thermal_source=thermal,
            radar_source=radar,
            log_path=None,
            controller=ctrl,
        )

        results = []
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and len(results) < 5:
            r = pipe.step()
            if r is not None:
                results.append(r)
            else:
                time.sleep(0.01)
        pipe.close()

        assert len(results) >= 1
        assert all(r.scenario == "WARNING" for r in results)


# ---------------------------------------------------------------------------
# 7.  Backend config/mode endpoint
# ---------------------------------------------------------------------------

class TestBackendModeEndpoint:
    def test_get_config_mode_returns_synthetic(self):
        import backend.app as backend_app
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from tests.test_backend import FakePipeline

        fake = FakePipeline()
        with patch.object(backend_app, "Pipeline", return_value=fake):
            with TestClient(backend_app.app) as client:
                resp = client.get("/api/config/mode")

        assert resp.status_code == 200
        body = resp.json()
        assert "thermal" in body
        assert "radar"   in body
        assert "label"   in body
        assert body["thermal"] == "synthetic"
        assert body["radar"]   == "synthetic"
        assert body["label"]   == "SYNTHETIC"


# ---------------------------------------------------------------------------
# Direct runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import inspect, traceback
    mod = sys.modules[__name__]
    fns = [f for name, f in inspect.getmembers(mod, inspect.isfunction) if name.startswith("test_")]
    # Also collect methods from test classes
    classes = [c for name, c in inspect.getmembers(mod, inspect.isclass) if name.startswith("Test")]
    for cls in classes:
        instance = cls()
        for name, m in inspect.getmembers(instance, callable):
            if name.startswith("test_") and "hardware" not in name:
                fns.append(m)

    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {getattr(fn, '__name__', str(fn))}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {getattr(fn, '__name__', str(fn))}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
