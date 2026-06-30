"""Tiny Home Assistant import fallbacks for local static tests.

These classes are intentionally minimal and are used only when Home Assistant is
not installed in the local development environment. Real Home Assistant runtime
imports the actual classes instead.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class FallbackConfigFlow:
    """ConfigFlow-like fallback that tolerates HA's class keyword args."""

    def __init_subclass__(cls, **_kwargs: Any) -> None:
        super().__init_subclass__()

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    async def async_set_unique_id(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def _abort_if_unique_id_configured(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def _async_abort_entries_match(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class FallbackOptionsFlow:
    """OptionsFlow-like fallback for local imports."""

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs


class FallbackCoordinatorEntity:
    """CoordinatorEntity-like fallback supporting generic subscription syntax."""

    def __class_getitem__(cls, _item: Any) -> type["FallbackCoordinatorEntity"]:
        return cls

    def __init__(self, coordinator: Any | None = None) -> None:
        self.coordinator = coordinator


class FallbackEntity:
    """Entity-like fallback for local imports."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class FallbackUpdateFailed(Exception):
    """Fallback exception used by coordinator code paths in test mode."""


class FallbackDataUpdateCoordinator:
    """Minimal DataUpdateCoordinator-compatible base for non-HA runtime."""

    def __class_getitem__(cls, _item: Any) -> type["FallbackDataUpdateCoordinator"]:
        return cls

    def __init__(self, hass: Any, logger: Any, *, name: str, update_interval: timedelta | int | float | None = None) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = timedelta(seconds=update_interval) if isinstance(update_interval, (int, float)) else update_interval
        self.last_update_success = True
        self.last_update_success_time: datetime | None = None
        self.data: Any = None

    async def async_request_refresh(self) -> None:
        self.data = await self._async_update_data()
        self.last_update_success = True
        self.last_update_success_time = datetime.utcnow()

    async def async_config_entry_first_refresh(self) -> None:
        await self.async_request_refresh()

    def async_add_listener(self, *_args: Any, **_kwargs: Any) -> None:
        return None
