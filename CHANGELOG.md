# Changelog

## Unreleased

## 0.2.1 - 2026-08-19

### Changed

- Add public installation, upgrade, uninstall, troubleshooting, privacy, support, and
  contribution guidance with representative released-card screenshots and one-click
  HACS and blueprint import links.
- Hide the unsupported default branch from HACS and add automated dependency updates,
  a pull-request checklist, and private vulnerability-reporting guidance.
- Move checkout and Python setup workflows to immutable Node 24 action revisions.
- Pin HACS and Hassfest container execution to immutable image digests and import the
  notification blueprint from the released tag instead of the mutable default branch.

## 0.2.0 - 2026-08-19

### Changed

- Validate the integration against both its minimum supported Home Assistant release
  and the current stable Home Assistant test stack, with a dedicated Hassfest workflow.
- Cache successful radar-frame analyses in a bounded in-memory LRU so unchanged frames
  are not downloaded and decoded again; a rolling four-frame window normally fetches
  only the newly published frame.
- Align RainViewer metadata refreshes with a five-minute TTL while retaining the local
  lightning evaluation cadence.
- Add jittered exponential retry delays and bounded cooldowns for transient network,
  `408`, `429`, and `5xx` responses, including numeric `Retry-After` handling.

### Fixed

- Declare the Home Assistant HTTP dependency and config-entry-only schema so the bundled
  frontend route is registered before the HTTP router starts accepting requests.
- Preserve the last successful radar metadata during transient upstream outages so the
  existing frame-age and stale rules control degradation and recovery.
- Do not report the event-driven lightning source as stale merely because no strikes
  occurred; old event values remain excluded from risk evidence, while explicitly
  unavailable or missing entities still degrade the source.

## 0.1.0 - 2026-08-17

### Changed

- Rename the integration, repository surfaces, entities, custom card, and notification
  blueprint to the frozen Storm Detector public contract.
- Localize every card-owned visible and accessibility string for Czech with English
  fallback, and keep current radar or lightning evidence when the other source degrades.
- Qualify all hail wording as radar-supported possibility and keep official-warning advice.

### Removed

- Remove obsolete private release-candidate bundle and handoff artifacts.

## 0.0.7 - 2026-07-23

### Fixed

- Center the live radar viewport exactly on the monitored home location and crop the
  surrounding RainViewer tile mosaic symmetrically around that point.
- Preserve a square, north-up Web Mercator viewport on desktop and mobile so distance
  rings remain circular and radar imagery is no longer stretched or apparently rotated.

## 0.0.6 - 2026-07-22

### Added

- Display the synchronized live RainViewer radar frame directly in the custom card,
  with every detected storm core projected over the same frame and the risk-driving
  core highlighted.
- Add fail-closed live-overlay states, visible RainViewer attribution, mobile marker
  sizing, reduced-motion behavior, and configurable `auto`, `off`, and `always` modes.

### Security

- Validate RainViewer hosts, frame paths, templates, and payload sizes before exposing
  renderable browser URLs; stale, malformed, or oversized overlays fall back safely to
  the schematic view.

## 0.0.5 - 2026-07-14

### Changed

- Render every currently detected radar core in the schematic while keeping the core
  that drives the risk state larger and highlighted.
- Show the number of detected cores and label the selected distance as the main core.

## 0.0.4 - 2026-07-14

### Fixed

- Draw the schematic core at its geographic bearing from home instead of incorrectly
  using the storm's direction of motion.
- Suppress misleading "approaching" and ETA labels for slow radial drift; an approach
  now requires at least 10 km/h closing speed and ETA is shown only up to 180 minutes.

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
