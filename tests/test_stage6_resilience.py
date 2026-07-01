"""Stage 6 options, diagnostics, and resilience tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.radar_hail_risk.config_flow import (
    RadarHailRiskOptionsFlowHandler,
    _validate_parameter_ranges,
)
from custom_components.radar_hail_risk.const import (
    ATTR_DEGRADATION_REASONS,
    ATTR_LIGHTNING_DIAGNOSTICS,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LOCATION_SOURCE,
    ATTR_RAINVIEWER_DIAGNOSTICS,
    ATTR_SOURCE_STATUS,
    ATTR_STALE,
    CONF_ANALYSIS_RADIUS_KM,
    CONF_LOCATION_ENTITY_ID,
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
            entity_id=entity_id,
            state=value,
            last_updated=last_updated,
            attributes={},
        )

    def set_location_state(
        self,
        entity_id: str,
        *,
        latitude: float,
        longitude: float,
        last_updated: datetime,
    ) -> None:
        self._states[entity_id] = SimpleNamespace(
            entity_id=entity_id,
            state="0",
            last_updated=last_updated,
            attributes={"latitude": latitude, "longitude": longitude},
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
async def test_options_flow_exposes_location_source_default() -> None:
    class LocationEntry(FakeEntry):
        options = {CONF_LOCATION_ENTITY_ID: "zone.home"}

    flow = RadarHailRiskOptionsFlowHandler(LocationEntry())

    result = await flow.async_step_init()

    schema = result["data_schema"]
    assert schema[CONF_LOCATION_ENTITY_ID] == "zone.home"


def test_parameter_validation_rejects_unsafe_ranges_and_bad_order() -> None:
    assert _validate_parameter_ranges({CONF_ANALYSIS_RADIUS_KM: 5}) == {
        CONF_ANALYSIS_RADIUS_KM: "invalid_range"
    }
    assert _validate_parameter_ranges(
        {
            "core_watch_dbz": 55,
            "core_warning_dbz": 50,
            "core_urgent_dbz": 60,
        }
    ) == {"base": "invalid_threshold_order"}
    assert _validate_parameter_ranges(
        {
            "warning_lightning_distance_km": 8,
            "urgent_lightning_distance_km": 20,
        }
    ) == {"base": "invalid_distance_order"}
    assert _validate_parameter_ranges(
        {
            "lightning_trigger_radius_km": 10,
            "warning_lightning_distance_km": 20,
        }
    ) == {"base": "invalid_trigger_radius"}


@pytest.mark.asyncio
async def test_options_flow_rejects_invalid_parameter_ranges() -> None:
    flow = RadarHailRiskOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init({CONF_ANALYSIS_RADIUS_KM: 5})

    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_ANALYSIS_RADIUS_KM: "invalid_range"}


@pytest.mark.asyncio
async def test_options_flow_coerces_numeric_strings_before_saving() -> None:
    flow = RadarHailRiskOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init({CONF_ANALYSIS_RADIUS_KM: "60"})

    assert result["title"] == "Radar Hail Risk"
    assert result["data"][CONF_ANALYSIS_RADIUS_KM] == 60


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
    assert payload[ATTR_SOURCE_STATUS] == {
        "location": "ok",
        "radar": "degraded",
        "lightning": "ok",
    }
    assert "radar_source_error" in payload[ATTR_DEGRADATION_REASONS]
    assert "rainviewer unavailable" not in payload["last_error"]


@pytest.mark.asyncio
async def test_coordinator_uses_configured_location_entity_as_single_source() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_location_state("zone.home", latitude=49.144, longitude=15.003, last_updated=now)

    class LocationEntry(FakeEntry):
        options = {CONF_LOCATION_ENTITY_ID: "zone.home"}

    captured: dict[str, float] = {}

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {"#ffffff": 0}

    def _fake_analysis(_session: object, _meta: object, lat: float, lon: float, **_kwargs: object):
        captured["lat"] = lat
        captured["lon"] = lon
        return SimpleNamespace(
            max_dbz=40,
            selected_core_threshold_dbz=None,
            selected_core_distance_km=None,
            selected_core_latitude=None,
            selected_core_longitude=None,
            frame_age_seconds=10,
            frame_time=1710000000,
            frames_analyzed=2,
        )

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        _fake_analysis,
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            LocationEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert captured == {"lat": 49.144, "lon": 15.003}
    assert payload[ATTR_LOCATION_SOURCE] == "zone.home"


@pytest.mark.asyncio
async def test_missing_configured_location_entity_degrades_cleanly() -> None:
    hass = FakeHass()

    class LocationEntry(FakeEntry):
        options = {CONF_LOCATION_ENTITY_ID: "zone.missing"}

    coordinator = RadarHailRiskCoordinator(
        hass,
        None,
        "Radar Hail Risk",
        LocationEntry(),
        session_factory=FakeSessionContext,
    )
    payload = await coordinator._async_update_data()

    assert payload["level"] == "unavailable"
    assert payload[ATTR_STALE] is True
    assert payload[ATTR_LOCATION_SOURCE] == "zone.missing"
    assert payload[ATTR_SOURCE_STATUS] == {
        "location": "error",
        "radar": "skipped",
        "lightning": "skipped",
    }
    assert payload[ATTR_DEGRADATION_REASONS] == ("missing_location_entity",)
    assert payload["diagnostics"] == ["missing_location_entity"]


@pytest.mark.asyncio
async def test_radar_only_mode_marks_lightning_not_configured_without_degradation_reason() -> None:
    hass = FakeHass()

    class RadarOnlyEntry(FakeEntry):
        data = {CONF_ANALYSIS_RADIUS_KM: 40}
        options = {}

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {"#ffffff": 0}

    def _fake_analysis(*_args: object, **_kwargs: object):
        return SimpleNamespace(
            max_dbz=40,
            selected_core_threshold_dbz=None,
            selected_core_distance_km=None,
            selected_core_latitude=None,
            selected_core_longitude=None,
            frame_age_seconds=10,
            frame_time=1710000000,
            frames_analyzed=2,
        )

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        _fake_analysis,
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            RadarOnlyEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload[ATTR_SOURCE_STATUS]["lightning"] == "not_configured"
    assert payload[ATTR_LIGHTNING_DIAGNOSTICS] == ("lightning_not_configured",)
    assert "lightning_not_configured" not in payload[ATTR_DEGRADATION_REASONS]
