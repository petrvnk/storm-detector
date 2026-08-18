"""Shared pytest configuration for Home Assistant integration tests."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator

import pytest
from custom_components.storm_detector.rainviewer import _clear_runtime_caches


@pytest.fixture(autouse=True)
def clear_rainviewer_runtime_caches() -> Iterator[None]:
    """Keep process-local upstream caches isolated between tests."""

    _clear_runtime_caches()
    yield
    _clear_runtime_caches()

if importlib.util.find_spec("pytest_homeassistant_custom_component") is not None:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
        """Allow loading the integration from custom_components."""
