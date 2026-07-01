"""Sensor entities for radar hail risk."""

from __future__ import annotations

from typing import Any

from .const import (
    ATTR_CONFIDENCE_LEVEL,
    ATTR_CONFIDENCE_SCORE,
    ATTR_CORE50_DISTANCE_KM,
    ATTR_CORE55_DISTANCE_KM,
    ATTR_CORE60_DISTANCE_KM,
    ATTR_CORE_COUNT,
    ATTR_CORE_DISTANCE_KM,
    ATTR_DBZ_TREND,
    ATTR_DEGRADATION_REASONS,
    ATTR_DISTANCE_TREND,
    ATTR_FRAME_AGE_SECONDS,
    ATTR_FRAME_TIME,
    ATTR_FRAMES_ANALYZED,
    ATTR_LAST_ERROR,
    ATTR_LIGHTNING_AZIMUTH_DEGREES,
    ATTR_LIGHTNING_CORE_DISTANCE_KM,
    ATTR_LIGHTNING_COUNTER_DELTA,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LIGHTNING_LATITUDE,
    ATTR_LIGHTNING_LONGITUDE,
    ATTR_LIGHTNING_TRIGGERED,
    ATTR_LOCATION_SOURCE,
    ATTR_MAX_DBZ,
    ATTR_SELECTED_CORE_AREA_KM2,
    ATTR_SELECTED_CORE_DISTANCE_KM,
    ATTR_SELECTED_CORE_LATITUDE,
    ATTR_SELECTED_CORE_LONGITUDE,
    ATTR_SELECTED_CORE_MAX_DBZ,
    ATTR_SELECTED_CORE_PIXEL_COUNT,
    ATTR_SELECTED_CORE_THRESHOLD_DBZ,
    ATTR_SOURCE_STATUS,
    ATTR_STALE,
    ATTR_STORM_APPROACHING,
    ATTR_STORM_ETA_MINUTES,
    ATTR_STORM_MOTION_BEARING,
    ATTR_STORM_MOTION_SPEED_KMH,
    ATTR_SUMMARY,
    DATA_KEY_RESULT,
    DOMAIN,
    RISK_LEVEL_NONE,
    RISK_LEVEL_UNAVAILABLE,
    RISK_LEVEL_URGENT,
    RISK_LEVEL_WARNING,
    RISK_LEVEL_WATCH,
)
from .ha_fallback import FallbackCoordinatorEntity, FallbackEntity

try:  # pragma: no cover
    from homeassistant.components.sensor import SensorEntity
    from homeassistant.const import UnitOfLength
    from homeassistant.helpers.entity import DeviceInfo
    from homeassistant.helpers.update_coordinator import CoordinatorEntity
except Exception:  # pragma: no cover
    SensorEntity = FallbackEntity
    DeviceInfo = dict  # type: ignore[assignment]
    UnitOfLength = type("_Units", (), {"KILOMETERS": "km"})()
    CoordinatorEntity = FallbackCoordinatorEntity


