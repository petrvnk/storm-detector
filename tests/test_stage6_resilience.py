"""Stage 6 options, diagnostics, and resilience tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.storm_detector.config_flow import (
    StormDetectorConfigFlow,
    StormDetectorOptionsFlowHandler,
    _clean_optional_entity_ids,
    _has_partial_lightning_config,
    _validate_parameter_ranges,
)
from custom_components.storm_detector.const import (
    ATTR_DEGRADATION_REASONS,
    ATTR_EVIDENCE_KIND,
    ATTR_LIGHTNING_DIAGNOSTICS,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LOCATION_SOURCE,
    ATTR_RAINVIEWER_DIAGNOSTICS,
    ATTR_SOURCE_STATUS,
    ATTR_STALE,
    CONF_ANALYSIS_RADIUS_KM,
    CONF_LIGHTNING_AZIMUTH_ENTITY_ID,
    CONF_LIGHTNING_COUNTER_ENTITY_ID,
    CONF_LIGHTNING_DISTANCE_ENTITY_ID,
    CONF_LOCATION_ENTITY_ID,
    CONF_MIN_CORE_PIXELS,
    CONF_RAINVIEWER_FRAMES,
    DEFAULT_MIN_CORE_PIXELS,
    DEFAULT_RAINVIEWER_FRAMES,
    EVIDENCE_KIND_LIGHTNING_ONLY,
    OPTIONAL_CONF_DEFAULTS,
    RISK_LEVEL_WARNING,
)
from custom_components.storm_detector.coordinator import StormDetectorCoordinator
from custom_components.storm_detector.rainviewer import fetch_radar_metadata


class FakeHass:
    def __init__(self) -> None:
        self.config = SimpleNamespace(latitude=50.0755, longitude=14.4378)
        self._states: dict[str, SimpleNamespace] = {}

    @property
    def states(self) -> SimpleNamespace:
        return SimpleNamespace(
            get=self._states.get,
            async_all=lambda: list(self._states.values()),
        )

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


class ReadOnlyConfigEntryOptionsFlow(StormDetectorOptionsFlowHandler):
    @property
    def config_entry(self) -> object:
        return object()


class IsolatedConfigFlow(StormDetectorConfigFlow):
    """Exercise flow behavior without requiring a Home Assistant flow manager."""

    async def async_set_unique_id(self, *_args: object, **_kwargs: object) -> None:
        return None

    def _abort_if_unique_id_configured(self, *_args: object, **_kwargs: object) -> None:
        return None

    def async_create_entry(self, **kwargs: object) -> dict[str, object]:
        return kwargs


def _schema_default(schema: object, field_name: str) -> object:
    """Read a field default from either a fallback dict or voluptuous schema."""

    schema_mapping = getattr(schema, "schema", schema)
    if not isinstance(schema_mapping, dict):
        raise AssertionError("Expected a mapping-backed options schema")
    for marker, value in schema_mapping.items():
        if getattr(marker, "schema", marker) != field_name:
            continue
        default = getattr(marker, "default", None)
        return default() if callable(default) else (value if default is None else default)
    raise AssertionError(f"Missing schema field: {field_name}")


def _schema_fields(schema: object) -> set[str]:
    """Return field names from either a fallback dict or voluptuous schema."""

    schema_mapping = getattr(schema, "schema", schema)
    if not isinstance(schema_mapping, dict):
        raise AssertionError("Expected a mapping-backed schema")
    return {str(getattr(marker, "schema", marker)) for marker in schema_mapping}


def test_initial_config_schema_only_exposes_simple_location_and_lightning_fields() -> None:
    flow = SimpleNamespace(hass=FakeHass())

    schema = StormDetectorConfigFlow._base_schema(flow)  # type: ignore[arg-type]

    assert _schema_fields(schema) == {
        CONF_LOCATION_ENTITY_ID,
        CONF_LIGHTNING_DISTANCE_ENTITY_ID,
        CONF_LIGHTNING_COUNTER_ENTITY_ID,
    }


def test_blank_lightning_fields_are_radar_only_and_partial_pair_is_rejected() -> None:
    cleaned = _clean_optional_entity_ids(
        {
            CONF_LIGHTNING_DISTANCE_ENTITY_ID: " ",
            CONF_LIGHTNING_COUNTER_ENTITY_ID: "",
        }
    )

    assert cleaned == {
        CONF_LIGHTNING_DISTANCE_ENTITY_ID: None,
        CONF_LIGHTNING_COUNTER_ENTITY_ID: None,
    }
    assert _has_partial_lightning_config(cleaned) is False
    assert _has_partial_lightning_config(
        {CONF_LIGHTNING_DISTANCE_ENTITY_ID: "sensor.lightning_distance"}
    ) is True


@pytest.mark.asyncio
async def test_explicit_radar_only_selection_survives_options_update_and_reload() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_state("sensor.blitzortung_lightning_distance", "4.5", last_updated=now)
    hass.set_state("sensor.blitzortung_lightning_count", "20", last_updated=now)

    setup_flow = IsolatedConfigFlow()
    setup_flow.hass = hass
    setup = await setup_flow.async_step_user({})
    assert setup["data"][CONF_LIGHTNING_DISTANCE_ENTITY_ID] is None
    assert setup["data"][CONF_LIGHTNING_COUNTER_ENTITY_ID] is None

    entry = SimpleNamespace(entry_id="entry-explicit-radar-only", data=setup["data"], options={})
    options_flow = StormDetectorOptionsFlowHandler(entry)
    saved = await options_flow.async_step_init({CONF_ANALYSIS_RADIUS_KM: 60})
    assert saved["data"][CONF_LIGHTNING_DISTANCE_ENTITY_ID] is None
    assert saved["data"][CONF_LIGHTNING_COUNTER_ENTITY_ID] is None

    entry.options = saved["data"]
    reloaded = StormDetectorCoordinator(
        hass,
        None,
        "Storm Detector",
        entry,
        session_factory=FakeSessionContext,
    )
    assert reloaded._build_lightning_snapshot(now) is None


def test_legacy_entry_without_lightning_keys_retains_runtime_autodetection() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_state("sensor.blitzortung_lightning_distance", "4.5", last_updated=now)
    hass.set_state("sensor.blitzortung_lightning_count", "20", last_updated=now)
    legacy_entry = SimpleNamespace(entry_id="entry-legacy", data={}, options={})

    coordinator = StormDetectorCoordinator(
        hass,
        None,
        "Storm Detector",
        legacy_entry,
        session_factory=FakeSessionContext,
    )

    snapshot = coordinator._build_lightning_snapshot(now)
    assert snapshot is not None
    assert snapshot.distance_km == 4.5
    assert snapshot.counter == 20


def test_options_flow_does_not_assign_home_assistant_config_entry_property() -> None:
    flow = ReadOnlyConfigEntryOptionsFlow(FakeEntry())

    assert flow._current_options()[CONF_ANALYSIS_RADIUS_KM] == 40


def test_coordinator_still_honors_existing_entry_data_and_options_keys() -> None:
    coordinator = StormDetectorCoordinator(
        FakeHass(),
        None,
        "Storm Detector",
        FakeEntry(),
        session_factory=FakeSessionContext,
    )

    config = coordinator._effective_config()
    assert config[CONF_ANALYSIS_RADIUS_KM] == 40
    assert config[CONF_RAINVIEWER_FRAMES] == 2


@pytest.mark.asyncio
async def test_options_flow_uses_existing_options_as_defaults() -> None:
    flow = StormDetectorOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init()

    schema = result["data_schema"]
    assert _schema_default(schema, CONF_ANALYSIS_RADIUS_KM) == 40
    assert _schema_default(schema, CONF_RAINVIEWER_FRAMES) == 2
    assert _schema_default(schema, CONF_RAINVIEWER_FRAMES) != DEFAULT_RAINVIEWER_FRAMES


@pytest.mark.asyncio
async def test_options_flow_only_exposes_advanced_fields_and_preserves_hidden_sources() -> None:
    flow = StormDetectorOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init()

    schema = result["data_schema"]
    assert _schema_fields(schema) == {
        CONF_LIGHTNING_AZIMUTH_ENTITY_ID,
        *OPTIONAL_CONF_DEFAULTS,
    }

    saved = await flow.async_step_init({CONF_ANALYSIS_RADIUS_KM: 60})
    assert saved["data"][CONF_LIGHTNING_DISTANCE_ENTITY_ID] == "sensor.lightning_distance"
    assert saved["data"][CONF_LIGHTNING_COUNTER_ENTITY_ID] == "sensor.lightning_count"


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
    assert _validate_parameter_ranges({CONF_MIN_CORE_PIXELS: 0}) == {
        CONF_MIN_CORE_PIXELS: "invalid_range"
    }


@pytest.mark.asyncio
async def test_options_flow_sets_min_core_pixels_with_defaults_and_range() -> None:
    flow = StormDetectorOptionsFlowHandler(FakeEntry())

    assert flow._current_options()[CONF_MIN_CORE_PIXELS] == DEFAULT_MIN_CORE_PIXELS

    result = await flow.async_step_init({CONF_MIN_CORE_PIXELS: DEFAULT_MIN_CORE_PIXELS + 1})
    assert result["title"] == "Storm Detector"
    assert result["data"][CONF_MIN_CORE_PIXELS] == DEFAULT_MIN_CORE_PIXELS + 1


@pytest.mark.asyncio
async def test_options_flow_rejects_invalid_parameter_ranges() -> None:
    flow = StormDetectorOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init({CONF_ANALYSIS_RADIUS_KM: 5})

    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_ANALYSIS_RADIUS_KM: "invalid_range"}


@pytest.mark.asyncio
async def test_options_flow_coerces_numeric_strings_before_saving() -> None:
    flow = StormDetectorOptionsFlowHandler(FakeEntry())

    result = await flow.async_step_init({CONF_ANALYSIS_RADIUS_KM: "60"})

    assert result["title"] == "Storm Detector"
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
        "custom_components.storm_detector.coordinator.fetch_radar_metadata",
        _broken_meta,
    ):
        coordinator = StormDetectorCoordinator(
            hass,
            None,
            "Storm Detector",
            FakeEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload["level"] == RISK_LEVEL_WARNING
    assert payload[ATTR_EVIDENCE_KIND] == EVIDENCE_KIND_LIGHTNING_ONLY
    assert payload[ATTR_LIGHTNING_DISTANCE_KM] == 4.5
    assert payload[ATTR_STALE] is True
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
        "custom_components.storm_detector.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.storm_detector.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.storm_detector.coordinator.analyze_recent_frames",
        _fake_analysis,
    ):
        coordinator = StormDetectorCoordinator(
            hass,
            None,
            "Storm Detector",
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

    coordinator = StormDetectorCoordinator(
        hass,
        None,
        "Storm Detector",
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
        "custom_components.storm_detector.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.storm_detector.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.storm_detector.coordinator.analyze_recent_frames",
        _fake_analysis,
    ):
        coordinator = StormDetectorCoordinator(
            hass,
            None,
            "Storm Detector",
            RadarOnlyEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload[ATTR_SOURCE_STATUS]["lightning"] == "not_configured"
    assert payload[ATTR_LIGHTNING_DIAGNOSTICS] == ("lightning_not_configured",)
    assert "lightning_not_configured" not in payload[ATTR_DEGRADATION_REASONS]
