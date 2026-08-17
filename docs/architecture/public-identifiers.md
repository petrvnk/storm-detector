# Storm Detector Public Identifiers

Status: frozen for implementation after Petr approval.
Scope: public identifiers only. This document intentionally does not rename runtime files by itself.

## Repository and package identity

| Surface | Frozen identifier |
|---|---|
| GitHub repository | `petrvnk/storm-detector` |
| Repository slug | `storm-detector` |
| Python/package distribution slug | `storm-detector` |
| Home Assistant domain | `storm_detector` |
| Integration display name | `Storm Detector` |
| Device name | `Storm Detector` |
| Runtime package path | `custom_components/storm_detector/` |
| Logger namespace | `custom_components.storm_detector` |
| HACS name | `Storm Detector` |
| First Storm Detector release | `v0.1.0` |

No old `v0.0.x` tags are part of the new repository release contract.

## Frontend identifiers

| Surface | Frozen identifier |
|---|---|
| Custom card tag | `custom:storm-detector-card` |
| Web Component name | `storm-detector-card` |
| JavaScript file | `storm-detector-card.js` |
| Home Assistant resource URL | `/storm_detector/storm-detector-card.js` |
| Frontend source path | `custom_components/storm_detector/frontend/storm-detector-card.js` |
| Recommended example path | `examples/storm-detector-card.yaml` |

The old `custom:radar-hail-risk-card` tag must not be registered as an alias in Storm Detector.

## Blueprint identifiers and service policy

| Surface | Frozen identifier |
|---|---|
| Notification blueprint path | `blueprints/automation/storm_detector/storm_notification.yaml` |
| Blueprint name | `Storm Detector notification` |
| Notification tag | `storm_detector` |

Storm Detector `v0.1.0` exposes no custom Home Assistant service. Do not publish, document, translate, register, or test `storm_detector.force_update` as part of the rename; the current baseline does not register a force-update service. Cleanup of any dead runtime force-update constant belongs to a separate backend refactor, not to the public contract.

## Main entity contract

These four entities are enabled by default and form the minimum automation/dashboard contract:

| Entity ID | State | Purpose |
|---|---|---|
| `sensor.storm_detector_level` | `none`, `watch`, `warning`, `urgent`, `unavailable` | Primary machine-readable attention level. |
| `sensor.storm_detector_summary` | short text | Primary human-readable summary. |
| `binary_sensor.storm_detector_active` | `on`/`off` | Current non-clear storm/attention signal is active and not merely a stale pending level. |
| `binary_sensor.storm_detector_data_stale` | `on`/`off` | At least one required current source is stale/untrusted. |

Home Assistant may append suffixes if a user already has colliding entity IDs. The default clean-install names above are the public contract.

## Diagnostic entity contract

Diagnostic entities use the same `storm_detector` prefix and are disabled by default unless listed otherwise by Home Assistant platform rules.

| Entity ID | Category | Purpose |
|---|---|---|
| `sensor.storm_detector_max_dbz` | diagnostic | Selected/current radar core intensity. |
| `sensor.storm_detector_core_distance` | diagnostic | Distance to selected storm core. |
| `sensor.storm_detector_lightning_distance` | diagnostic | Distance to current valid lightning context. |
| `sensor.storm_detector_frame_age` | diagnostic | Age of evaluated radar frame. |
| `sensor.storm_detector_last_error` | diagnostic | Last user-safe source/runtime error. |
| `device_tracker.storm_detector_storm_core` | diagnostic | Approximate selected storm-core location when current radar supports it. |

## Attribute contract for automations and card UX

The level sensor attributes below are the minimum stable integration surface for evidence-aware automations and the adaptive card:

- `summary`
- `evidence_kind`
- `is_stale`
- `has_current_signal`
- `source_status`
- `degradation_reasons`
- `max_dbz`
- `core50_distance_km`
- `core55_distance_km`
- `core60_distance_km`
- `core_watch_distance_km`
- `core_warning_distance_km`
- `core_urgent_distance_km`
- `selected_core_threshold_dbz`
- `selected_core_distance_km`
- `selected_core_latitude`
- `selected_core_longitude`
- `selected_core_area_km2`
- `selected_core_pixel_count`
- `selected_core_max_dbz`
- `storm_cores`
- `core_count`
- `storm_motion_bearing`
- `storm_motion_speed_kmh`
- `storm_approaching`
- `storm_eta_minutes`
- `dbz_trend`
- `distance_trend`
- `confidence_score`
- `confidence_level`
- `lightning_distance_km`
- `lightning_azimuth_degrees`
- `lightning_latitude`
- `lightning_longitude`
- `lightning_core_distance_km`
- `lightning_triggered`
- `lightning_new_strike`
- `lightning_counter_delta`
- `frame_age_seconds`
- `frame_time`
- `frames_analyzed`
- `location_source`
- `radar_diagnostics`
- `lightning_diagnostics`
- `radar_overlay`

The rename implementation must preserve every attribute currently emitted by the baseline level sensor, not only the minimum subset above. Regression tests must assert the full baseline attribute-key set survives the rename, including threshold-distance attributes (`core50_distance_km`, `core55_distance_km`, `core60_distance_km`, `core_watch_distance_km`, `core_warning_distance_km`, `core_urgent_distance_km`), selected-core coordinates (`selected_core_latitude`, `selected_core_longitude`), lightning trigger/delta fields (`lightning_triggered`, `lightning_new_strike`, `lightning_counter_delta`), and `radar_overlay`. Intentional attribute removals or semantic changes require separate Petr approval before implementation.

Automations must branch on `evidence_kind`, not parse localized summary text.

## Evidence identifiers

Allowed evidence identifiers:

- `none`
- `radar_storm`
- `lightning_only`
- `radar_hail`
- `radar_hail_with_lightning`
- `unavailable`

`radar_hail` and `radar_hail_with_lightning` are preserved only for radar-supported possible-hail evidence. They are not product/domain identifiers and must not be used to name the integration, repository, package, card, resource, blueprint, service, or default entities.

## Legacy identifier policy

Reject these old public identifiers outside historical attribution, migration notes, or explicit legacy-audit tests:

- `Radar Hail Risk`
- `radar-hail-risk`
- `radar_hail_risk`
- `custom:radar-hail-risk-card`
- `/radar_hail_risk/radar-hail-risk-card.js`
- `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`
- `sensor.radar_hail_risk_level`
- `sensor.radar_hail_risk_summary`
- `binary_sensor.radar_hail_risk_active`
- `binary_sensor.radar_hail_risk_data_stale`

Do not provide compatibility aliases, migration shims, custom services, duplicate card tags, duplicate blueprint paths, or old-domain config-entry support unless Petr approves a separate compatibility project.

## Implementation notes for the rename phase

- Use `git mv` for package, card, blueprint, and examples so history remains traceable.
- Update tests before code where deterministic behavior is affected by public identifiers.
- Public identifier tests should fail on old product/domain strings while allowlisting only legitimate radar-supported possible-hail evidence terms (`radar_hail`, `radar_hail_with_lightning`) and hail-specific safety copy in current possible-hail contexts.
- Preserve all thresholds and algorithm behavior during the rename.
