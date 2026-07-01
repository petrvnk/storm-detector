"""Diagnostics support for Radar Hail Risk."""

from __future__ import annotations

from typing import Any

from .const import COORDINATOR_KEY, DOMAIN

_RUNTIME_KEYS = (
    "level",
    "summary",
    "is_stale",
    "location_source",
    "source_status",
    "degradation_reasons",
    "diagnostics",
    "radar_diagnostics",
    "lightning_diagnostics",
    "max_dbz",
    "core_distance_km",
    "lightning_distance_km",
    "frame_age_seconds",
    "frame_time",
    "frames_analyzed",
    "selected_core_threshold_dbz",
    "selected_core_distance_km",
    "selected_core_latitude",
    "selected_core_longitude",
    "last_error",
    "update_count",
)


async def async_get_config_entry_diagnostics(hass: Any, entry: Any) -> dict[str, Any]:
    """Return safe config-entry diagnostics for issue reports.

    The payload intentionally contains entity IDs and runtime source health, but
    no credentials or Home Assistant tokens.
    """

    entry_data = getattr(entry, "data", {}) or {}
    entry_options = getattr(entry, "options", {}) or {}
    coordinator = (
        getattr(hass, "data", {})
        .get(DOMAIN, {})
        .get(getattr(entry, "entry_id", ""), {})
        .get(COORDINATOR_KEY)
    )
    runtime_data = getattr(coordinator, "data", None) or {}

    return {
        "entry": {
            "entry_id": getattr(entry, "entry_id", None),
            "title": getattr(entry, "title", None),
            "data": dict(entry_data),
            "options": dict(entry_options),
        },
        "runtime": {key: runtime_data.get(key) for key in _RUNTIME_KEYS if key in runtime_data},
    }
