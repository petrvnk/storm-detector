"""Import smoke tests for the Stage 2 skeleton.

These catch regressions where local static-tool fallbacks compile but modules fail
at import time when Home Assistant is not installed in the dev environment.
"""

from __future__ import annotations

import importlib


def test_stage2_modules_import_without_homeassistant_installed() -> None:
    modules = [
        "custom_components.radar_hail_risk",
        "custom_components.radar_hail_risk.config_flow",
        "custom_components.radar_hail_risk.sensor",
        "custom_components.radar_hail_risk.binary_sensor",
        "custom_components.radar_hail_risk.device_tracker",
        "custom_components.radar_hail_risk.coordinator",
        "custom_components.radar_hail_risk.lightning",
        "custom_components.radar_hail_risk.rainviewer",
        "custom_components.radar_hail_risk.risk",
    ]

    for module in modules:
        assert importlib.import_module(module)
