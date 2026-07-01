"""DataUpdateCoordinator for radar/lighting risk evaluation."""

from __future__ import annotations

import inspect
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from .const import (
    ATTR_CORE_DISTANCE_KM,
    ATTR_FRAME_AGE_SECONDS,
    ATTR_FRAME_TIME,
    ATTR_FRAMES_ANALYZED,
    ATTR_LAST_ERROR,
    ATTR_LIGHTNING_COUNTER_DELTA,
    ATTR_LIGHTNING_DIAGNOSTICS,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LIGHTNING_TRIGGERED,
    ATTR_MAX_DBZ,
    ATTR_RAINVIEWER_DIAGNOSTICS,
    ATTR_SELECTED_CORE_DISTANCE_KM,
    ATTR_SELECTED_CORE_LATITUDE,
    ATTR_SELECTED_CORE_LONGITUDE,
    ATTR_SELECTED_CORE_THRESHOLD_DBZ,
    ATTR_STALE,
    ATTR_SUMMARY,
    CONF_ANALYSIS_RADIUS_KM,
    CONF_CORE_URGENT_DBZ,
    CONF_CORE_WARNING_DBZ,
    CONF_CORE_WATCH_DBZ,
    CONF_LIGHTNING_COUNTER_ENTITY_ID,
    CONF_LIGHTNING_DISTANCE_ENTITY_ID,
    CONF_LIGHTNING_TRIGGER_RADIUS_KM,
    CONF_MIN_ANALYSIS_INTERVAL_SECONDS,
    CONF_RAINVIEWER_FRAMES,
    CONF_RAINVIEWER_ZOOM,
    CONF_STALE_CLEAR_SECONDS,
    CONF_URGENT_CORE_DISTANCE_KM,
    CONF_URGENT_LIGHTNING_DISTANCE_KM,
    CONF_WARNING_CORE_DISTANCE_KM,
    CONF_WARNING_LIGHTNING_DISTANCE_KM,
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
    OPTIONAL_CONF_DEFAULTS,
    RISK_LEVEL_UNAVAILABLE,
)
from .ha_fallback import FallbackDataUpdateCoordinator, FallbackUpdateFailed
from .lightning import HomeAssistantLightningSource, autodetect_blitzortung_entities
from .rainviewer import analyze_recent_frames, fetch_radar_metadata, fetch_rainviewer_color_lookup
from .risk import (
    HailRiskResult,
    build_summary,
    classify_from_thresholds,
    normalize_optional_float,
    normalize_optional_int,
    user_visible_diagnostics,
)

try:  # pragma: no cover
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
except Exception:  # pragma: no cover
    DataUpdateCoordinator = FallbackDataUpdateCoordinator  # type: ignore[assignment]
    UpdateFailed = FallbackUpdateFailed  # type: ignore[assignment]

try:  # pragma: no cover
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]


async def _await_if_needed(value: Any) -> Any:
    """Support both awaitable and sync callables in tests/fixtures and production."""

    if inspect.isawaitable(value):
        return await value
    return value


