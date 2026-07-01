"""Stage 5 coordinator and entity behavior tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.radar_hail_risk.binary_sensor import (
    RadarHailDataStaleBinarySensor,
    RadarHailRiskActiveBinarySensor,
)
from custom_components.radar_hail_risk.const import (
    ATTR_FRAME_AGE_SECONDS,
    ATTR_LAST_ERROR,
    ATTR_LIGHTNING_COUNTER_DELTA,
    ATTR_LIGHTNING_DIAGNOSTICS,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LIGHTNING_TRIGGERED,
    ATTR_MAX_DBZ,
    ATTR_SELECTED_CORE_LATITUDE,
    ATTR_SELECTED_CORE_LONGITUDE,
    ATTR_SELECTED_CORE_THRESHOLD_DBZ,
    ATTR_STALE,
    ATTR_SUMMARY,
    DEFAULT_STALE_CLEAR_SECONDS,
    DOMAIN,
    RISK_LEVEL_NONE,
    RISK_LEVEL_UNAVAILABLE,
    RISK_LEVEL_WARNING,
)
from custom_components.radar_hail_risk.coordinator import RadarHailRiskCoordinator
from custom_components.radar_hail_risk.device_tracker import RadarHailStormCoreTracker
from custom_components.radar_hail_risk.sensor import RadarHailRiskLevelSensor


class FakeHass:
    def __init__(self) -> None:
        self.config = SimpleNamespace(latitude=50.0755, longitude=14.4378)
        self._states: dict[str, SimpleNamespace] = {}

    @property
    def states(self) -> SimpleNamespace:
        return SimpleNamespace(get=self._states.get, async_all=lambda: list(self._states.values()))

    def set_state(self, entity_id: str, value: str, *, last_updated: datetime) -> None:
        self._states[entity_id] = SimpleNamespace(
            entity_id=entity_id,
            state=value,
            last_updated=last_updated,
            attributes={},
        )


class FakeSessionContext:
    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> "FakeSessionContext":
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.closed = True


class FakeEntry:
    entry_id = "entry-stage5"
    data = {
        "lightning_distance_entity_id": "sensor.lightning_distance",
        "lightning_counter_entity_id": "sensor.lightning_count",
    }
    options = {}


class FakeRadarOnlyEntry:
    entry_id = "entry-radar-only"
    data = {}
    options = {}


def _analysis_payload():
    return SimpleNamespace(
        max_dbz=56,
        selected_core_threshold_dbz=55,
        selected_core_distance_km=6.2,
        selected_core_latitude=50.1,
        selected_core_longitude=14.5,
        frame_age_seconds=120,
        frame_time=1710000000,
        frames_analyzed=4,
    )


async def test_coordinator_payload_includes_risk_summary_and_entities() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_state("sensor.lightning_distance", "4.5", last_updated=now - timedelta(minutes=2))
    hass.set_state("sensor.lightning_count", "12", last_updated=now - timedelta(minutes=2))

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {}

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        lambda *_args, **_kwargs: _analysis_payload(),
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
    assert payload[ATTR_MAX_DBZ] == 56
    assert payload[ATTR_SELECTED_CORE_THRESHOLD_DBZ] == 55
    assert payload[ATTR_LIGHTNING_DISTANCE_KM] == 4.5
    assert payload[ATTR_LIGHTNING_TRIGGERED] is True
    assert payload[ATTR_LIGHTNING_COUNTER_DELTA] is None
    assert payload[ATTR_FRAME_AGE_SECONDS] == 120
    assert payload[ATTR_STALE] is False
    assert payload[ATTR_SUMMARY].startswith("Warning")
    assert payload[ATTR_SELECTED_CORE_LATITUDE] == 50.1
    assert payload[ATTR_SELECTED_CORE_LONGITUDE] == 14.5

    level_sensor = RadarHailRiskLevelSensor(coordinator, FakeEntry())
    coordinator.data = payload
    level_sensor._coordinator = coordinator
    assert level_sensor.unique_id == f"{DOMAIN}_entry-stage5_level"
    assert level_sensor.native_value == RISK_LEVEL_WARNING
    attrs = level_sensor.extra_state_attributes
    assert attrs[ATTR_LIGHTNING_DISTANCE_KM] == 4.5

    stale_bin = RadarHailDataStaleBinarySensor(coordinator, FakeEntry())
    stale_bin._coordinator = coordinator
    assert stale_bin.is_on is False

    active_bin = RadarHailRiskActiveBinarySensor(coordinator, FakeEntry())
    active_bin._coordinator = coordinator
    assert active_bin.is_on is True

    tracker = RadarHailStormCoreTracker(coordinator, FakeEntry())
    tracker._coordinator = coordinator
    assert tracker.unique_id == f"{DOMAIN}_entry-stage5_storm_core"
    assert tracker.latitude == 50.1
    assert tracker.longitude == 14.5


async def test_stale_lightning_is_not_used_in_urgent_risk_summary() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=DEFAULT_STALE_CLEAR_SECONDS + 10)
    hass.set_state("sensor.lightning_distance", "17.5", last_updated=stale_time)
    hass.set_state("sensor.lightning_count", "25", last_updated=stale_time)

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {"#ffffff": 0}

    urgent_radar = SimpleNamespace(
        max_dbz=60,
        selected_core_threshold_dbz=55,
        selected_core_distance_km=34.8,
        selected_core_latitude=50.1,
        selected_core_longitude=14.5,
        frame_age_seconds=180,
        frame_time=1710000000,
        frames_analyzed=4,
    )

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        lambda *_args, **_kwargs: urgent_radar,
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            FakeEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload["level"] == "urgent"
    assert payload[ATTR_LIGHTNING_DISTANCE_KM] is None
    assert payload[ATTR_LIGHTNING_TRIGGERED] is False
    assert payload[ATTR_LAST_ERROR] is None
    assert payload[ATTR_SUMMARY] == "Urgent risk"
    assert "stale_distance_entity" in payload[ATTR_LIGHTNING_DIAGNOSTICS]
    assert "stale_counter_entity" in payload[ATTR_LIGHTNING_DIAGNOSTICS]


async def test_coordinator_without_coordinates_is_unavailable() -> None:
    hass = FakeHass()
    hass.config = SimpleNamespace(latitude=None, longitude=None)

    coordinator = RadarHailRiskCoordinator(hass, None, "Radar Hail Risk", FakeEntry())
    payload = await coordinator._async_update_data()

    assert payload["level"] == RISK_LEVEL_UNAVAILABLE
    assert payload["diagnostics"] == ["missing_hass_location"]
    assert payload[ATTR_STALE] is True


async def test_coordinator_autodetects_blitzortung_like_lightning_entities() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_state("sensor.home_lightning_distance", "12", last_updated=now)
    hass.set_state("sensor.home_lightning_counter", "7", last_updated=now)

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {}

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        lambda *_args, **_kwargs: _analysis_payload(),
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            FakeRadarOnlyEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload[ATTR_LIGHTNING_DISTANCE_KM] == 12
    assert payload[ATTR_LIGHTNING_TRIGGERED] is True
    assert "lightning_not_configured" not in payload[ATTR_SUMMARY]


async def test_radar_only_mode_does_not_surface_lightning_not_configured_as_error() -> None:
    hass = FakeHass()

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {}

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        lambda *_args, **_kwargs: _analysis_payload(),
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            FakeRadarOnlyEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload[ATTR_LIGHTNING_DISTANCE_KM] is None
    assert payload["lightning_diagnostics"] == ("lightning_not_configured",)
    assert "lightning_not_configured" not in payload[ATTR_SUMMARY]
    assert payload[ATTR_LAST_ERROR] is None or "lightning_not_configured" not in payload[ATTR_LAST_ERROR]


async def test_none_level_classifies_stable_none() -> None:
    hass = FakeHass()
    now = datetime.now(timezone.utc)
    hass.set_state("sensor.lightning_distance", "250", last_updated=now)
    hass.set_state("sensor.lightning_count", "5", last_updated=now)

    async def _fake_meta(*_args: object, **_kwargs: object):
        return {"radar": {"past": []}, "host": "https://tilecache.rainviewer.com"}

    async def _fake_color(*_args: object, **_kwargs: object):
        return {}

    analysis = SimpleNamespace(
        max_dbz=45,
        selected_core_threshold_dbz=55,
        selected_core_distance_km=999,
        selected_core_latitude=None,
        selected_core_longitude=None,
        frame_age_seconds=10,
        frame_time=1710000000,
        frames_analyzed=3,
    )

    with patch(
        "custom_components.radar_hail_risk.coordinator.fetch_radar_metadata",
        _fake_meta,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.radar_hail_risk.coordinator.analyze_recent_frames",
        lambda *_args, **_kwargs: analysis,
    ):
        coordinator = RadarHailRiskCoordinator(
            hass,
            None,
            "Radar Hail Risk",
            FakeEntry(),
            session_factory=FakeSessionContext,
        )
        payload = await coordinator._async_update_data()

    assert payload["level"] == RISK_LEVEL_NONE
    assert payload["selected_core_distance_km"] == 999
    assert payload[ATTR_LIGHTNING_TRIGGERED] is False
    assert payload[ATTR_LIGHTNING_COUNTER_DELTA] == 0
