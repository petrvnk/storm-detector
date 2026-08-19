"""Real Home Assistant config-entry lifecycle coverage."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from custom_components.storm_detector.const import (
    CONF_ANALYSIS_RADIUS_KM,
    COORDINATOR_KEY,
    DOMAIN,
)

ConfigEntryState = pytest.importorskip("homeassistant.config_entries").ConfigEntryState
async_get_clientsession = pytest.importorskip(
    "homeassistant.helpers.aiohttp_client"
).async_get_clientsession
entity_registry = pytest.importorskip("homeassistant.helpers.entity_registry")
MockConfigEntry = pytest.importorskip(
    "pytest_homeassistant_custom_component.common"
).MockConfigEntry


async def test_static_card_url_is_registered_once_with_real_ha_router(
    hass, hass_client
) -> None:
    """Register the bundled card on the real HA HTTP application, idempotently."""

    import custom_components.storm_detector as integration
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "http", {"http": {}})
    await integration.async_setup(hass, {})
    client = await hass_client()
    first_registration = {
        id(route.resource)
        for route in hass.http.app.router.routes()
        if route.resource.canonical.startswith("/storm_detector")
    }
    await integration.async_setup(hass, {})

    canonical = "/storm_detector/storm-detector-card.js"
    matching = [
        route
        for route in hass.http.app.router.routes()
        if route.resource.canonical.startswith("/storm_detector")
    ]
    assert first_registration
    assert {id(route.resource) for route in matching} == first_registration
    response = await client.get(canonical)
    assert response.status == 200
    assert "storm-detector-card" in await response.text()


@pytest.mark.parametrize(("language", "level_name"), [("en", "Level"), ("cs", "Úroveň")])
async def test_clean_install_registers_exact_locale_stable_entity_ids(
    hass, monkeypatch, language: str, level_name: str
) -> None:
    """Keep registry IDs stable while resolving localized entity display names."""

    import custom_components.storm_detector.coordinator as coordinator_module
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "http", {"http": {}})
    hass.config.language = language

    async def fake_metadata(_session: object) -> dict[str, object]:
        return {
            "radar": {"past": [{"time": 1_710_000_000, "path": "/frame"}]},
            "host": "https://tilecache.rainviewer.com",
        }

    async def fake_colors(_session: object) -> dict[tuple[int, int, int, int], int]:
        return {(255, 255, 255, 255): 0}

    async def fake_analysis(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return _analysis_payload()

    monkeypatch.setattr(coordinator_module, "fetch_radar_metadata", fake_metadata)
    monkeypatch.setattr(coordinator_module, "fetch_rainviewer_color_lookup", fake_colors)
    monkeypatch.setattr(coordinator_module, "analyze_recent_frames", fake_analysis)

    entry = MockConfigEntry(domain=DOMAIN, title="Storm Detector", data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    registry = entity_registry.async_get(hass)
    frozen = {
        "sensor.storm_detector_level",
        "sensor.storm_detector_summary",
        "binary_sensor.storm_detector_active",
        "binary_sensor.storm_detector_data_stale",
        "sensor.storm_detector_max_dbz",
        "sensor.storm_detector_core_distance",
        "sensor.storm_detector_lightning_distance",
        "sensor.storm_detector_frame_age",
        "sensor.storm_detector_last_error",
        "device_tracker.storm_detector_storm_core",
    }
    registered = {
        entity_id
        for entity_id, registry_entry in registry.entities.items()
        if registry_entry.platform == DOMAIN
    }
    assert registered == frozen

    for entity_id in frozen:
        entry = registry.async_get(entity_id)
        assert entry is not None
        assert entry.platform == DOMAIN

    level_entry = registry.async_get("sensor.storm_detector_level")
    assert level_entry is not None
    assert level_entry.original_name == level_name


def _analysis_payload() -> SimpleNamespace:
    return SimpleNamespace(
        max_dbz=40,
        max_core_dbz=None,
        selected_core_threshold_dbz=None,
        selected_core_distance_km=None,
        selected_core_latitude=None,
        selected_core_longitude=None,
        frame_age_seconds=10,
        frame_time=1_710_000_000,
        frames_analyzed=1,
    )


def test_coordinator_omits_config_entry_for_ha_2024_10_signature(monkeypatch) -> None:
    """Construct against the minimum-HA coordinator signature without config_entry."""

    import custom_components.storm_detector.coordinator as coordinator_module

    init_call: dict[str, Any] = {}

    def legacy_init(
        self: object,
        hass: object,
        logger: object,
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        init_call.update(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=update_interval,
        )

    monkeypatch.setattr(coordinator_module.DataUpdateCoordinator, "__init__", legacy_init)
    hass = SimpleNamespace()
    logger = object()
    entry = SimpleNamespace(
        entry_id="minimum-ha",
        state=ConfigEntryState.LOADED,
        data={},
        options={},
    )

    coordinator = coordinator_module.StormDetectorCoordinator(
        hass,
        logger,
        "Storm Detector",
        entry,
    )

    assert coordinator.entry is entry
    assert init_call == {
        "hass": hass,
        "logger": logger,
        "name": "Storm Detector",
        "update_interval": timedelta(seconds=60),
    }


async def test_real_ha_setup_reload_and_unload_lifecycle(hass, monkeypatch) -> None:
    """Exercise setup, options reload, failed unload, and successful cleanup."""

    import custom_components.storm_detector as integration
    import custom_components.storm_detector.coordinator as coordinator_module

    shared_session = async_get_clientsession(hass)
    sessions_seen: list[object] = []

    async def fake_frontend_registration(_hass: object) -> None:
        return None

    async def fake_metadata(session: object) -> dict[str, object]:
        sessions_seen.append(session)
        return {
            "radar": {"past": [{"time": 1_710_000_000, "path": "/frame"}]},
            "host": "https://tilecache.rainviewer.com",
        }

    async def fake_colors(session: object) -> dict[tuple[int, int, int, int], int]:
        sessions_seen.append(session)
        return {(255, 255, 255, 255): 0}

    async def fake_analysis(session: object, *_args: object, **_kwargs: object) -> SimpleNamespace:
        sessions_seen.append(session)
        return _analysis_payload()

    monkeypatch.setattr(integration, "_async_register_frontend_static_path", fake_frontend_registration)
    monkeypatch.setattr(coordinator_module, "fetch_radar_metadata", fake_metadata)
    monkeypatch.setattr(coordinator_module, "fetch_rainviewer_color_lookup", fake_colors)
    monkeypatch.setattr(coordinator_module, "analyze_recent_frames", fake_analysis)

    forward_setups = AsyncMock()
    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", forward_setups)

    entry = MockConfigEntry(domain=DOMAIN, title="Storm Detector", data={}, options={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert COORDINATOR_KEY in hass.data[DOMAIN][entry.entry_id]
    assert hass.data[DOMAIN][entry.entry_id][COORDINATOR_KEY].config_entry is entry
    assert forward_setups.await_count == 1
    assert sessions_seen == [shared_session, shared_session, shared_session]
    assert shared_session.closed is False
    assert len(entry.update_listeners) == 1

    reload_entry = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload_entry)
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_ANALYSIS_RADIUS_KM: 60},
    )
    await hass.async_block_till_done()

    reload_entry.assert_awaited_once_with(entry.entry_id)

    unload_platforms = AsyncMock(return_value=False)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload_platforms)

    assert await integration.async_unload_entry(hass, entry) is False
    assert entry.entry_id in hass.data[DOMAIN]
    assert len(entry.update_listeners) == 1
    assert shared_session.closed is False

    unload_platforms.return_value = True
    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.update_listeners == []
    assert shared_session.closed is False
