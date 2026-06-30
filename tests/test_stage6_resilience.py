"""Stage 6 options, diagnostics, and resilience tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.radar_hail_risk.config_flow import RadarHailRiskOptionsFlowHandler
from custom_components.radar_hail_risk.const import (
    ATTR_LIGHTNING_DIAGNOSTICS,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_RAINVIEWER_DIAGNOSTICS,
    ATTR_STALE,
    CONF_ANALYSIS_RADIUS_KM,
    CONF_RAINVIEWER_FRAMES,
    DEFAULT_RAINVIEWER_FRAMES,
    RISK_LEVEL_WARNING,
)
from custom_components.radar_hail_risk.coordinator import RadarHailRiskCoordinator
from custom_components.radar_hail_risk.rainviewer import fetch_radar_metadata


class FakeHass:
    def __init__(self) -> None:
        self.config = SimpleNamespace(latitude=50.0755, longitude=14.4378)
        self._states: dict[str, SimpleNamespace] = {}

    @property
    def states(self) -> SimpleNamespace:
        return SimpleNamespace(get=self._states.get)

    def set_state(self, entity_id: str, value: str, *, last_updated: datetime) -> None:
        self._states[entity_id] = SimpleNamespace(
            state=value,
            last_updated=last_updated,
            attributes={},
        )


class FakeSessionContext:
    async def __aenter__(self) -> "FakeSessionContext":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeEntry:
    entry_id = "entry-stage6"
    data = {
        "lightning_distance_entity_id": "sensor.lightning_distance",
        "lightning_counter_entity_id": "sensor.lightning_count",
        CONF_ANALYSIS_RADIUS_KM: 40,
    }
    options = {
        CONF_RAINVIEWER_FRAMES: 2,
    }


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, object] | None = None) -> None:
        self.status = status
        self._payload = payload or {}

    async def json(self, content_type: str | None = None) -> dict[str, object]:
        return self._payload

    async def release(self) -> None:
        return None


class FlakySession:
    def __init__(self) -> None:
        self.calls = 0

    async def get(self, _url: str, timeout: int = 20) -> FakeResponse:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("temporary network timeout")
        return FakeResponse(
            200,
            {
                "radar": {"past": []},
                "host": "https://tilecache.rainviewer.com",
            },
        )


@pytest.mark.asyncio
async def test_options_flow_uses_existing_options_as_defaults() -> None:
    flow = RadarHailRiskOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init()

    schema = result["data_schema"]
    assert schema[CONF_ANALYSIS_RADIUS_KM] == 40
    assert schema[CONF_RAINVIEWER_FRAMES] == 2
    assert schema[CONF_RAINVIEWER_FRAMES] != DEFAULT_RAINVIEWER_FRAMES


@pytest.mark.asyncio
async def test_rainviewer_metadata_retries_transient_errors_without_open_meteo() -> None:
    session = FlakySession()

    payload = await fetch_radar_metadata(
        session,
        api_base="https://fake-rainviewer",
        ttl_seconds=0,
        retry_attempts=1,
        retry_backoff_seconds=0,
    )

    assert payload["host"] == "https://tilecache.rainviewer.com"
    assert session.calls == 2


@pytest.mark.asyncio
async def test_coordinator_degrades_to_lightning_when_radar_source_fails() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_state("sensor.lightning_distance", "4.5", last_updated=now - timedelta(seconds=10))
    hass.set_state("sensor.lightning_count", "20", last_updated=now - timedelta(seconds=10))

    async def _broken_meta(*_args: object, **_kwargs: object):
        raise TimeoutError("rainviewer unavailable")

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _broken_meta,
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            FakeEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload["level"] == RISK_LEVEL_WARNING
    assert payload[ATTR_LIGHTNING_DISTANCE_KM] == 4.5
    assert payload[ATTR_STALE] is False
    assert "radar_source_error" in payload[ATTR_RAINVIEWER_DIAGNOSTICS]
    assert payload[ATTR_LIGHTNING_DIAGNOSTICS] == ()
    assert "rainviewer unavailable" not in payload["last_error"]
