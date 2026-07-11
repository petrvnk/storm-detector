"""Device tracker for selected hail-risk core position."""

from __future__ import annotations

from typing import Any

from .const import (
    ATTR_SELECTED_CORE_LATITUDE,
    ATTR_SELECTED_CORE_LONGITUDE,
    DATA_KEY_RESULT,
    DOMAIN,
)
from .ha_fallback import FallbackCoordinatorEntity, FallbackEntity

try:  # pragma: no cover
    from homeassistant.components.device_tracker import TrackerEntity
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
    from homeassistant.helpers.entity import DeviceInfo, EntityCategory
    from homeassistant.helpers.update_coordinator import CoordinatorEntity
    SOURCE_TYPE_GPS = "gps"
except Exception:  # pragma: no cover
    TrackerEntity = FallbackEntity
    DeviceInfo = dict  # type: ignore[assignment]
    SOURCE_TYPE_GPS = "gps"
    ConfigEntry = Any
    ATTR_LATITUDE = "latitude"
    ATTR_LONGITUDE = "longitude"
    CoordinatorEntity = FallbackCoordinatorEntity
    class EntityCategory:  # type: ignore[no-redef]
        DIAGNOSTIC = "diagnostic"


async def async_setup_entry(hass: Any, config_entry: ConfigEntry, async_add_entities: Any) -> None:
    """Register core tracker entity."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_KEY_RESULT]
    async_add_entities([RadarHailStormCoreTracker(coordinator, config_entry)])


class RadarHailStormCoreTracker(CoordinatorEntity[Any], TrackerEntity):
    """Expose the nearest detected hail core position for map rendering."""

    _attr_has_entity_name = True
    _attr_name = "Storm Core"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: Any | None = None, config_entry: ConfigEntry | None = None) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._entry_id = getattr(config_entry, "entry_id", "default")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_storm_core"

    @property
    def source_type(self) -> str:
        return SOURCE_TYPE_GPS

    @property
    def latitude(self) -> float | None:
        data = self._coordinator.data if getattr(self, "coordinator", None) else {}
        if not isinstance(data, dict):
            return None
        lat = data.get(ATTR_SELECTED_CORE_LATITUDE)
        return float(lat) if isinstance(lat, (int, float)) else None

    @property
    def longitude(self) -> float | None:
        data = self._coordinator.data if getattr(self, "coordinator", None) else {}
        if not isinstance(data, dict):
            return None
        lon = data.get(ATTR_SELECTED_CORE_LONGITUDE)
        return float(lon) if isinstance(lon, (int, float)) else None

    @property
    def battery_level(self) -> int:
        return 100

    @property
    def icon(self) -> str:
        return "mdi:map-marker-star"

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
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data if getattr(self, "coordinator", None) else {}
        if not isinstance(data, dict):
            return {}
        return {
            ATTR_LATITUDE: self.latitude,
            ATTR_LONGITUDE: self.longitude,
            "selected_core_distance_km": data.get("selected_core_distance_km"),
            "selected_core_threshold_dbz": data.get("selected_core_threshold_dbz"),
        }
