"""Storm Detector integration bootstrap.

This file intentionally contains a minimal, Stage-2-safe skeleton for:
- config entry setup/unload hooks
- platform forwarding
- options update reload wiring
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .const import COORDINATOR_KEY, DATA_KEY_RESULT, DOMAIN, INTEGRATION_NAME, PLATFORMS
from .coordinator import RadarHailRiskCoordinator

_LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - Home Assistant imports are validated in real runtime.
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except Exception:  # pragma: no cover
    ConfigEntry = Any
    HomeAssistant = Any
    StaticPathConfig = Any

_FRONTEND_PATH = Path(__file__).parent / "frontend"
_FRONTEND_URL = f"/{DOMAIN}"
_STATIC_REGISTERED = "frontend_static_registered"


async def async_setup(hass: HomeAssistant, _config: dict[str, Any]) -> bool:
    """Set up the integration from yaml config (frontend static path only)."""

    await _async_register_frontend_static_path(hass)
    return True


async def _async_register_frontend_static_path(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card without requiring `/config/www` writes."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_STATIC_REGISTERED):
        return
    if not _FRONTEND_PATH.exists():
        _LOGGER.debug("Storm Detector frontend path does not exist: %s", _FRONTEND_PATH)
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_FRONTEND_URL, str(_FRONTEND_PATH), True)]
    )
    domain_data[_STATIC_REGISTERED] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry.

    Stage 2 keeps the coordinator lifecycle as a placeholder. Platforms are
    forwarded so platform scaffolds can be developed independently.
    """

    await _async_register_frontend_static_path(hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    coordinator = RadarHailRiskCoordinator(hass, _LOGGER, INTEGRATION_NAME, entry)
    hass.data[DOMAIN][entry.entry_id][COORDINATOR_KEY] = coordinator
    hass.data[DOMAIN][entry.entry_id][DATA_KEY_RESULT] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and release shared state."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data.get(DOMAIN, {})
        entry_data.pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""

    await hass.config_entries.async_reload(entry.entry_id)
