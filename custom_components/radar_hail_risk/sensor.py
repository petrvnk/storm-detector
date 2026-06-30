"""Sensor entities for radar hail risk."""

from __future__ import annotations

from typing import Any

from .const import (
    ATTR_CORE_DISTANCE_KM,
    ATTR_FRAME_AGE_SECONDS,
    ATTR_FRAME_TIME,
    ATTR_FRAMES_ANALYZED,
    ATTR_LAST_ERROR,
    ATTR_LIGHTNING_COUNTER_DELTA,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LIGHTNING_TRIGGERED,
    ATTR_MAX_DBZ,
    ATTR_SELECTED_CORE_DISTANCE_KM,
    ATTR_SELECTED_CORE_LATITUDE,
    ATTR_SELECTED_CORE_LONGITUDE,
    ATTR_SELECTED_CORE_THRESHOLD_DBZ,
    ATTR_STALE,
    ATTR_SUMMARY,
    DATA_KEY_RESULT,
    DOMAIN,
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
        return f"Radar Hail Risk {self._title}"

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
            ATTR_SELECTED_CORE_DISTANCE_KM: data.get(ATTR_SELECTED_CORE_DISTANCE_KM),
            ATTR_SELECTED_CORE_LATITUDE: data.get(ATTR_SELECTED_CORE_LATITUDE),
            ATTR_SELECTED_CORE_LONGITUDE: data.get(ATTR_SELECTED_CORE_LONGITUDE),
            ATTR_SELECTED_CORE_THRESHOLD_DBZ: data.get(ATTR_SELECTED_CORE_THRESHOLD_DBZ),
            ATTR_LIGHTNING_TRIGGERED: bool(data.get(ATTR_LIGHTNING_TRIGGERED, False)),
            ATTR_LIGHTNING_COUNTER_DELTA: data.get(ATTR_LIGHTNING_COUNTER_DELTA),
            ATTR_LIGHTNING_DISTANCE_KM: data.get(ATTR_LIGHTNING_DISTANCE_KM),
            ATTR_FRAME_AGE_SECONDS: data.get(ATTR_FRAME_AGE_SECONDS),
            ATTR_FRAME_TIME: data.get(ATTR_FRAME_TIME),
            ATTR_FRAMES_ANALYZED: data.get(ATTR_FRAMES_ANALYZED),
        }


class RadarHailRiskLevelSensor(RadarHailRiskSensorBase):
    """Overall hail risk level."""

    _attr_icon = "mdi:weather-lightning"

    def __init__(self, coordinator: Any, config_entry: Any) -> None:
        super().__init__(coordinator, config_entry, key="level", title="Level")

    @property
    def icon(self) -> str:
        level = self.native_value
        if level == "urgent":
            return "mdi:alert-decagram"
        if level in {"warning", "watch"}:
            return "mdi:alert"
        return "mdi:check-decagram"


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
