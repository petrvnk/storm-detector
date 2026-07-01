"""Config and options flow for radar_hail_risk."""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - imported in HA runtime only.
    import voluptuous as vol
    from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
    from homeassistant.data_entry_flow import FlowResult
    from homeassistant.helpers import selector
except Exception:  # pragma: no cover - local static/test environment only.
    from .ha_fallback import FallbackConfigFlow, FallbackOptionsFlow

    vol = None  # type: ignore[assignment]
    ConfigEntry = Any  # type: ignore[assignment]
    ConfigFlow = FallbackConfigFlow
    OptionsFlow = FallbackOptionsFlow
    FlowResult = dict[str, Any]

    class selector:  # pragma: no cover
        class EntitySelector:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        class EntitySelectorConfig:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

from .const import (
    CONF_ANALYSIS_RADIUS_KM,
    CONF_CORE_URGENT_DBZ,
    CONF_CORE_WARNING_DBZ,
    CONF_CORE_WATCH_DBZ,
    CONF_LIGHTNING_AZIMUTH_ENTITY_ID,
    CONF_LIGHTNING_COUNTER_ENTITY_ID,
    CONF_LIGHTNING_DISTANCE_ENTITY_ID,
    CONF_LIGHTNING_TRIGGER_RADIUS_KM,
    CONF_LOCATION_ENTITY_ID,
    CONF_MIN_ANALYSIS_INTERVAL_SECONDS,
    CONF_RAINVIEWER_FRAMES,
    CONF_RAINVIEWER_ZOOM,
    CONF_STALE_CLEAR_SECONDS,
    CONF_URGENT_CORE_DISTANCE_KM,
    CONF_URGENT_LIGHTNING_DISTANCE_KM,
    CONF_WARNING_CORE_DISTANCE_KM,
    CONF_WARNING_LIGHTNING_DISTANCE_KM,
    DEFAULT_ANALYSIS_RADIUS_KM,
    DEFAULT_CORE_URGENT_DBZ,
    DEFAULT_CORE_WARNING_DBZ,
    DEFAULT_CORE_WATCH_DBZ,
    DEFAULT_LIGHTNING_TRIGGER_RADIUS_KM,
    DEFAULT_MIN_ANALYSIS_INTERVAL_SECONDS,
    DEFAULT_RAINVIEWER_FRAMES,
    DEFAULT_RAINVIEWER_ZOOM,
    DEFAULT_STALE_CLEAR_SECONDS,
    DEFAULT_URGENT_CORE_DISTANCE_KM,
    DEFAULT_URGENT_LIGHTNING_DISTANCE_KM,
    DEFAULT_WARNING_CORE_DISTANCE_KM,
    DEFAULT_WARNING_LIGHTNING_DISTANCE_KM,
    DOMAIN,
    OPTIONAL_CONF_DEFAULTS,
)
from .lightning import autodetect_blitzortung_entities


class RadarHailRiskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for adding the integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial user step."""

        if user_input is not None:
            user_input = _clean_optional_entity_ids(user_input)
            if _has_partial_lightning_config(user_input):
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(self._base_schema()) if vol else dict,
                    errors={"base": "lightning_pair_required"},
                )
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Radar Hail Risk", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self._base_schema()) if vol else dict,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> "RadarHailRiskOptionsFlowHandler":
        """Return the options flow handler for this config entry."""

        return RadarHailRiskOptionsFlowHandler(config_entry)

    def _base_schema(self) -> dict[str, Any]:
        """Return the setup schema with optional autodetected Blitzortung sensors."""

        candidates = autodetect_blitzortung_entities(_iter_hass_states(getattr(self, "hass", None)))

        if not vol:
            return {
                CONF_LOCATION_ENTITY_ID: "",
                CONF_LIGHTNING_DISTANCE_ENTITY_ID: candidates.distance_entity_id or str,
                CONF_LIGHTNING_COUNTER_ENTITY_ID: candidates.counter_entity_id or str,
                CONF_LIGHTNING_AZIMUTH_ENTITY_ID: candidates.azimuth_entity_id or str,
                **OPTIONAL_CONF_DEFAULTS,
            }

        return {
            _optional_entity_key(CONF_LOCATION_ENTITY_ID, None): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["zone", "person", "device_tracker"], multiple=False
                )
            ),
            _optional_entity_key(
                CONF_LIGHTNING_DISTANCE_ENTITY_ID, candidates.distance_entity_id
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="distance", multiple=False
                )
            ),
            _optional_entity_key(
                CONF_LIGHTNING_COUNTER_ENTITY_ID, candidates.counter_entity_id
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=False)
            ),
            _optional_entity_key(
                CONF_LIGHTNING_AZIMUTH_ENTITY_ID, candidates.azimuth_entity_id
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=False)
            ),
            vol.Optional(
                CONF_ANALYSIS_RADIUS_KM,
                default=DEFAULT_ANALYSIS_RADIUS_KM,
            ): int,
            vol.Optional(
                CONF_LIGHTNING_TRIGGER_RADIUS_KM,
                default=DEFAULT_LIGHTNING_TRIGGER_RADIUS_KM,
            ): int,
            vol.Optional(
                CONF_WARNING_LIGHTNING_DISTANCE_KM,
                default=DEFAULT_WARNING_LIGHTNING_DISTANCE_KM,
            ): int,
            vol.Optional(
                CONF_URGENT_LIGHTNING_DISTANCE_KM,
                default=DEFAULT_URGENT_LIGHTNING_DISTANCE_KM,
            ): int,
            vol.Optional(CONF_CORE_WATCH_DBZ, default=DEFAULT_CORE_WATCH_DBZ): int,
            vol.Optional(CONF_CORE_WARNING_DBZ, default=DEFAULT_CORE_WARNING_DBZ): int,
            vol.Optional(CONF_CORE_URGENT_DBZ, default=DEFAULT_CORE_URGENT_DBZ): int,
            vol.Optional(
                CONF_MIN_ANALYSIS_INTERVAL_SECONDS,
                default=DEFAULT_MIN_ANALYSIS_INTERVAL_SECONDS,
            ): int,
            vol.Optional(CONF_STALE_CLEAR_SECONDS, default=DEFAULT_STALE_CLEAR_SECONDS): int,
            vol.Optional(CONF_RAINVIEWER_ZOOM, default=DEFAULT_RAINVIEWER_ZOOM): int,
            vol.Optional(CONF_RAINVIEWER_FRAMES, default=DEFAULT_RAINVIEWER_FRAMES): int,
            vol.Optional(
                CONF_WARNING_CORE_DISTANCE_KM,
                default=DEFAULT_WARNING_CORE_DISTANCE_KM,
            ): int,
            vol.Optional(CONF_URGENT_CORE_DISTANCE_KM, default=DEFAULT_URGENT_CORE_DISTANCE_KM): int,
        }


class RadarHailRiskOptionsFlowHandler(OptionsFlow):
    """Options flow for post-setup thresholds and lightning source selection."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options updates."""

        if user_input is not None:
            user_input = _clean_optional_entity_ids(user_input)
            if _has_partial_lightning_config(user_input):
                current_options = self._current_options()
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(self._options_schema(current_options)) if vol else dict,
                    errors={"base": "lightning_pair_required"},
                )
            return self.async_create_entry(title="Radar Hail Risk", data=user_input)

        current_options = self._current_options()
        schema = self._options_schema(current_options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema) if vol else schema,
        )

    def _current_options(self) -> dict[str, Any]:
        """Return defaults merged with setup data and saved options."""

        current = dict(OPTIONAL_CONF_DEFAULTS)
        current.update(getattr(self.config_entry, "data", {}) or {})
        current.update(getattr(self.config_entry, "options", {}) or {})
        return current

    @staticmethod
    def _options_schema(current_options: dict[str, Any]) -> dict[Any, Any]:
        """Build the options schema using current values as defaults."""

        if not vol:
            return {
                CONF_LOCATION_ENTITY_ID: current_options.get(CONF_LOCATION_ENTITY_ID, ""),
                CONF_LIGHTNING_DISTANCE_ENTITY_ID: current_options.get(
                    CONF_LIGHTNING_DISTANCE_ENTITY_ID, ""
                ),
                CONF_LIGHTNING_COUNTER_ENTITY_ID: current_options.get(
                    CONF_LIGHTNING_COUNTER_ENTITY_ID, ""
                ),
                CONF_LIGHTNING_AZIMUTH_ENTITY_ID: current_options.get(
                    CONF_LIGHTNING_AZIMUTH_ENTITY_ID, ""
                ),
                **{
                    key: current_options.get(key, value)
                    for key, value in OPTIONAL_CONF_DEFAULTS.items()
                },
            }

        return {
            _optional_entity_key(
                CONF_LOCATION_ENTITY_ID,
                current_options.get(CONF_LOCATION_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["zone", "person", "device_tracker"], multiple=False
                )
            ),
            _optional_entity_key(
                CONF_LIGHTNING_DISTANCE_ENTITY_ID,
                current_options.get(CONF_LIGHTNING_DISTANCE_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="distance", multiple=False
                )
            ),
            _optional_entity_key(
                CONF_LIGHTNING_COUNTER_ENTITY_ID,
                current_options.get(CONF_LIGHTNING_COUNTER_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=False)
            ),
            _optional_entity_key(
                CONF_LIGHTNING_AZIMUTH_ENTITY_ID,
                current_options.get(CONF_LIGHTNING_AZIMUTH_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=False)
            ),
            **{
                vol.Optional(key, default=current_options.get(key, value)): int
                for key, value in OPTIONAL_CONF_DEFAULTS.items()
            },
        }


def _clean_optional_entity_ids(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop blank optional lightning entity selectors from flow input."""

    cleaned = dict(user_input)
    for key in (
        CONF_LOCATION_ENTITY_ID,
        CONF_LIGHTNING_DISTANCE_ENTITY_ID,
        CONF_LIGHTNING_COUNTER_ENTITY_ID,
        CONF_LIGHTNING_AZIMUTH_ENTITY_ID,
    ):
        value = cleaned.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            cleaned.pop(key, None)
    return cleaned


def _has_partial_lightning_config(user_input: dict[str, Any]) -> bool:
    """Return true when exactly one lightning source entity was provided."""

    distance = user_input.get(CONF_LIGHTNING_DISTANCE_ENTITY_ID)
    counter = user_input.get(CONF_LIGHTNING_COUNTER_ENTITY_ID)
    return bool(distance) != bool(counter)


def _optional_entity_key(name: str, default: str | None) -> Any:
    if default:
        return vol.Optional(name, default=default)
    return vol.Optional(name)


def _iter_hass_states(hass: Any) -> list[Any]:
    states = getattr(hass, "states", None)
    async_all = getattr(states, "async_all", None)
    if callable(async_all):
        return list(async_all())
    all_states = getattr(states, "all", None)
    if callable(all_states):
        return list(all_states())
    return []
