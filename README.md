# Radar Hail Risk

Home Assistant custom integration for local hail/storm-core risk estimation using:

- **RainViewer radar** for reflectivity / storm-core detection
- **optional Blitzortung-compatible Home Assistant sensors** for nearby lightning context
- **Home Assistant location/config entry options** for local thresholds

Open-Meteo is intentionally **not** part of the hail-risk decision path. The integration can run in radar-only mode; Blitzortung is recommended for better confidence but is not required.

## Status

This repository is being built in staged review gates for HACS readiness.

Current implemented slices:

- HACS/custom integration skeleton
- RainViewer metadata/tile helpers and storm-core detector
- Blitzortung-compatible lightning source normalization
- Data coordinator and Home Assistant entities
- Options/diagnostics/resilience hardening
- Dashboard snippets and notification blueprint

## Install via HACS custom repository

1. HACS → Integrations → three-dot menu → Custom repositories.
2. Add this repository URL.
3. Category: `Integration`.
4. Install **Radar Hail Risk**.
5. Restart Home Assistant.
6. Settings → Devices & services → Add integration → **Radar Hail Risk**.
7. Optional but recommended: install/configure a Blitzortung-compatible integration and select its distance/counter sensors. If you skip this, Radar Hail Risk runs in radar-only mode.

## Location and configurable parameters

By default, Radar Hail Risk uses the Home Assistant core location (`hass.config`) as the single source of truth for radar center and distance calculations. In the options flow you can instead select a `zone`, `person`, or `device_tracker` with latitude/longitude attributes, for example `zone.home`. This is recommended when another integration already owns the canonical home/test location.

If the configured location entity is missing or has no coordinates, the integration degrades to `unavailable` with a diagnostic such as `missing_location_entity` instead of silently falling back to another position.

The config/options flow exposes bounded number selectors for the main tuning parameters:

| Parameter | Default | Allowed range | Meaning |
|---|---:|---:|---|
| `analysis_radius_km` | 50 km | 10–150 km | Radar search radius around the configured location. |
| `lightning_trigger_radius_km` | 30 km | 5–150 km | Nearby lightning radius that can trigger or strengthen evaluation. |
| `warning_lightning_distance_km` | 20 km | 1–100 km | Lightning distance contributing to `warning`. |
| `urgent_lightning_distance_km` | 8 km | 1–100 km | Lightning distance contributing to `urgent`. |
| `core_watch_dbz` | 50 dBZ | 35–75 dBZ | Radar core threshold for `watch`. |
| `core_warning_dbz` | 55 dBZ | 35–75 dBZ | Radar core threshold for `warning`. |
| `core_urgent_dbz` | 60 dBZ | 35–75 dBZ | Radar core threshold for `urgent`. |
| `warning_core_distance_km` | 25 km | 1–100 km | Distance for warning-level radar cores. |
| `urgent_core_distance_km` | 15 km | 1–100 km | Distance for urgent-level radar cores. |
| `rainviewer_frames` | 4 | 1–8 | Recent radar frames used for current state/trend. |
| `rainviewer_zoom` | 7 | 6–9 | RainViewer tile zoom; higher is more detailed but heavier. |
| `min_analysis_interval_seconds` | 60 s | 30–3600 s | Minimum interval between expensive radar analyses. |
| `stale_clear_seconds` | 900 s | 300–7200 s | Source age after which data is treated as stale and gated out. |

Validation also enforces sensible relationships: `watch < warning < urgent` dBZ thresholds, warning distances greater than or equal to urgent distances, and lightning trigger radius greater than or equal to warning lightning distance.

## Diagnostics and source status

Every risk entity includes support-oriented attributes that help explain degraded behavior and threshold-aware radar cores:

