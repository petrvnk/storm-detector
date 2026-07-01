"""Binary sensors for radar hail risk."""

from __future__ import annotations

from typing import Any

from .const import (
    ATTR_LEVEL,
    ATTR_LIGHTNING_TRIGGERED,
    ATTR_STALE,
    DATA_KEY_RESULT,
    DOMAIN,
    RISK_LEVEL_NONE,
    RISK_LEVEL_UNAVAILABLE,
)
from .ha_fallback import FallbackCoordinatorEntity, FallbackEntity

try:  # pragma: no cover
    from homeassistant.components.binary_sensor import BinarySensorEntity
    from homeassistant.helpers.entity import DeviceInfo
    from homeassistant.helpers.update_coordinator import CoordinatorEntity
except Exception:  # pragma: no cover
    BinarySensorEntity = FallbackEntity
    CoordinatorEntity = FallbackCoordinatorEntity
    DeviceInfo = dict  # type: ignore[assignment]


async def async_setup_entry(hass: Any, config_entry: Any, async_add_entities: Any) -> None:
    """Register binary entities for this entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_KEY_RESULT]
    async_add_entities(
        [
            RadarHailDataStaleBinarySensor(coordinator, config_entry),
            RadarHailRiskActiveBinarySensor(coordinator, config_entry),
        ]
    )


class RadarHailDataStaleBinarySensor(CoordinatorEntity[Any], BinarySensorEntity):
    """Reports whether source data is stale."""

    _attr_has_entity_name = True
    _attr_name = "Data Stale"
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, coordinator: Any | None = None, config_entry: Any | None = None) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._entry_id = getattr(config_entry, "entry_id", "default")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_data_stale"

    @property
    def is_on(self) -> bool:
        data = self._coordinator.data if getattr(self, "coordinator", None) else {}
        if isinstance(data, dict):
            return bool(data.get(ATTR_STALE, False))
        return False

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


class RadarHailRiskActiveBinarySensor(CoordinatorEntity[Any], BinarySensorEntity):
    """True when risk is at least watch level and not stale/unavailable."""

    _attr_has_entity_name = True
    _attr_name = "Active"
    _attr_icon = "mdi:weather-hail"

    def __init__(self, coordinator: Any | None = None, config_entry: Any | None = None) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._entry_id = getattr(config_entry, "entry_id", "default")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_risk_active"

    @property
    def is_on(self) -> bool:
        data = self._coordinator.data if getattr(self, "coordinator", None) else {}
        if not isinstance(data, dict):
            return False
        level = data.get(ATTR_LEVEL)
        if level in (RISK_LEVEL_NONE, RISK_LEVEL_UNAVAILABLE):
            return False
        if bool(data.get(ATTR_STALE, False)) and level in (RISK_LEVEL_NONE, RISK_LEVEL_UNAVAILABLE):
            return False
        return level is not None

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
            ATTR_LIGHTNING_TRIGGERED: bool(data.get(ATTR_LIGHTNING_TRIGGERED, False)),
            ATTR_LEVEL: data.get(ATTR_LEVEL),
            ATTR_STALE: bool(data.get(ATTR_STALE, False)),
        }
