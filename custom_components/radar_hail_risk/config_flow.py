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

        class NumberSelector:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        class NumberSelectorConfig:
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
    PARAMETER_SPECS,
)
from .lightning import autodetect_blitzortung_entities


class RadarHailRiskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for adding the integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial user step."""

        if user_input is not None:
            user_input = _clean_optional_entity_ids(user_input)
            validation_errors = _validate_parameter_ranges(user_input)
            if validation_errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(self._base_schema()) if vol else dict,
                    errors=validation_errors,
                )
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
            _number_key(CONF_ANALYSIS_RADIUS_KM, DEFAULT_ANALYSIS_RADIUS_KM): _number_selector(
                CONF_ANALYSIS_RADIUS_KM
            ),
            _number_key(
                CONF_LIGHTNING_TRIGGER_RADIUS_KM,
                DEFAULT_LIGHTNING_TRIGGER_RADIUS_KM,
            ): _number_selector(CONF_LIGHTNING_TRIGGER_RADIUS_KM),
            _number_key(
                CONF_WARNING_LIGHTNING_DISTANCE_KM,
                DEFAULT_WARNING_LIGHTNING_DISTANCE_KM,
            ): _number_selector(CONF_WARNING_LIGHTNING_DISTANCE_KM),
            _number_key(
                CONF_URGENT_LIGHTNING_DISTANCE_KM,
                DEFAULT_URGENT_LIGHTNING_DISTANCE_KM,
            ): _number_selector(CONF_URGENT_LIGHTNING_DISTANCE_KM),
            _number_key(CONF_CORE_WATCH_DBZ, DEFAULT_CORE_WATCH_DBZ): _number_selector(
                CONF_CORE_WATCH_DBZ
            ),
            _number_key(
                CONF_CORE_WARNING_DBZ,
                DEFAULT_CORE_WARNING_DBZ,
            ): _number_selector(CONF_CORE_WARNING_DBZ),
            _number_key(CONF_CORE_URGENT_DBZ, DEFAULT_CORE_URGENT_DBZ): _number_selector(
                CONF_CORE_URGENT_DBZ
            ),
            _number_key(
                CONF_MIN_ANALYSIS_INTERVAL_SECONDS,
                DEFAULT_MIN_ANALYSIS_INTERVAL_SECONDS,
            ): _number_selector(CONF_MIN_ANALYSIS_INTERVAL_SECONDS),
            _number_key(CONF_STALE_CLEAR_SECONDS, DEFAULT_STALE_CLEAR_SECONDS): _number_selector(
                CONF_STALE_CLEAR_SECONDS
            ),
            _number_key(CONF_RAINVIEWER_ZOOM, DEFAULT_RAINVIEWER_ZOOM): _number_selector(
                CONF_RAINVIEWER_ZOOM
            ),
            _number_key(CONF_RAINVIEWER_FRAMES, DEFAULT_RAINVIEWER_FRAMES): _number_selector(
                CONF_RAINVIEWER_FRAMES
            ),
            _number_key(
                CONF_WARNING_CORE_DISTANCE_KM,
                DEFAULT_WARNING_CORE_DISTANCE_KM,
            ): _number_selector(CONF_WARNING_CORE_DISTANCE_KM),
            _number_key(
                CONF_URGENT_CORE_DISTANCE_KM,
                DEFAULT_URGENT_CORE_DISTANCE_KM,
            ): _number_selector(CONF_URGENT_CORE_DISTANCE_KM),
        }


class RadarHailRiskOptionsFlowHandler(OptionsFlow):
    """Options flow for post-setup thresholds and lightning source selection."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options updates."""

        if user_input is not None:
            user_input = _clean_optional_entity_ids(user_input)
            validation_errors = _validate_parameter_ranges(user_input)
            if validation_errors:
                current_options = self._current_options()
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(self._options_schema(current_options)) if vol else dict,
                    errors=validation_errors,
                )
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
                _number_key(key, current_options.get(key, value)): _number_selector(key)
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


def _number_key(name: str, default: int | float | None) -> Any:
    if not vol:
        return name
    return vol.Optional(name, default=default)


def _number_selector(name: str) -> Any:
    """Return a Home Assistant number selector with documented safe bounds."""

    spec = PARAMETER_SPECS[name]
    kwargs: dict[str, Any] = {
        "min": spec["min"],
        "max": spec["max"],
        "step": spec["step"],
    }
    unit = spec.get("unit")
    if unit:
        kwargs["unit_of_measurement"] = unit
    return selector.NumberSelector(selector.NumberSelectorConfig(**kwargs))


def _validate_parameter_ranges(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate numeric options before saving config/options entries."""

    errors: dict[str, str] = {}
    values: dict[str, int] = {}
    for key, spec in PARAMETER_SPECS.items():
        raw = user_input.get(key)
        if raw in (None, ""):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            errors[key] = "invalid_value"
            continue
        if value < int(spec["min"]) or value > int(spec["max"]):
            errors[key] = "invalid_range"
            continue
        user_input[key] = value
        values[key] = value

    if errors:
        return errors

    merged = {**OPTIONAL_CONF_DEFAULTS, **values}
    watch = int(merged[CONF_CORE_WATCH_DBZ])
    warning = int(merged[CONF_CORE_WARNING_DBZ])
    urgent = int(merged[CONF_CORE_URGENT_DBZ])
    if not watch < warning < urgent:
        return {"base": "invalid_threshold_order"}

    warning_core = int(merged[CONF_WARNING_CORE_DISTANCE_KM])
    urgent_core = int(merged[CONF_URGENT_CORE_DISTANCE_KM])
    warning_lightning = int(merged[CONF_WARNING_LIGHTNING_DISTANCE_KM])
    urgent_lightning = int(merged[CONF_URGENT_LIGHTNING_DISTANCE_KM])
    if not warning_core >= urgent_core or not warning_lightning >= urgent_lightning:
        return {"base": "invalid_distance_order"}

    trigger = int(merged[CONF_LIGHTNING_TRIGGER_RADIUS_KM])
    if trigger < warning_lightning:
        return {"base": "invalid_trigger_radius"}

    return {}


def _iter_hass_states(hass: Any) -> list[Any]:
    states = getattr(hass, "states", None)
    async_all = getattr(states, "async_all", None)
    if callable(async_all):
        return list(async_all())
    all_states = getattr(states, "all", None)
    if callable(all_states):
        return list(all_states())
    return []