- `location_source` — `hass.config` or the selected `zone` / `person` / `device_tracker`.
- `core50_distance_km`, `core55_distance_km`, `core60_distance_km` — distances to threshold-specific radar cores used by the risk model.
- `selected_core_area_km2`, `selected_core_pixel_count`, `selected_core_max_dbz`, `core_count` — connected-component storm-core metadata used to distinguish compact cores from isolated pixels.
- `storm_motion_bearing`, `storm_motion_speed_kmh`, `storm_approaching`, `storm_eta_minutes`, `dbz_trend`, `distance_trend` — motion/trend estimate from recent radar frames when enough frame history is available.
- `lightning_azimuth_degrees`, `lightning_latitude`, `lightning_longitude`, `lightning_core_distance_km` — optional strike-position estimate and radar-core correlation when a lightning azimuth/bearing entity is configured.
- `confidence_score`, `confidence_level` — 0–100 / `low|medium|high` confidence estimate based on radar health, compact core evidence, lightning corroboration, and approach trend.
- `source_status` — compact status for `location`, `radar`, and `lightning` (`ok`, `degraded`, `stale`, `not_configured`, `error`, `skipped`).
- `degradation_reasons` — machine-readable reason codes such as `radar_source_error`, `stale_radar_frame`, or `missing_location_entity`.
- `radar_diagnostics` and `lightning_diagnostics` — source-specific debug reason codes.

Home Assistant's diagnostics download for the config entry also includes the selected options and the latest runtime status. It intentionally includes entity IDs and runtime reason codes, but no credentials.

## Lightning source modes

Radar Hail Risk supports three setup modes:

| Mode | Requirement | Behavior |
|---|---|---|
| Radar only | Home Assistant + internet access to RainViewer | Computes radar reflectivity risk without lightning confidence. |
| Radar + Blitzortung | Blitzortung-compatible HA sensors | Adds nearest-lightning distance/counter trigger context. |
| Manual lightning sensors | Any HA sensors with distance + counter values | Uses the selected sensors instead of autodetection. |

The config flow tries to autodetect sensors such as `sensor.*_lightning_distance` and `sensor.*_lightning_counter`. You can leave both fields blank for radar-only mode. If you set one lightning entity, set both.

Normal HA empty states such as `unknown`/`unavailable` from the lightning distance sensor are treated as “no current lightning distance”, not as integration failures.

## Entities

Entity IDs may differ depending on Home Assistant naming. The examples below assume default names such as:

| Entity | Purpose |
|---|---|
| `sensor.radar_hail_risk_level` | `none`, `watch`, `warning`, `urgent`, `unavailable` |
| `sensor.radar_hail_risk_summary` | human-readable summary |
| `sensor.radar_hail_risk_max_dbz` | maximum detected dBZ |
| `sensor.radar_hail_risk_core_distance` | nearest selected storm core distance |
| `sensor.radar_hail_risk_lightning_distance` | normalized lightning distance |
| `sensor.radar_hail_risk_frame_age` | age of analyzed radar frame |
| `binary_sensor.radar_hail_risk_active` | true when the risk level is active |
| `binary_sensor.radar_hail_data_stale` | true when source data is stale |

Adjust entity IDs in examples to match your Home Assistant instance.

## Lovelace dashboard snippets and examples

These snippets are **manual examples only**: the integration provides entities only and never writes dashboards automatically. Copy one of the example files and adjust entity IDs if you renamed the integration:

```text
examples/lovelace/native-card.yaml      # native HA cards, no custom dependencies
examples/lovelace/mushroom-card.yaml    # Mushroom card variant
examples/lovelace/weather-tab.yaml      # detailed weather/storm view
```

### Minimal glance card

```yaml
type: glance
title: Radar Hail Risk
entities:
  - entity: sensor.radar_hail_risk_level
    name: Risk
  - entity: sensor.radar_hail_risk_max_dbz
    name: Max dBZ
  - entity: sensor.radar_hail_risk_core_distance
    name: Core distance
  - entity: sensor.radar_hail_risk_lightning_distance
    name: Lightning
```

### Status + detail entities

