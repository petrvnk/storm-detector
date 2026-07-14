"""Constants for the Radar Hail Risk integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "radar_hail_risk"
INTEGRATION_NAME: Final = "Radar Hail Risk"

PLATFORMS: Final = ["sensor", "binary_sensor", "device_tracker"]

CONF_LIGHTNING_DISTANCE_ENTITY_ID: Final = "lightning_distance_entity_id"
CONF_LIGHTNING_COUNTER_ENTITY_ID: Final = "lightning_counter_entity_id"
CONF_LIGHTNING_AZIMUTH_ENTITY_ID: Final = "lightning_azimuth_entity_id"
CONF_LOCATION_ENTITY_ID: Final = "location_entity_id"
CONF_ANALYSIS_RADIUS_KM: Final = "analysis_radius_km"
CONF_LIGHTNING_TRIGGER_RADIUS_KM: Final = "lightning_trigger_radius_km"
CONF_MIN_ANALYSIS_INTERVAL_SECONDS: Final = "min_analysis_interval_seconds"
CONF_STALE_CLEAR_SECONDS: Final = "stale_clear_seconds"
CONF_RAINVIEWER_ZOOM: Final = "rainviewer_zoom"
CONF_RAINVIEWER_FRAMES: Final = "rainviewer_frames"
CONF_CORE_WATCH_DBZ: Final = "core_watch_dbz"
CONF_CORE_WARNING_DBZ: Final = "core_warning_dbz"
CONF_CORE_URGENT_DBZ: Final = "core_urgent_dbz"
CONF_WARNING_CORE_DISTANCE_KM: Final = "warning_core_distance_km"
CONF_URGENT_CORE_DISTANCE_KM: Final = "urgent_core_distance_km"
CONF_MIN_CORE_PIXELS: Final = "min_core_pixels"
CONF_WARNING_LIGHTNING_DISTANCE_KM: Final = "warning_lightning_distance_km"
CONF_URGENT_LIGHTNING_DISTANCE_KM: Final = "urgent_lightning_distance_km"

DEFAULT_ANALYSIS_RADIUS_KM: Final = 80
DEFAULT_LIGHTNING_TRIGGER_RADIUS_KM: Final = 30
DEFAULT_MIN_ANALYSIS_INTERVAL_SECONDS: Final = 60
DEFAULT_STALE_CLEAR_SECONDS: Final = 900
DEFAULT_RAINVIEWER_ZOOM: Final = 7
DEFAULT_RAINVIEWER_FRAMES: Final = 4
DEFAULT_CORE_WATCH_DBZ: Final = 50
DEFAULT_CORE_WARNING_DBZ: Final = 55
DEFAULT_CORE_URGENT_DBZ: Final = 60
DEFAULT_WARNING_CORE_DISTANCE_KM: Final = 25
DEFAULT_URGENT_CORE_DISTANCE_KM: Final = 15
DEFAULT_MIN_CORE_PIXELS: Final = 2
DEFAULT_WARNING_LIGHTNING_DISTANCE_KM: Final = 20
DEFAULT_URGENT_LIGHTNING_DISTANCE_KM: Final = 8

OPTIONAL_CONF_DEFAULTS: Final = {
    CONF_ANALYSIS_RADIUS_KM: DEFAULT_ANALYSIS_RADIUS_KM,
    CONF_LIGHTNING_TRIGGER_RADIUS_KM: DEFAULT_LIGHTNING_TRIGGER_RADIUS_KM,
    CONF_MIN_ANALYSIS_INTERVAL_SECONDS: DEFAULT_MIN_ANALYSIS_INTERVAL_SECONDS,
    CONF_STALE_CLEAR_SECONDS: DEFAULT_STALE_CLEAR_SECONDS,
    CONF_RAINVIEWER_ZOOM: DEFAULT_RAINVIEWER_ZOOM,
    CONF_RAINVIEWER_FRAMES: DEFAULT_RAINVIEWER_FRAMES,
    CONF_CORE_WATCH_DBZ: DEFAULT_CORE_WATCH_DBZ,
    CONF_CORE_WARNING_DBZ: DEFAULT_CORE_WARNING_DBZ,
    CONF_CORE_URGENT_DBZ: DEFAULT_CORE_URGENT_DBZ,
    CONF_WARNING_CORE_DISTANCE_KM: DEFAULT_WARNING_CORE_DISTANCE_KM,
    CONF_URGENT_CORE_DISTANCE_KM: DEFAULT_URGENT_CORE_DISTANCE_KM,
    CONF_MIN_CORE_PIXELS: DEFAULT_MIN_CORE_PIXELS,
    CONF_WARNING_LIGHTNING_DISTANCE_KM: DEFAULT_WARNING_LIGHTNING_DISTANCE_KM,
    CONF_URGENT_LIGHTNING_DISTANCE_KM: DEFAULT_URGENT_LIGHTNING_DISTANCE_KM,
}

PARAMETER_SPECS: Final = {
    CONF_ANALYSIS_RADIUS_KM: {"min": 10, "max": 150, "step": 1, "unit": "km"},
    CONF_LIGHTNING_TRIGGER_RADIUS_KM: {"min": 5, "max": 150, "step": 1, "unit": "km"},
    CONF_MIN_ANALYSIS_INTERVAL_SECONDS: {"min": 30, "max": 3600, "step": 10, "unit": "s"},
    CONF_STALE_CLEAR_SECONDS: {"min": 300, "max": 7200, "step": 60, "unit": "s"},
    CONF_RAINVIEWER_ZOOM: {"min": 6, "max": 9, "step": 1},
    CONF_RAINVIEWER_FRAMES: {"min": 1, "max": 8, "step": 1},
    CONF_CORE_WATCH_DBZ: {"min": 35, "max": 75, "step": 1, "unit": "dBZ"},
    CONF_CORE_WARNING_DBZ: {"min": 35, "max": 75, "step": 1, "unit": "dBZ"},
    CONF_CORE_URGENT_DBZ: {"min": 35, "max": 75, "step": 1, "unit": "dBZ"},
    CONF_WARNING_CORE_DISTANCE_KM: {"min": 1, "max": 100, "step": 1, "unit": "km"},
    CONF_URGENT_CORE_DISTANCE_KM: {"min": 1, "max": 100, "step": 1, "unit": "km"},
    CONF_MIN_CORE_PIXELS: {"min": 1, "max": 512, "step": 1, "unit": "px"},
    CONF_WARNING_LIGHTNING_DISTANCE_KM: {"min": 1, "max": 100, "step": 1, "unit": "km"},
    CONF_URGENT_LIGHTNING_DISTANCE_KM: {"min": 1, "max": 100, "step": 1, "unit": "km"},
}

ATTR_LEVEL: Final = "level"
ATTR_SUMMARY: Final = "summary"
ATTR_EVIDENCE_KIND: Final = "evidence_kind"
ATTR_MAX_DBZ: Final = "max_dbz"
ATTR_CORE_DISTANCE_KM: Final = "core_distance_km"
ATTR_CORE50_DISTANCE_KM: Final = "core50_distance_km"
ATTR_CORE55_DISTANCE_KM: Final = "core55_distance_km"
ATTR_CORE60_DISTANCE_KM: Final = "core60_distance_km"
ATTR_CORE_WATCH_DISTANCE_KM: Final = "core_watch_distance_km"
ATTR_CORE_WARNING_DISTANCE_KM: Final = "core_warning_distance_km"
ATTR_CORE_URGENT_DISTANCE_KM: Final = "core_urgent_distance_km"
ATTR_LIGHTNING_DISTANCE_KM: Final = "lightning_distance_km"
ATTR_LIGHTNING_AZIMUTH_DEGREES: Final = "lightning_azimuth_degrees"
ATTR_LIGHTNING_LATITUDE: Final = "lightning_latitude"
ATTR_LIGHTNING_LONGITUDE: Final = "lightning_longitude"
ATTR_LIGHTNING_CORE_DISTANCE_KM: Final = "lightning_core_distance_km"
ATTR_FRAME_AGE_SECONDS: Final = "frame_age_seconds"
ATTR_FRAME_TIME: Final = "frame_time"
ATTR_FRAMES_ANALYZED: Final = "frames_analyzed"
ATTR_SELECTED_CORE_THRESHOLD_DBZ: Final = "selected_core_threshold_dbz"
ATTR_SELECTED_CORE_DISTANCE_KM: Final = "selected_core_distance_km"
ATTR_SELECTED_CORE_AREA_KM2: Final = "selected_core_area_km2"
ATTR_SELECTED_CORE_PIXEL_COUNT: Final = "selected_core_pixel_count"
ATTR_SELECTED_CORE_MAX_DBZ: Final = "selected_core_max_dbz"
ATTR_CORE_COUNT: Final = "core_count"
ATTR_STORM_CORES: Final = "storm_cores"
ATTR_SELECTED_CORE_LATITUDE: Final = "selected_core_latitude"
ATTR_SELECTED_CORE_LONGITUDE: Final = "selected_core_longitude"
ATTR_STORM_MOTION_BEARING: Final = "storm_motion_bearing"
ATTR_STORM_MOTION_SPEED_KMH: Final = "storm_motion_speed_kmh"
ATTR_STORM_APPROACHING: Final = "storm_approaching"
ATTR_STORM_ETA_MINUTES: Final = "storm_eta_minutes"
ATTR_DBZ_TREND: Final = "dbz_trend"
ATTR_DISTANCE_TREND: Final = "distance_trend"
ATTR_CONFIDENCE_SCORE: Final = "confidence_score"
ATTR_CONFIDENCE_LEVEL: Final = "confidence_level"
ATTR_LIGHTNING_TRIGGERED: Final = "lightning_triggered"
ATTR_LIGHTNING_COUNTER_DELTA: Final = "lightning_counter_delta"
ATTR_LIGHTNING_NEW_STRIKE: Final = "lightning_new_strike"
ATTR_HAS_CURRENT_SIGNAL: Final = "has_current_signal"
ATTR_STALE: Final = "is_stale"
ATTR_LAST_ERROR: Final = "last_error"
ATTR_LIGHTNING_DIAGNOSTICS: Final = "lightning_diagnostics"
ATTR_RAINVIEWER_DIAGNOSTICS: Final = "radar_diagnostics"
ATTR_LOCATION_SOURCE: Final = "location_source"
ATTR_SOURCE_STATUS: Final = "source_status"
ATTR_DEGRADATION_REASONS: Final = "degradation_reasons"

RISK_LEVEL_NONE: Final = "none"
RISK_LEVEL_WATCH: Final = "watch"
RISK_LEVEL_WARNING: Final = "warning"
RISK_LEVEL_URGENT: Final = "urgent"
RISK_LEVEL_UNAVAILABLE: Final = "unavailable"

EVIDENCE_KIND_NONE: Final = "none"
EVIDENCE_KIND_RADAR_STORM: Final = "radar_storm"
EVIDENCE_KIND_RADAR_HAIL: Final = "radar_hail"
EVIDENCE_KIND_LIGHTNING_ONLY: Final = "lightning_only"
EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING: Final = "radar_hail_with_lightning"
EVIDENCE_KIND_UNAVAILABLE: Final = "unavailable"

EVIDENCE_KINDS: Final = (
    EVIDENCE_KIND_NONE,
    EVIDENCE_KIND_RADAR_STORM,
    EVIDENCE_KIND_RADAR_HAIL,
    EVIDENCE_KIND_LIGHTNING_ONLY,
    EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING,
    EVIDENCE_KIND_UNAVAILABLE,
)

RISK_LEVELS = [
    RISK_LEVEL_NONE,
    RISK_LEVEL_WATCH,
    RISK_LEVEL_WARNING,
    RISK_LEVEL_URGENT,
    RISK_LEVEL_UNAVAILABLE,
]

SERVICE_FORCE_UPDATE: Final = "force_update"

COORDINATOR_KEY: Final = "coordinator"
DATA_KEY_RESULT: Final = "hail_risk_result"
