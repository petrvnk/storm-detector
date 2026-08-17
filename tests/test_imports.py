"""Import smoke tests for the Stage 2 skeleton.

These catch regressions where local static-tool fallbacks compile but modules fail
at import time when Home Assistant is not installed in the dev environment.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


def test_stage2_modules_import_without_homeassistant_installed() -> None:
    modules = [
        "custom_components.storm_detector",
        "custom_components.storm_detector.config_flow",
        "custom_components.storm_detector.sensor",
        "custom_components.storm_detector.binary_sensor",
        "custom_components.storm_detector.device_tracker",
        "custom_components.storm_detector.coordinator",
        "custom_components.storm_detector.lightning",
        "custom_components.storm_detector.rainviewer",
        "custom_components.storm_detector.risk",
    ]

    for module in modules:
        assert importlib.import_module(module)


def test_old_runtime_package_is_absent_and_not_importable() -> None:
    root = Path(__file__).resolve().parents[1]

    assert not (root / "custom_components" / "radar_hail_risk").exists()
    assert importlib.util.find_spec("custom_components.radar_hail_risk") is None
