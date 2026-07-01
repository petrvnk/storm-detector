"""DataUpdateCoordinator for radar/lighting risk evaluation."""

from __future__ import annotations

import inspect
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from .const import (
    ATTR_CONFIDENCE_LEVEL,
    ATTR_CONFIDENCE_SCORE,
    ATTR_CORE50_DISTANCE_KM,
    ATTR_CORE55_DISTANCE_KM,
    ATTR_CORE60_DISTANCE_KM,
    ATTR_CORE_COUNT,
    ATTR_CORE_DISTANCE_KM,
    ATTR_DBZ_TREND,
    ATTR_DEGRADATION_REASONS,
    ATTR_DISTANCE_TREND,
    ATTR_FRAME_AGE_SECONDS,
    ATTR_FRAME_TIME,
    ATTR_FRAMES_ANALYZED,
    ATTR_LAST_ERROR,
    ATTR_LIGHTNING_AZIMUTH_DEGREES,
    ATTR_LIGHTNING_CORE_DISTANCE_KM,
    ATTR_LIGHTNING_COUNTER_DELTA,
    ATTR_LIGHTNING_DIAGNOSTICS,
    ATTR_LIGHTNING_DISTANCE_KM,
    ATTR_LIGHTNING_LATITUDE,
    ATTR_LIGHTNING_LONGITUDE,
    ATTR_LIGHTNING_TRIGGERED,
    ATTR_LOCATION_SOURCE,
    ATTR_MAX_DBZ,
    ATTR_RAINVIEWER_DIAGNOSTICS,
    ATTR_SELECTED_CORE_AREA_KM2,
    ATTR_SELECTED_CORE_DISTANCE_KM,
    ATTR_SELECTED_CORE_LATITUDE,
    ATTR_SELECTED_CORE_LONGITUDE,
    ATTR_SELECTED_CORE_MAX_DBZ,
    ATTR_SELECTED_CORE_PIXEL_COUNT,
    ATTR_SELECTED_CORE_THRESHOLD_DBZ,
    ATTR_SOURCE_STATUS,
    ATTR_STALE,
    ATTR_STORM_APPROACHING,
    ATTR_STORM_CORES,
    ATTR_STORM_ETA_MINUTES,
    ATTR_STORM_MOTION_BEARING,
    ATTR_STORM_MOTION_SPEED_KMH,
    ATTR_SUMMARY,
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
from .lightning import (
    HomeAssistantLightningSource,
    autodetect_blitzortung_entities,
    destination_point,
    haversine_km,
)
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
        self._lightning_source_key: tuple[str, ...] | None = None
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

    def _location(self) -> tuple[float, float, str, str | None]:
        """Resolve the configured location source.

        When a zone/person/device_tracker is configured, its latitude/longitude
        attributes become the single source of truth. Otherwise, fall back to the
        Home Assistant core location.
        """

        configured_entity = self._effective_config().get(CONF_LOCATION_ENTITY_ID)
        if configured_entity:
            state = _get_hass_state(self.hass, str(configured_entity))
            if state is None:
                return 0.0, 0.0, str(configured_entity), "missing_location_entity"
            location = _location_from_state(state)
            if location is None:
                return 0.0, 0.0, str(configured_entity), "invalid_location_entity"
            lat, lon = location
            return lat, lon, str(configured_entity), None

        config = getattr(self.hass, "config", None)
        lat = getattr(config, "latitude", None)
        lon = getattr(config, "longitude", None)
        if lat is None or lon is None:
            return 0.0, 0.0, "hass.config", "missing_hass_location"
        try:
            return float(lat), float(lon), "hass.config", None
        except Exception:
            return 0.0, 0.0, "hass.config", "invalid_hass_location"

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
            ATTR_CORE50_DISTANCE_KM: result.core50_distance_km,
            ATTR_CORE55_DISTANCE_KM: result.core55_distance_km,
            ATTR_CORE60_DISTANCE_KM: result.core60_distance_km,
            ATTR_LIGHTNING_DISTANCE_KM: result.lightning_distance_km,
            ATTR_LIGHTNING_AZIMUTH_DEGREES: result.lightning_azimuth_degrees,
            ATTR_LIGHTNING_LATITUDE: result.lightning_latitude,
            ATTR_LIGHTNING_LONGITUDE: result.lightning_longitude,
            ATTR_LIGHTNING_CORE_DISTANCE_KM: result.lightning_core_distance_km,
            ATTR_FRAME_AGE_SECONDS: result.frame_age_seconds,
            ATTR_FRAME_TIME: result.frame_time,
            ATTR_FRAMES_ANALYZED: result.frames_analyzed,
            ATTR_SELECTED_CORE_THRESHOLD_DBZ: result.selected_core_threshold_dbz,
            ATTR_SELECTED_CORE_DISTANCE_KM: result.selected_core_distance_km,
            ATTR_SELECTED_CORE_AREA_KM2: result.selected_core_area_km2,
            ATTR_SELECTED_CORE_PIXEL_COUNT: result.selected_core_pixel_count,
            ATTR_SELECTED_CORE_MAX_DBZ: result.selected_core_max_dbz,
            ATTR_STORM_CORES: list(result.storm_cores or ()),
            ATTR_CORE_COUNT: result.core_count,
            ATTR_SELECTED_CORE_LATITUDE: result.selected_core_latitude,
            ATTR_SELECTED_CORE_LONGITUDE: result.selected_core_longitude,
            ATTR_STORM_MOTION_BEARING: result.storm_motion_bearing,
            ATTR_STORM_MOTION_SPEED_KMH: result.storm_motion_speed_kmh,
            ATTR_STORM_APPROACHING: result.storm_approaching,
            ATTR_STORM_ETA_MINUTES: result.storm_eta_minutes,
            ATTR_DBZ_TREND: result.dbz_trend,
            ATTR_DISTANCE_TREND: result.distance_trend,
            ATTR_CONFIDENCE_SCORE: result.confidence_score,
            ATTR_CONFIDENCE_LEVEL: result.confidence_level,
            ATTR_LIGHTNING_TRIGGERED: result.has_lightning_trigger,
            ATTR_LIGHTNING_COUNTER_DELTA: result.lightning_counter_delta,
            ATTR_LIGHTNING_DIAGNOSTICS: extras.get(ATTR_LIGHTNING_DIAGNOSTICS)
            if extras
            else (),
            ATTR_RAINVIEWER_DIAGNOSTICS: extras.get(ATTR_RAINVIEWER_DIAGNOSTICS)
            if extras
            else (),
            ATTR_LOCATION_SOURCE: extras.get(ATTR_LOCATION_SOURCE) if extras else None,
            ATTR_SOURCE_STATUS: extras.get(ATTR_SOURCE_STATUS) if extras else {},
            ATTR_DEGRADATION_REASONS: extras.get(ATTR_DEGRADATION_REASONS) if extras else (),
            ATTR_STALE: result.is_stale,
            "update_count": self._update_count,
        }

    def _build_lightning_snapshot(self, now: datetime):
        config = self._effective_config()
        distance_entity_id = config.get(CONF_LIGHTNING_DISTANCE_ENTITY_ID)
        counter_entity_id = config.get(CONF_LIGHTNING_COUNTER_ENTITY_ID)
        azimuth_entity_id = config.get(CONF_LIGHTNING_AZIMUTH_ENTITY_ID)

        if not distance_entity_id or not counter_entity_id or not azimuth_entity_id:
            candidates = autodetect_blitzortung_entities(_iter_hass_states(self.hass))
            distance_entity_id = distance_entity_id or candidates.distance_entity_id
            counter_entity_id = counter_entity_id or candidates.counter_entity_id
            azimuth_entity_id = azimuth_entity_id or candidates.azimuth_entity_id

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

        source_key = (str(distance_entity_id), str(counter_entity_id), str(azimuth_entity_id or ""))
        if self._lightning_source is None or self._lightning_source_key != source_key:
            self._lightning_source = HomeAssistantLightningSource(
                distance_entity_id=str(distance_entity_id),
                counter_entity_id=str(counter_entity_id),
                azimuth_entity_id=str(azimuth_entity_id) if azimuth_entity_id else None,
                trigger_radius_km=trigger_radius_km,
                stale_after_seconds=stale_after_seconds,
            )
            self._lightning_source_key = source_key

        return self._lightning_source.read(self.hass, now=now)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch sources, degrade per-source, and publish one resilient payload."""

        self._update_count += 1
        now = datetime.now(UTC)
        location_lat, location_lon, location_source, location_error = self._location()
        if location_error is not None:
            return self._payload(
                HailRiskResult(
                    level=RISK_LEVEL_UNAVAILABLE,
                    summary="Location source is not configured or has no coordinates",
                    last_error=location_error,
                    is_stale=True,
                    diagnostics=(location_error,),
                ),
                extras={
                    ATTR_LOCATION_SOURCE: location_source,
                    ATTR_SOURCE_STATUS: {
                        "location": "error",
                        "radar": "skipped",
                        "lightning": "skipped",
                    },
                    ATTR_DEGRADATION_REASONS: (location_error,),
                },
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
                center_latitude, center_longitude = location_lat, location_lon
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

                raw_max_dbz = getattr(analysis, "max_dbz", None) if analysis else None
                raw_core50_distance = getattr(analysis, "core50_distance_km", None) if analysis else None
                raw_core55_distance = getattr(analysis, "core55_distance_km", None) if analysis else None
                raw_core60_distance = getattr(analysis, "core60_distance_km", None) if analysis else None
                raw_selected_threshold = getattr(analysis, "selected_core_threshold_dbz", None) if analysis else None
                raw_selected_distance = getattr(analysis, "selected_core_distance_km", None) if analysis else None
                raw_selected_lat = getattr(analysis, "selected_core_latitude", None) if analysis else None
                raw_selected_lon = getattr(analysis, "selected_core_longitude", None) if analysis else None
                raw_selected_area = getattr(analysis, "selected_core_area_km2", None) if analysis else None
                raw_selected_pixels = getattr(analysis, "selected_core_pixel_count", None) if analysis else None
                raw_selected_max_dbz = getattr(analysis, "selected_core_max_dbz", None) if analysis else None
                raw_storm_cores = getattr(analysis, "storm_cores", ()) if analysis else ()
                raw_core_count = getattr(analysis, "core_count", None) if analysis else None
                raw_motion_bearing = getattr(analysis, "storm_motion_bearing", None) if analysis else None
                raw_motion_speed = getattr(analysis, "storm_motion_speed_kmh", None) if analysis else None
                raw_approaching = getattr(analysis, "storm_approaching", None) if analysis else None
                raw_eta = getattr(analysis, "storm_eta_minutes", None) if analysis else None
                raw_dbz_trend = getattr(analysis, "dbz_trend", None) if analysis else None
                raw_distance_trend = getattr(analysis, "distance_trend", None) if analysis else None
                frame_age = getattr(analysis, "frame_age_seconds", None) if analysis else None
                frame_time = getattr(analysis, "frame_time", None) if analysis else None
                frames_analyzed = getattr(analysis, "frames_analyzed", None) if analysis else None

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

                if raw_core50_distance is None and raw_selected_threshold == 50:
                    raw_core50_distance = raw_selected_distance
                if raw_core55_distance is None and raw_selected_threshold == 55:
                    raw_core55_distance = raw_selected_distance
                if raw_core60_distance is None and raw_selected_threshold == 60:
                    raw_core60_distance = raw_selected_distance

                if radar_stale:
                    max_dbz = None
                    core50_distance = None
                    core55_distance = None
                    core60_distance = None
                    selected_threshold = None
                    selected_distance = None
                    selected_lat = None
                    selected_lon = None
                    selected_area = None
                    selected_pixels = None
                    selected_max_dbz = None
                    storm_cores = ()
                    core_count = raw_core_count
                    motion_bearing = None
                    motion_speed = None
                    approaching = None
                    eta = None
                    dbz_trend = None
                    distance_trend = None
                else:
                    max_dbz = raw_max_dbz
                    core50_distance = raw_core50_distance
                    core55_distance = raw_core55_distance
                    core60_distance = raw_core60_distance
                    selected_threshold = raw_selected_threshold
                    selected_distance = raw_selected_distance
                    selected_lat = raw_selected_lat
                    selected_lon = raw_selected_lon
                    selected_area = raw_selected_area
                    selected_pixels = raw_selected_pixels
                    selected_max_dbz = raw_selected_max_dbz
                    storm_cores = raw_storm_cores
                    core_count = raw_core_count
                    motion_bearing = raw_motion_bearing
                    motion_speed = raw_motion_speed
                    approaching = raw_approaching
                    eta = raw_eta
                    dbz_trend = raw_dbz_trend
                    distance_trend = raw_distance_trend

                lightning_snapshot = self._build_lightning_snapshot(now)
                lightning_distance_km = None
                lightning_azimuth_degrees = None
                lightning_latitude = None
                lightning_longitude = None
                lightning_core_distance_km = None
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
                        lightning_azimuth_degrees = lightning_snapshot.azimuth_degrees
                        if lightning_distance_km is not None and lightning_azimuth_degrees is not None:
                            lightning_latitude, lightning_longitude = destination_point(
                                location_lat,
                                location_lon,
                                lightning_distance_km,
                                lightning_azimuth_degrees,
                            )
                            if selected_lat is not None and selected_lon is not None:
                                lightning_core_distance_km = haversine_km(
                                    lightning_latitude,
                                    lightning_longitude,
                                    selected_lat,
                                    selected_lon,
                                )
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
                source_status = {
                    "location": "ok",
                    "radar": _radar_source_status(
                        diagnostics=radar_diagnostics,
                        has_analysis=analysis is not None,
                        is_stale=radar_stale,
                    ),
                    "lightning": _lightning_source_status(
                        snapshot_configured=lightning_snapshot is not None,
                        diagnostics=tuple(lightning_diagnostics),
                        is_stale=lightning_stale,
                    ),
                }
                degradation_reasons = _degradation_reasons(
                    radar_diagnostics=radar_diagnostics,
                    lightning_diagnostics=tuple(lightning_diagnostics),
                )
                source_data_stale = bool(radar_stale or lightning_stale)

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
                    core50_distance_km=core50_distance,
                    core55_distance_km=core55_distance,
                    core60_distance_km=core60_distance,
                )

                confidence_score, confidence_level = _confidence_from_signals(
                    max_dbz=max_dbz,
                    selected_core_distance_km=selected_distance,
                    selected_core_pixel_count=selected_pixels,
                    lightning_distance_km=lightning_distance_km,
                    lightning_core_distance_km=lightning_core_distance_km,
                    storm_approaching=approaching,
                    radar_stale=radar_stale,
                    lightning_stale=lightning_stale,
                    source_status=source_status,
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
                        core50_distance_km=core50_distance,
                        core55_distance_km=core55_distance,
                        core60_distance_km=core60_distance,
                        lightning_distance_km=lightning_distance_km,
                        lightning_azimuth_degrees=lightning_azimuth_degrees,
                        lightning_latitude=lightning_latitude,
                        lightning_longitude=lightning_longitude,
                        lightning_core_distance_km=lightning_core_distance_km,
                        frame_age_seconds=frame_age,
                        selected_core_threshold_dbz=selected_threshold,
                        selected_core_distance_km=selected_distance,
                        selected_core_area_km2=selected_area,
                        selected_core_pixel_count=selected_pixels,
                        selected_core_max_dbz=selected_max_dbz,
                        storm_cores=tuple(storm_cores or ()),
                        core_count=core_count,
                        selected_core_latitude=selected_lat,
                        selected_core_longitude=selected_lon,
                        storm_motion_bearing=motion_bearing,
                        storm_motion_speed_kmh=motion_speed,
                        storm_approaching=approaching,
                        storm_eta_minutes=eta,
                        dbz_trend=dbz_trend,
                        distance_trend=distance_trend,
                        confidence_score=confidence_score,
                        confidence_level=confidence_level,
                        frames_analyzed=frames_analyzed,
                        frame_time=frame_time,
                        last_error=", ".join(diagnostics) if diagnostics else None,
                        is_stale=source_data_stale,
                        has_lightning_trigger=lightning_triggered,
                        lightning_counter_delta=lightning_counter_delta,
                        diagnostics=tuple(diagnostics),
                    ),
                    extras={
                        ATTR_LIGHTNING_DIAGNOSTICS: tuple(lightning_diagnostics),
                        ATTR_RAINVIEWER_DIAGNOSTICS: tuple(radar_diagnostics),
                        ATTR_LOCATION_SOURCE: location_source,
                        ATTR_SOURCE_STATUS: source_status,
                        ATTR_DEGRADATION_REASONS: degradation_reasons,
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


def _get_hass_state(hass: Any, entity_id: str) -> Any | None:
    states = getattr(hass, "states", None)
    getter = getattr(states, "get", None)
    if callable(getter):
        return getter(entity_id)
    return None


def _location_from_state(state: Any) -> tuple[float, float] | None:
    attributes = getattr(state, "attributes", {})
    if not isinstance(attributes, dict):
        attributes = {}
    lat = attributes.get("latitude")
    lon = attributes.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except Exception:
        return None


def _radar_source_status(*, diagnostics: Iterable[str], has_analysis: bool, is_stale: bool) -> str:
    """Return a compact runtime status for the radar source."""

    diagnostics_tuple = tuple(diagnostics)
    if is_stale:
        return "stale"
    if not has_analysis:
        return "degraded"
    if diagnostics_tuple:
        return "degraded"
    return "ok"


def _lightning_source_status(
    *, snapshot_configured: bool, diagnostics: Iterable[str], is_stale: bool
) -> str:
    """Return a compact runtime status for the optional lightning source."""

    diagnostics_tuple = tuple(diagnostics)
    if not snapshot_configured:
        return "not_configured"
    if is_stale:
        return "stale"
    actionable = [item for item in diagnostics_tuple if item != "lightning_not_configured"]
    if actionable:
        return "degraded"
    return "ok"


def _degradation_reasons(
    *, radar_diagnostics: Iterable[str], lightning_diagnostics: Iterable[str]
) -> tuple[str, ...]:
    """Return source diagnostics that represent actionable degraded behavior."""

    non_degrading = {
        "lightning_not_configured",
        "lightning_strike_delta",
        "lightning_counter_delta",
    }
    return tuple(
        dict.fromkeys(
            item for item in (*radar_diagnostics, *lightning_diagnostics) if item not in non_degrading
        )
    )


def _confidence_from_signals(
    *,
    max_dbz: int | None,
    selected_core_distance_km: float | None,
    selected_core_pixel_count: int | None,
    lightning_distance_km: float | None,
    lightning_core_distance_km: float | None,
    storm_approaching: bool | None,
    radar_stale: bool,
    lightning_stale: bool,
    source_status: dict[str, str],
) -> tuple[int, str]:
    """Return a simple confidence score/level for the current risk estimate."""

    score = 20
    if source_status.get("radar") == "ok" and not radar_stale:
        score += 25
    if max_dbz is not None and max_dbz >= 50:
        score += 15
    if selected_core_distance_km is not None:
        score += 10
    if selected_core_pixel_count is not None and selected_core_pixel_count > 1:
        score += min(10, selected_core_pixel_count)
    if lightning_distance_km is not None and not lightning_stale:
        score += 10
    if lightning_core_distance_km is not None and lightning_core_distance_km <= 15:
        score += 10
    if storm_approaching is True:
        score += 5
    if source_status.get("radar") in {"degraded", "stale", "error"}:
        score -= 25
    if lightning_stale:
        score -= 10

    score = max(0, min(100, score))
    if score >= 75:
        return score, "high"
    if score >= 45:
        return score, "medium"
    return score, "low"


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