async def async_setup_entry(hass: Any, config_entry: Any, async_add_entities: Any) -> None:
    """Register entities for this config entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_KEY_RESULT]
    async_add_entities(
        [
            RadarHailRiskLevelSensor(coordinator, config_entry),
            RadarHailRiskSummarySensor(coordinator, config_entry),
            RadarHailRiskMaxDbzSensor(coordinator, config_entry),
            RadarHailRiskCoreDistanceSensor(coordinator, config_entry),
            RadarHailRiskLightningDistanceSensor(coordinator, config_entry),
            RadarHailRiskFrameAgeSensor(coordinator, config_entry),
            RadarHailRiskLastErrorSensor(coordinator, config_entry),
        ]
    )


class RadarHailRiskSensorBase(CoordinatorEntity[Any], SensorEntity):
    """Common helpers shared by all risk sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, config_entry: Any, *, key: str, title: str, unit: str | None = None) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._key = key
        self._title = title
        self._unit = unit
        self._entry_id = getattr(config_entry, "entry_id", "default")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_{self._key}"

    @property
    def name(self) -> str:
        return self._title

    @property
    def device_info(self) -> DeviceInfo:
        if isinstance(DeviceInfo, type):
            return DeviceInfo(
                identifiers={(DOMAIN, self._entry_id)},
                name="Radar Hail Risk",
                manufacturer="Radar Hail Risk Integration",
                model="Risk Monitor",
            )
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Radar Hail Risk",
            "manufacturer": "Radar Hail Risk Integration",
            "model": "Risk Monitor",
        }

    @property
    def native_value(self) -> Any:
        data = self._coordinator.data or {}
        return data.get(self._key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data or {}
        return {
            ATTR_SUMMARY: data.get(ATTR_SUMMARY),
            ATTR_STALE: bool(data.get(ATTR_STALE, False)),
            ATTR_CORE50_DISTANCE_KM: data.get(ATTR_CORE50_DISTANCE_KM),
            ATTR_CORE55_DISTANCE_KM: data.get(ATTR_CORE55_DISTANCE_KM),
            ATTR_CORE60_DISTANCE_KM: data.get(ATTR_CORE60_DISTANCE_KM),
            ATTR_SELECTED_CORE_DISTANCE_KM: data.get(ATTR_SELECTED_CORE_DISTANCE_KM),
            ATTR_SELECTED_CORE_AREA_KM2: data.get(ATTR_SELECTED_CORE_AREA_KM2),
            ATTR_SELECTED_CORE_PIXEL_COUNT: data.get(ATTR_SELECTED_CORE_PIXEL_COUNT),
            ATTR_SELECTED_CORE_MAX_DBZ: data.get(ATTR_SELECTED_CORE_MAX_DBZ),
            ATTR_CORE_COUNT: data.get(ATTR_CORE_COUNT),
            ATTR_SELECTED_CORE_LATITUDE: data.get(ATTR_SELECTED_CORE_LATITUDE),
            ATTR_SELECTED_CORE_LONGITUDE: data.get(ATTR_SELECTED_CORE_LONGITUDE),
            ATTR_SELECTED_CORE_THRESHOLD_DBZ: data.get(ATTR_SELECTED_CORE_THRESHOLD_DBZ),
            ATTR_STORM_MOTION_BEARING: data.get(ATTR_STORM_MOTION_BEARING),
            ATTR_STORM_MOTION_SPEED_KMH: data.get(ATTR_STORM_MOTION_SPEED_KMH),
            ATTR_STORM_APPROACHING: data.get(ATTR_STORM_APPROACHING),
            ATTR_STORM_ETA_MINUTES: data.get(ATTR_STORM_ETA_MINUTES),
            ATTR_DBZ_TREND: data.get(ATTR_DBZ_TREND),
            ATTR_DISTANCE_TREND: data.get(ATTR_DISTANCE_TREND),
            ATTR_CONFIDENCE_SCORE: data.get(ATTR_CONFIDENCE_SCORE),
            ATTR_CONFIDENCE_LEVEL: data.get(ATTR_CONFIDENCE_LEVEL),
            ATTR_LIGHTNING_TRIGGERED: bool(data.get(ATTR_LIGHTNING_TRIGGERED, False)),
            ATTR_LIGHTNING_COUNTER_DELTA: data.get(ATTR_LIGHTNING_COUNTER_DELTA),
            ATTR_LIGHTNING_DISTANCE_KM: data.get(ATTR_LIGHTNING_DISTANCE_KM),
            ATTR_LIGHTNING_AZIMUTH_DEGREES: data.get(ATTR_LIGHTNING_AZIMUTH_DEGREES),
            ATTR_LIGHTNING_LATITUDE: data.get(ATTR_LIGHTNING_LATITUDE),
            ATTR_LIGHTNING_LONGITUDE: data.get(ATTR_LIGHTNING_LONGITUDE),
            ATTR_LIGHTNING_CORE_DISTANCE_KM: data.get(ATTR_LIGHTNING_CORE_DISTANCE_KM),
            ATTR_FRAME_AGE_SECONDS: data.get(ATTR_FRAME_AGE_SECONDS),
            ATTR_FRAME_TIME: data.get(ATTR_FRAME_TIME),
            ATTR_FRAMES_ANALYZED: data.get(ATTR_FRAMES_ANALYZED),
            ATTR_LOCATION_SOURCE: data.get(ATTR_LOCATION_SOURCE),
            ATTR_SOURCE_STATUS: data.get(ATTR_SOURCE_STATUS),
            ATTR_DEGRADATION_REASONS: data.get(ATTR_DEGRADATION_REASONS),
        }


class RadarHailRiskLevelSensor(RadarHailRiskSensorBase):
    """Overall hail risk level."""

    _attr_icon = "mdi:weather-lightning"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(coordinator, config_entry, key="level", title="Level")

    @property
    def icon(self) -> str:
        level = self.native_value
        if level == RISK_LEVEL_URGENT:
            return "mdi:alert-decagram"
        if level in {RISK_LEVEL_WARNING, RISK_LEVEL_WATCH}:
            return "mdi:alert"
        if level == RISK_LEVEL_UNAVAILABLE or bool(
            (self._coordinator.data or {}).get(ATTR_STALE, False)
        ):
            return "mdi:alert-circle-outline"
        if level == RISK_LEVEL_NONE:
            return "mdi:check-decagram"
        return "mdi:help-circle-outline"


class RadarHailRiskSummarySensor(RadarHailRiskSensorBase):
    """One-line summary text generated by coordinator."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(coordinator, config_entry, key=ATTR_SUMMARY, title="Summary")


class RadarHailRiskMaxDbzSensor(RadarHailRiskSensorBase):
    """Maximum detected DBZ from selected core."""

    _attr_icon = "mdi:radar"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(coordinator, config_entry, key=ATTR_MAX_DBZ, title="Max dBZ", unit="dBZ")


class RadarHailRiskCoreDistanceSensor(RadarHailRiskSensorBase):
    """Distance to selected core."""

    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(
            coordinator,
            config_entry,
            key=ATTR_CORE_DISTANCE_KM,
            title="Core Distance",
            unit=UnitOfLength.KILOMETERS,
        )


class RadarHailRiskLightningDistanceSensor(RadarHailRiskSensorBase):
    """Distance to last valid lightning point."""

    _attr_icon = "mdi:flash"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(
            coordinator,
            config_entry,
            key=ATTR_LIGHTNING_DISTANCE_KM,
            title="Lightning Distance",
            unit=UnitOfLength.KILOMETERS,
        )


class RadarHailRiskFrameAgeSensor(RadarHailRiskSensorBase):
    """Age of evaluated frame (seconds)."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(
            coordinator,
            config_entry,
            key=ATTR_FRAME_AGE_SECONDS,
            title="Frame Age",
            unit="s",
        )


class RadarHailRiskLastErrorSensor(RadarHailRiskSensorBase):
    """Textual update error status."""

    _attr_icon = "mdi:bug"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(coordinator, config_entry, key=ATTR_LAST_ERROR, title="Last Error")
