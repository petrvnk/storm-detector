# Changelog

## 0.0.3 - 2026-07-14

### Fixed

- Restored the adaptive card's useful storm-core details: selected-core intensity and area now appear alongside distance, motion, and ETA.
- Scale the schematic radar to distant detected cores instead of pinning every core beyond 50 km to a fixed 50 km scale.

### Changed

- Increased the default analysis radius from 50 km to 80 km so strong nearby storms just outside the old hard boundary produce an early `watch`; warning and urgent proximity gates remain unchanged.

## 0.0.2 - 2026-07-14

### Fixed

- Detect connected storm activity in the five-dBZ band below the configured watch threshold, so a valid 46-49 dBZ nearby echo is surfaced as `watch` instead of a green clear state.
- Preserve the connected-component minimum-pixel filter for near-watch activity; isolated high-reflectivity pixels still do not create an alert.

### Changed

- Use precise clear-state wording that says no strong nearby radar core was detected rather than implying that all weather is safe.
- Describe radar-only `watch` evidence as nearby storm activity without making a hail claim.

## 0.0.1 - 2026-07-13

Initial HACS-ready prerelease.

### Fixed

- Treat old Blitzortung event timestamps as normal idle lightning context instead of an actionable source degradation, while continuing to exclude old strike distance/counter values from risk classification.

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
- Stable additive `evidence_kind` payload/entity attribute and evidence-aware notification wording.
- Fail-closed radar outage semantics: lightning-only events are capped at thunderstorm `warning`, while `urgent` requires current urgent radar evidence.
- HACS validation GitHub Actions workflow.
- Unit/scaffold tests for staged implementation slices.

### Limitations

- This is a pre-release integration and should be validated in a real Home Assistant instance before relying on it for protective actions.
- Hail risk is heuristic and based on radar reflectivity plus lightning context; it is not an official weather warning.
- Migration from another hail-risk alerting setup should happen only after parity verification in the target Home Assistant environment.
