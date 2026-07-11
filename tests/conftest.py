"""Shared pytest configuration for Home Assistant integration tests."""

from __future__ import annotations

import importlib.util

import pytest

if importlib.util.find_spec("pytest_homeassistant_custom_component") is not None:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
        """Allow loading the integration from custom_components."""