```yaml
type: entities
title: Radar Hail Risk
show_header_toggle: false
entities:
  - entity: sensor.radar_hail_risk_level
    name: Risk level
  - entity: sensor.radar_hail_risk_summary
    name: Summary
  - entity: binary_sensor.radar_hail_risk_active
    name: Active risk
  - entity: binary_sensor.radar_hail_data_stale
    name: Data stale
  - type: section
    label: Radar
  - entity: sensor.radar_hail_risk_max_dbz
  - entity: sensor.radar_hail_risk_core_distance
  - entity: sensor.radar_hail_risk_frame_age
  - type: section
    label: Lightning
  - entity: sensor.radar_hail_risk_lightning_distance
```

### Mushroom-style chips/card example

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-template-card
    primary: Radar Hail Risk
    secondary: "{{ states('sensor.radar_hail_risk_summary') }}"
    icon: mdi:weather-hail
    icon_color: >-
      {% set level = states('sensor.radar_hail_risk_level') %}
      {% if level == 'urgent' %}red
      {% elif level == 'warning' %}orange
      {% elif level == 'watch' %}yellow
      {% else %}green
      {% endif %}
  - type: glance
    entities:
      - sensor.radar_hail_risk_max_dbz
      - sensor.radar_hail_risk_core_distance
      - sensor.radar_hail_risk_lightning_distance
```

## Notification blueprint

A manual automation blueprint is included at:

```text
blueprints/automation/radar_hail_risk/hail_risk_notification.yaml
```

Import/copy it into Home Assistant and choose:

- risk level sensor
- optional summary sensor
- optional max dBZ sensor
- optional lightning distance sensor
- notify service, e.g. `notify.mobile_app_phone`
- minimum notification level: `watch`, `warning`, or `urgent`
- title language: `en` or `cs`
- cooldown in minutes

The blueprint is opt-in and does **not** create automations or dashboard changes by itself.

## Czech notification wording

The blueprint supports Czech titles:

| Level | Czech title |
|---|---|
| `watch` | Sledování bouřky |
| `warning` | Varování před kroupami |
| `urgent` | Nebezpečí krup |

## Limitations and safety notes

- Radar Hail Risk is a heuristic integration, not an official warning source.
- Radar reflectivity can miss local conditions or overestimate hail risk.
- RainViewer and Blitzortung-compatible data may be delayed, unavailable, unknown after restart, or stale.
- Do not trigger safety-critical actions without local validation and fallback logic.
- Use only one active alerting setup at a time to avoid duplicate sensors/alerts.

## Credits

- Radar data source: [RainViewer](https://www.rainviewer.com/api.html)
- Lightning context: Home Assistant entities from Blitzortung-compatible integrations/sensors
- Platform: [Home Assistant](https://www.home-assistant.io/) and [HACS](https://www.hacs.xyz/)

## Release readiness

See [`docs/release-checklist.md`](docs/release-checklist.md) before publishing a tag.

Required local verification:

```bash
python -m pytest -q
python -m ruff check .
python -m compileall -q .
```

GitHub Actions also runs unit tests, Ruff, compileall, and HACS validation via `hacs/action@main`.

## Repository structure

- `custom_components/radar_hail_risk/manifest.json` – integration manifest
- `hacs.json` – HACS metadata
- `custom_components/radar_hail_risk/const.py` – constants/defaults
- `custom_components/radar_hail_risk/__init__.py` – integration entrypoint
- `custom_components/radar_hail_risk/config_flow.py` – config + options flow
- `custom_components/radar_hail_risk/coordinator.py` – data coordinator
- `custom_components/radar_hail_risk/sensor.py` – sensor platform
- `custom_components/radar_hail_risk/binary_sensor.py` – binary sensor platform
- `custom_components/radar_hail_risk/device_tracker.py` – optional storm-core tracker
- `custom_components/radar_hail_risk/lightning.py` – HA lightning-source normalization
- `custom_components/radar_hail_risk/rainviewer.py` – RainViewer ingestion/detection helpers
- `custom_components/radar_hail_risk/risk.py` – risk classification helpers
- `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml` – optional notification automation blueprint
- `examples/lovelace/` – copy-paste dashboard examples
- `tests/` – unit/scaffold tests
