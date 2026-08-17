"""Diagnostics support for Storm Detector."""

from __future__ import annotations

from typing import Any

from .const import CONF_ANALYSIS_RADIUS_KM, COORDINATOR_KEY, DOMAIN

_RUNTIME_KEYS = (
    "level",
    "is_stale",
    "source_status",
    "degradation_reasons",
    "diagnostics",
    "radar_diagnostics",
    "lightning_diagnostics",
    "frame_age_seconds",
    "frames_analyzed",
    "confidence_level",
    "update_count",
)

_OPTION_KEYS = (CONF_ANALYSIS_RADIUS_KM,)


async def async_get_config_entry_diagnostics(hass: Any, entry: Any) -> dict[str, Any]:
    """Return safe config-entry diagnostics for issue reports.

    The payload contains only allowlisted non-identifying options and source health.
    """

    entry_options = getattr(entry, "options", {}) or {}
    coordinator = (
        getattr(hass, "data", {})
        .get(DOMAIN, {})
        .get(getattr(entry, "entry_id", ""), {})
        .get(COORDINATOR_KEY)
    )
    runtime_data = getattr(coordinator, "data", None) or {}

    return {
        "options": {key: entry_options[key] for key in _OPTION_KEYS if key in entry_options},
        "runtime": {key: runtime_data.get(key) for key in _RUNTIME_KEYS if key in runtime_data},
    }
