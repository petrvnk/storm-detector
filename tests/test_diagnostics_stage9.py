"""Diagnostics export tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from custom_components.storm_detector.const import (
    ATTR_DEGRADATION_REASONS,
    ATTR_SOURCE_STATUS,
    CONF_LIGHTNING_COUNTER_ENTITY_ID,
    CONF_LIGHTNING_DISTANCE_ENTITY_ID,
    CONF_LOCATION_ENTITY_ID,
    COORDINATOR_KEY,
    DOMAIN,
)
from custom_components.storm_detector.diagnostics import async_get_config_entry_diagnostics


class FakeEntry:
    entry_id = "diag-entry"
    data = {
        CONF_LOCATION_ENTITY_ID: "zone.home",
        CONF_LIGHTNING_DISTANCE_ENTITY_ID: "sensor.home_lightning_distance",
        CONF_LIGHTNING_COUNTER_ENTITY_ID: "sensor.home_lightning_counter",
    }
    options = {"analysis_radius_km": 40}


@pytest.mark.asyncio
async def test_diagnostics_export_includes_config_and_runtime_status() -> None:
    coordinator = SimpleNamespace(
        data={
            "level": "warning",
            "summary": "Warning: max 56 dBZ",
            ATTR_SOURCE_STATUS: {"location": "ok", "radar": "ok", "lightning": "ok"},
            ATTR_DEGRADATION_REASONS: (),
            "location_source": "zone.home",
            "radar_diagnostics": (),
            "lightning_diagnostics": (),
            "frame_age_seconds": 120,
            "frames_analyzed": 4,
        }
    )
    hass = SimpleNamespace(
        data={DOMAIN: {FakeEntry.entry_id: {COORDINATOR_KEY: coordinator}}}
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, FakeEntry())

    assert diagnostics["entry"]["entry_id"] == "diag-entry"
    assert diagnostics["entry"]["data"][CONF_LOCATION_ENTITY_ID] == "zone.home"
    assert diagnostics["runtime"]["level"] == "warning"
    assert diagnostics["runtime"][ATTR_SOURCE_STATUS] == {
        "location": "ok",
        "radar": "ok",
        "lightning": "ok",
    }
    assert "summary" in diagnostics["runtime"]
