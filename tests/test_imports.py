"""Import smoke tests for the Stage 2 skeleton.

These catch regressions where local static-tool fallbacks compile but modules fail
at import time when Home Assistant is not installed in the dev environment.
"""

from __future__ import annotations

import importlib


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
