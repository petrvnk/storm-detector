# Changelog

## 0.0.1 - unreleased

Initial HACS-readiness build.

### Added

- Home Assistant custom integration metadata and config/options flow.
- RainViewer radar metadata/tile helpers and storm-core detection.
- Blitzortung-compatible Home Assistant lightning source normalization with radar-only fallback.
- DataUpdateCoordinator and sensor/binary sensor/device tracker entities.
- Diagnostics/resilience helpers for stale and degraded source data.
- Threshold-aware risk model that treats 50+/55+/60+ dBZ cores differently and gates stale radar data out of active classification.
- Connected-component radar-core metadata (`selected_core_area_km2`, `selected_core_pixel_count`, `selected_core_max_dbz`, `core_count`) for more robust storm-core detection.
- Configurable minimum connected-core size (`min_core_pixels`) with bounded parameter flow/validation and documentation.
- Storm motion/trend attributes (`storm_motion_bearing`, `storm_motion_speed_kmh`, `storm_approaching`, `storm_eta_minutes`, `dbz_trend`, `distance_trend`) estimated from recent radar frames.
- Optional lightning azimuth/bearing source with projected strike coordinates and lightning-to-radar-core distance.
- Confidence score/level (`confidence_score`, `confidence_level`) combining radar health, core compactness, lightning corroboration, and storm approach trend.
- Bounded config/options number selectors with validation for radar radius, lightning distances, dBZ thresholds, stale timeout, RainViewer zoom/frames, and analysis cadence.
- Manual Lovelace dashboard snippets in `README.md`.
- Opt-in notification blueprint with Czech and English titles.
- HACS validation GitHub Actions workflow.
- Unit/scaffold tests for staged implementation slices.

### Limitations

- This is a pre-release integration and should be validated in a real Home Assistant instance before relying on it for protective actions.
- Hail risk is heuristic and based on radar reflectivity plus lightning context; it is not an official weather warning.
- Migration from another hail-risk alerting setup should happen only after parity verification in the target Home Assistant environment.
