"""Real Home Assistant config-entry lifecycle coverage."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from custom_components.radar_hail_risk.const import (
    CONF_ANALYSIS_RADIUS_KM,
    COORDINATOR_KEY,
    DOMAIN,
)

ConfigEntryState = pytest.importorskip("homeassistant.config_entries").ConfigEntryState
async_get_clientsession = pytest.importorskip(
    "homeassistant.helpers.aiohttp_client"
).async_get_clientsession
MockConfigEntry = pytest.importorskip(
    "pytest_homeassistant_custom_component.common"
).MockConfigEntry


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

    import custom_components.radar_hail_risk.coordinator as coordinator_module

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

    coordinator = coordinator_module.RadarHailRiskCoordinator(
        hass,
        logger,
        "Radar Hail Risk",
        entry,
    )

    assert coordinator.entry is entry
    assert init_call == {
        "hass": hass,
        "logger": logger,
        "name": "Radar Hail Risk",
        "update_interval": timedelta(seconds=60),
    }


async def test_real_ha_setup_reload_and_unload_lifecycle(hass, monkeypatch) -> None:
    """Exercise setup, options reload, failed unload, and successful cleanup."""

    import custom_components.radar_hail_risk as integration
    import custom_components.radar_hail_risk.coordinator as coordinator_module

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

    entry = MockConfigEntry(domain=DOMAIN, title="Radar Hail Risk", data={}, options={})
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