class RadarHailRiskCoordinator(DataUpdateCoordinator):
    """Polls RainViewer and optional lightning sensor states and publishes risk."""

    def __init__(
        self,
        hass: Any,
        logger: Any,
        name: str,
        entry: Any | None = None,
        *,
        session_factory: Any | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = getattr(entry, "entry_id", "default")
        self._session_factory = session_factory
        self._lightning_source: HomeAssistantLightningSource | None = None
        self._lightning_source_key: tuple[str, str] | None = None
        self._update_count = 0

        config = self._effective_config()
        interval = normalize_optional_int(
            config.get(CONF_MIN_ANALYSIS_INTERVAL_SECONDS),
            default=DEFAULT_MIN_ANALYSIS_INTERVAL_SECONDS,
        )
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=timedelta(seconds=max(interval, 30)),
        )

    def _effective_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if self.entry is not None:
            config.update(getattr(self.entry, "data", {}) or {})
            config.update(getattr(self.entry, "options", {}) or {})

        merged = dict(OPTIONAL_CONF_DEFAULTS)
        merged.update(config)
        return merged

    def _location(self) -> tuple[float, float] | None:
        config = getattr(self.hass, "config", None)
        lat = getattr(config, "latitude", None)
        lon = getattr(config, "longitude", None)
        if lat is None or lon is None:
            return None
        try:
            return float(lat), float(lon)
        except Exception:
            return None

    def _payload(
        self, result: HailRiskResult, *, extras: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = asdict(result)
        # Keep both list-like attrs for easier template consumption.
        payload["diagnostics"] = list(result.diagnostics)
        payload["level"] = result.level
        if result.last_error:
            payload[ATTR_LAST_ERROR] = result.last_error
        if extras:
            payload.update(extras)

        return {
            **payload,
            ATTR_SUMMARY: result.summary,
            ATTR_MAX_DBZ: result.max_dbz,
            ATTR_CORE_DISTANCE_KM: result.core_distance_km,
            ATTR_LIGHTNING_DISTANCE_KM: result.lightning_distance_km,
            ATTR_FRAME_AGE_SECONDS: result.frame_age_seconds,
            ATTR_FRAME_TIME: result.frame_time,
            ATTR_FRAMES_ANALYZED: result.frames_analyzed,
            ATTR_SELECTED_CORE_THRESHOLD_DBZ: result.selected_core_threshold_dbz,
            ATTR_SELECTED_CORE_DISTANCE_KM: result.selected_core_distance_km,
            ATTR_SELECTED_CORE_LATITUDE: result.selected_core_latitude,
            ATTR_SELECTED_CORE_LONGITUDE: result.selected_core_longitude,
            ATTR_LIGHTNING_TRIGGERED: result.has_lightning_trigger,
            ATTR_LIGHTNING_COUNTER_DELTA: result.lightning_counter_delta,
            ATTR_LIGHTNING_DIAGNOSTICS: extras.get(ATTR_LIGHTNING_DIAGNOSTICS)
            if extras
            else (),
            ATTR_RAINVIEWER_DIAGNOSTICS: extras.get(ATTR_RAINVIEWER_DIAGNOSTICS)
            if extras
            else (),
            ATTR_STALE: result.is_stale,
            "update_count": self._update_count,
        }

    def _build_lightning_snapshot(self, now: datetime):
        config = self._effective_config()
        distance_entity_id = config.get(CONF_LIGHTNING_DISTANCE_ENTITY_ID)
        counter_entity_id = config.get(CONF_LIGHTNING_COUNTER_ENTITY_ID)

        if not distance_entity_id or not counter_entity_id:
            candidates = autodetect_blitzortung_entities(_iter_hass_states(self.hass))
            distance_entity_id = distance_entity_id or candidates.distance_entity_id
            counter_entity_id = counter_entity_id or candidates.counter_entity_id

        if not distance_entity_id or not counter_entity_id:
            return None

        trigger_radius_km = normalize_optional_float(
            config.get(CONF_LIGHTNING_TRIGGER_RADIUS_KM),
            default=DEFAULT_LIGHTNING_TRIGGER_RADIUS_KM,
        )
        stale_after_seconds = normalize_optional_int(
            config.get(CONF_STALE_CLEAR_SECONDS),
            default=DEFAULT_STALE_CLEAR_SECONDS,
        )

        source_key = (str(distance_entity_id), str(counter_entity_id))
        if self._lightning_source is None or self._lightning_source_key != source_key:
            self._lightning_source = HomeAssistantLightningSource(
                distance_entity_id=str(distance_entity_id),
                counter_entity_id=str(counter_entity_id),
                trigger_radius_km=trigger_radius_km,
                stale_after_seconds=stale_after_seconds,
            )
            self._lightning_source_key = source_key

        return self._lightning_source.read(self.hass, now=now)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch sources, degrade per-source, and publish one resilient payload."""

        self._update_count += 1
        now = datetime.now(UTC)
        location = self._location()
        if location is None:
            return self._payload(
                HailRiskResult(
                    level=RISK_LEVEL_UNAVAILABLE,
                    summary="Home Assistant location is not configured",
                    last_error="Home Assistant location is not configured",
                    is_stale=True,
                    diagnostics=("missing_hass_location",),
                )
            )

        if self._session_factory is None:
            if aiohttp is None:
                return self._payload(
                    HailRiskResult(
                        level=RISK_LEVEL_UNAVAILABLE,
                        summary="aiohttp is not available in this environment",
                        last_error="aiohttp is not available in this environment",
                        is_stale=True,
                        diagnostics=("missing_aiohttp_dependency",),
                    )
                )
            session_ctx = aiohttp.ClientSession()
            close_session = True
        else:
            session_ctx = self._session_factory()
            close_session = False

        use_cm = callable(getattr(session_ctx, "__aenter__", None)) and callable(
            getattr(session_ctx, "__aexit__", None)
        )

        try:
            async def _run_with_session(session: Any) -> dict[str, Any]:
                center_latitude, center_longitude = location
                cfg = self._effective_config()

                radar_diagnostics: list[str] = []
                lightning_diagnostics: Iterable[str] = ()


                analysis = None
                try:
                    meta = await _await_if_needed(fetch_radar_metadata(session))
                except Exception:
                    meta = {}
                    radar_diagnostics.append("radar_source_error")

                if not isinstance(meta, dict):
                    meta = {}
                    radar_diagnostics.append("invalid_radar_metadata")
                elif "radar" not in meta:
                    radar_diagnostics.append("missing_radar_metadata")

                color_lookup: dict[Any, Any] = {}
                if meta.get("radar"):
                    try:
                        color_lookup = await _await_if_needed(fetch_rainviewer_color_lookup(session))
                    except Exception:
                        color_lookup = {}
                        radar_diagnostics.append("color_lookup_error")
                    if not color_lookup:
                        radar_diagnostics.append("missing_color_lookup")

                    try:
                        analysis = await _await_if_needed(
                            analyze_recent_frames(
                                session,
                                meta,
                                center_latitude,
                                center_longitude,
                                analysis_radius_km=normalize_optional_float(
                                    cfg.get(CONF_ANALYSIS_RADIUS_KM),
                                    default=50.0,
                                ),
                                required_frames=normalize_optional_int(
                                    cfg.get(CONF_RAINVIEWER_FRAMES),
                                    default=DEFAULT_RAINVIEWER_FRAMES,
                                ),
                                zoom=normalize_optional_int(
                                    cfg.get(CONF_RAINVIEWER_ZOOM),
                                    default=DEFAULT_RAINVIEWER_ZOOM,
                                ),
                                color_lookup=color_lookup,
                                now=int(now.timestamp()),
                            )
                        )
                    except Exception:
                        analysis = None
                        radar_diagnostics.append("radar_analysis_error")

                if analysis is None:
                    radar_diagnostics.append("no_recent_analysis")

                max_dbz = analysis.max_dbz if analysis else None
                selected_threshold = analysis.selected_core_threshold_dbz if analysis else None
                selected_distance = analysis.selected_core_distance_km if analysis else None
                selected_lat = analysis.selected_core_latitude if analysis else None
                selected_lon = analysis.selected_core_longitude if analysis else None
                frame_age = analysis.frame_age_seconds if analysis else None
                frame_time = analysis.frame_time if analysis else None
                frames_analyzed = analysis.frames_analyzed if analysis else None

                stale_after = normalize_optional_int(
                    cfg.get(CONF_STALE_CLEAR_SECONDS),
                    default=DEFAULT_STALE_CLEAR_SECONDS,
                )
                radar_stale = bool(frame_age is not None and frame_age > stale_after)
                if frame_age is not None and frame_age < 0:
                    radar_diagnostics.append("negative_frame_age")
                    frame_age = 0
                    radar_stale = False
                if radar_stale:
                    radar_diagnostics.append("stale_radar_frame")

                lightning_snapshot = self._build_lightning_snapshot(now)
                lightning_distance_km = None
                lightning_counter_delta = None
                lightning_triggered = False
                lightning_stale = False
                if lightning_snapshot is None:
                    lightning_diagnostics = ("lightning_not_configured",)
                else:
                    lightning_stale = bool(lightning_snapshot.is_stale)
                    lightning_diagnostics = tuple(lightning_snapshot.diagnostics)
                    if not lightning_stale:
                        lightning_distance_km = lightning_snapshot.distance_km
                        lightning_counter_delta = lightning_snapshot.counter_delta
                        lightning_triggered = bool(lightning_snapshot.trigger_active)
                        if lightning_triggered:
                            lightning_counter_delta = None


                summary_lightning_diagnostics = () if lightning_stale else user_visible_diagnostics(
                    tuple(lightning_diagnostics)
                )

                diagnostics = [
                    *radar_diagnostics,
                    *summary_lightning_diagnostics,
                ]
                has_radar_signal = any(value is not None for value in (max_dbz, selected_distance))
                has_lightning_signal = lightning_distance_km is not None
                all_available_sources_stale = bool(
                    (has_radar_signal and radar_stale and not has_lightning_signal)
                    or (has_lightning_signal and lightning_stale and not has_radar_signal)
                    or (has_radar_signal and radar_stale and has_lightning_signal and lightning_stale)
                )

                level = classify_from_thresholds(
                    max_dbz=max_dbz,
                    core_distance_km=selected_distance,
                    lightning_distance_km=lightning_distance_km,
                    watch_dbz=normalize_optional_int(
                        cfg.get(CONF_CORE_WATCH_DBZ),
                        default=DEFAULT_CORE_WATCH_DBZ,
                    ),
                    warning_dbz=normalize_optional_int(
                        cfg.get(CONF_CORE_WARNING_DBZ),
                        default=DEFAULT_CORE_WARNING_DBZ,
                    ),
                    urgent_dbz=normalize_optional_int(
                        cfg.get(CONF_CORE_URGENT_DBZ),
                        default=DEFAULT_CORE_URGENT_DBZ,
                    ),
                    warning_core_distance_km=normalize_optional_int(
                        cfg.get(CONF_WARNING_CORE_DISTANCE_KM),
                        default=DEFAULT_WARNING_CORE_DISTANCE_KM,
                    ),
                    urgent_core_distance_km=normalize_optional_int(
                        cfg.get(CONF_URGENT_CORE_DISTANCE_KM),
                        default=DEFAULT_URGENT_CORE_DISTANCE_KM,
                    ),
                    warning_lightning_distance_km=normalize_optional_int(
                        cfg.get(CONF_WARNING_LIGHTNING_DISTANCE_KM),
                        default=DEFAULT_WARNING_LIGHTNING_DISTANCE_KM,
                    ),
                    urgent_lightning_distance_km=normalize_optional_int(
                        cfg.get(CONF_URGENT_LIGHTNING_DISTANCE_KM),
                        default=DEFAULT_URGENT_LIGHTNING_DISTANCE_KM,
                    ),
                    lightning_triggered=lightning_triggered,
                    lightning_counter_delta=lightning_counter_delta,
                )

                summary = build_summary(
                    level=level,
                    max_dbz=max_dbz,
                    core_distance_km=selected_distance,
                    lightning_distance_km=lightning_distance_km,
                    frame_age_seconds=frame_age,
                    selected_core_threshold_dbz=selected_threshold,
                    diagnostics=tuple(diagnostics),
                )

                return self._payload(
                    HailRiskResult(
                        level=level,
                        summary=summary,
                        max_dbz=max_dbz,
                        core_distance_km=selected_distance,
                        lightning_distance_km=lightning_distance_km,
                        frame_age_seconds=frame_age,
                        selected_core_threshold_dbz=selected_threshold,
                        selected_core_distance_km=selected_distance,
                        selected_core_latitude=selected_lat,
                        selected_core_longitude=selected_lon,
                        frames_analyzed=frames_analyzed,
                        frame_time=frame_time,
                        last_error=", ".join(diagnostics) if diagnostics else None,
                        is_stale=all_available_sources_stale,
                        has_lightning_trigger=lightning_triggered,
                        lightning_counter_delta=lightning_counter_delta,
                        diagnostics=tuple(diagnostics),
                    ),
                    extras={
                        ATTR_LIGHTNING_DIAGNOSTICS: tuple(lightning_diagnostics),
                        ATTR_RAINVIEWER_DIAGNOSTICS: tuple(radar_diagnostics),
                    },
                )

            if use_cm:
                async with session_ctx as session:
                    return await _run_with_session(session)
            return await _run_with_session(session_ctx)

        except Exception as err:  # pragma: no cover
            raise UpdateFailed(f"Risk update failed: {err}")
        finally:
            if close_session and hasattr(session_ctx, "close"):
                try:
                    await session_ctx.close()
                except Exception:
                    pass


def _iter_hass_states(hass: Any) -> Iterable[Any]:
    """Return all HA states when available for runtime lightning autodetection."""

    states = getattr(hass, "states", None)
    async_all = getattr(states, "async_all", None)
    if callable(async_all):
        return async_all()
    all_states = getattr(states, "all", None)
    if callable(all_states):
        return all_states()
    return ()
