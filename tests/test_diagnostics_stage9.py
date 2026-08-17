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
async def test_diagnostics_export_includes_only_safe_options_and_runtime_health() -> None:
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

    assert "diag-entry" not in repr(diagnostics)
    assert "zone.home" not in repr(diagnostics)
    assert diagnostics["runtime"]["level"] == "warning"
    assert diagnostics["runtime"][ATTR_SOURCE_STATUS] == {
        "location": "ok",
        "radar": "ok",
        "lightning": "ok",
    }
    assert diagnostics["options"] == {"analysis_radius_km": 40}
    assert "summary" not in diagnostics["runtime"]
    assert "entry" not in diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_location_and_config_identity_sentinels() -> None:
    """Issue-report diagnostics must retain health without reversible identity data."""
    private_latitude = 49.123456789
    private_longitude = 16.987654321
    private_location = "zone.private_home_sentinel"
    private_distance = "sensor.alice_private_lightning_distance"
    private_counter = "sensor.alice_private_lightning_counter"
    private_entry_id = "01PRIVATEENTRYIDSENTINEL"
    private_title = "Alice Home Private Sentinel"
    private_config_value = "private-config-sentinel"

    entry = SimpleNamespace(
        entry_id=private_entry_id,
        title=private_title,
        data={
            CONF_LOCATION_ENTITY_ID: private_location,
            CONF_LIGHTNING_DISTANCE_ENTITY_ID: private_distance,
            CONF_LIGHTNING_COUNTER_ENTITY_ID: private_counter,
            "latitude": private_latitude,
            "longitude": private_longitude,
            "private_label": private_config_value,
        },
        options={
            "analysis_radius_km": 40,
            "latitude": private_latitude,
            "longitude": private_longitude,
            "private_option": private_config_value,
        },
    )
    coordinator = SimpleNamespace(
        data={
            "level": "warning",
            "summary": private_title,
            ATTR_SOURCE_STATUS: {"location": "ok", "radar": "ok", "lightning": "stale"},
            ATTR_DEGRADATION_REASONS: ("lightning_stale",),
            "location_source": private_location,
            "selected_core_latitude": private_latitude,
            "selected_core_longitude": private_longitude,
            "lightning_latitude": private_latitude,
            "lightning_longitude": private_longitude,
            "radar_diagnostics": ("frame_current",),
            "frame_age_seconds": 120,
            "frames_analyzed": 4,
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {private_entry_id: {COORDINATOR_KEY: coordinator}}})

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = repr(diagnostics)

    for sentinel in (
        str(private_latitude),
        str(private_longitude),
        private_location,
        private_distance,
        private_counter,
        private_entry_id,
        private_title,
        private_config_value,
    ):
        assert sentinel not in serialized

    assert diagnostics["runtime"][ATTR_SOURCE_STATUS] == {
        "location": "ok",
        "radar": "ok",
        "lightning": "stale",
    }
    assert diagnostics["runtime"][ATTR_DEGRADATION_REASONS] == ("lightning_stale",)
    assert diagnostics["runtime"]["radar_diagnostics"] == ("frame_current",)
    assert diagnostics["runtime"]["frame_age_seconds"] == 120
    assert diagnostics["runtime"]["frames_analyzed"] == 4
    assert diagnostics["options"] == {"analysis_radius_km": 40}
