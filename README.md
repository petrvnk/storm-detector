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

## Current Simple RC install/test route — manual archive only

The **checksum-verified manual archive** is the only valid current install/test route for this unpushed RC. Verify the SHA-256 supplied with `radar_hail_risk-simple-rc.zip` before extracting it; do not substitute a repository checkout or HACS download.

1. Run `sha256sum radar_hail_risk-simple-rc.zip` and compare the complete digest with the separately supplied reviewed checksum.
2. Extract the verified ZIP outside the Home Assistant configuration directory.
3. Copy only `custom_components/radar_hail_risk/` from the extracted archive to `<HA config>/custom_components/radar_hail_risk/`.
4. Restart Home Assistant.
5. Settings → Devices & services → Add integration → **Radar Hail Risk**.
6. On the first setup screen, optionally select one location entity (for example `zone.home`) and a matching lightning distance/counter pair. Leave the location blank to use Home Assistant's core location; leave both lightning fields blank for radar-only mode.
7. Keep the safe defaults for the first run. Technical thresholds, radar workload, stale timeout, and optional lightning azimuth are available later under **Configure → Options**.

### Conditional future HACS route (not currently authorized)

HACS is **not** an equivalent current path. HACS instructions apply only after separately authorized publication of this exact reviewed source and SHA-256 checksum. If that separate authorization is given, add the authorized repository URL as a HACS custom repository in category `Integration`, install **Radar Hail Risk**, restart Home Assistant, and then use the same setup flow above. Until then, do not install or test this RC through HACS.

## Location and advanced options

By default, Radar Hail Risk uses the Home Assistant core location (`hass.config`) as the single source of truth for radar center and distance calculations. During initial setup you can instead select a `zone`, `person`, or `device_tracker` with latitude/longitude attributes, for example `zone.home`. This is recommended when another integration already owns the canonical home/test location.

If the configured location entity is missing or has no coordinates, the integration degrades to `unavailable` with a diagnostic such as `missing_location_entity` instead of silently falling back to another position.

The first setup screen deliberately contains only location, lightning distance, and lightning counter. The advanced options flow exposes bounded selectors for the optional lightning azimuth and these tuning parameters:

| Parameter | Default | Allowed range | Meaning |
|---|---:|---:|---|
| `analysis_radius_km` | 50 km | 10–150 km | Radar search radius around the configured location. |
| `lightning_trigger_radius_km` | 30 km | 5–150 km | Nearby lightning radius that can trigger or strengthen evaluation. |
| `warning_lightning_distance_km` | 20 km | 1–100 km | Lightning distance contributing to `warning`. |
| `urgent_lightning_distance_km` | 8 km | 1–100 km | Legacy proximity boundary retained for compatibility; lightning alone is capped at `warning`, while current urgent radar evidence is required for `urgent`. |
| `core_watch_dbz` | 50 dBZ | 35–75 dBZ | Radar core threshold for `watch`. |
| `core_warning_dbz` | 55 dBZ | 35–75 dBZ | Radar core threshold for `warning`. |
| `core_urgent_dbz` | 60 dBZ | 35–75 dBZ | Radar core threshold for `urgent`. |
| `min_core_pixels` | 2 px | 1–512 px | Minimum connected pixels required to count a core. |
| `warning_core_distance_km` | 25 km | 1–100 km | Distance for warning-level radar cores. |
| `urgent_core_distance_km` | 15 km | 1–100 km | Distance for urgent-level radar cores. |
| `rainviewer_frames` | 4 | 1–8 | Recent radar frames used for current state/trend. |
| `rainviewer_zoom` | 7 | 6–9 | RainViewer tile zoom; higher is more detailed but heavier. |
| `min_analysis_interval_seconds` | 60 s | 30–3600 s | Minimum interval between expensive radar analyses. |
| `stale_clear_seconds` | 900 s | 300–7200 s | Source age after which data is treated as stale and gated out. |

Validation also enforces sensible relationships: `watch < warning < urgent` dBZ thresholds, warning distances greater than or equal to urgent distances, and lightning trigger radius greater than or equal to warning lightning distance.

## Diagnostics and source status

Every risk entity includes support-oriented attributes that help explain degraded behavior and threshold-aware radar cores:

- `evidence_kind` — stable discriminator: `none`, `radar_storm`, `radar_hail`, `lightning_only`, `radar_hail_with_lightning`, or `unavailable`. Automations should use this instead of parsing summary text.
- `location_source` — `hass.config` or the selected `zone` / `person` / `device_tracker`.
- `core_watch_distance_km`, `core_warning_distance_km`, `core_urgent_distance_km` — authoritative core distances at the configured watch/warning/urgent thresholds used by the risk model.
- `core50_distance_km`, `core55_distance_km`, `core60_distance_km` — compatibility diagnostics at fixed 50/55/60 dBZ thresholds; they do not override the configured classification thresholds.
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

Lightning-only evidence can publish an immediate thunderstorm warning after a new nearby strike, but never `urgent` and never a positive hail claim. `urgent` always requires current urgent radar-core evidence. If radar is stale or unusable, the integration fails closed to `unavailable` unless current nearby lightning supports a degraded `lightning_only` warning.

## Entities

Entity IDs may differ depending on Home Assistant naming. The examples below assume default names such as:

| Entity | Purpose |
|---|---|
| `sensor.radar_hail_risk_level` | `none`, `watch`, `warning`, `urgent`, `unavailable` |
| `sensor.radar_hail_risk_summary` | human-readable summary |
| `binary_sensor.radar_hail_risk_active` | true when the risk level is active |
| `binary_sensor.radar_hail_risk_data_stale` | true when source data is stale |

These four entities are enabled by default for new installs. Diagnostic sensors (`Max dBZ`, core/lightning distance, frame age, and last error) and the storm-core device tracker remain available with their existing unique IDs, but are disabled by default for new entity-registry entries. Enable them from the integration's entity list when troubleshooting. Existing enabled entities remain enabled. Adjust entity IDs in examples to match your Home Assistant instance.

## Lovelace dashboard snippets and examples

These snippets are **manual examples only**: the integration provides entities only and never writes dashboards automatically. Copy one of the example files and adjust entity IDs if you renamed the integration:

```text
examples/lovelace/native-card.yaml      # native HA cards, no custom dependencies
examples/lovelace/mushroom-card.yaml    # Mushroom card variant
examples/lovelace/weather-tab.yaml      # detailed weather/storm view
examples/radar-hail-risk-card.yaml      # custom JS Lovelace card config
```

### Custom Lovelace card

A polished cockpit-style web component is available in `frontend/radar-hail-risk-card.js`. Add it as a Lovelace resource (for example through HACS/custom hosting or a `/local/` copy) and use:

```yaml
type: custom:radar-hail-risk-card
title: Bouřky v okolí
```

The card uses `level`, `evidence_kind`, and source freshness to progressively disclose only current user-relevant information. A clear or unavailable state stays compact; storm, lightning, and radar-supported possible-hail states show only trustworthy distance, movement, ETA, and corroborating-lightning facts that are actually available.

### Minimal default-entity card

```yaml
type: entities
title: Radar Hail Risk
entities:
  - entity: sensor.radar_hail_risk_level
    name: Risk level
  - entity: sensor.radar_hail_risk_summary
    name: Summary
  - entity: binary_sensor.radar_hail_risk_active
    name: Active risk
  - entity: binary_sensor.radar_hail_risk_data_stale
    name: Data stale
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
  - entity: binary_sensor.radar_hail_risk_data_stale
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

- risk level sensor (`sensor.radar_hail_risk_level`)
- optional summary sensor (`sensor.radar_hail_risk_summary`; otherwise the blueprint reads the level sensor's `summary` attribute)
- notify service, e.g. `notify.mobile_app_phone`
- minimum notification level: `watch`, `warning`, or `urgent`
- title language: `en` or `cs`
- cooldown in minutes

The blueprint is opt-in and does **not** create automations or dashboard changes by itself.

Notification titles and messages use the level sensor's machine-readable `evidence_kind` attribute. Lightning-only warnings say thunderstorm/lightning and “hail not confirmed”; radar-supported warnings say “possible hail”. Missing or unknown evidence values fall back to conservative weather wording without a hail claim.

## Czech notification wording

The blueprint supports Czech titles:

| Level / evidence | Czech title |
|---|---|
| `watch` + `radar_storm` | Sledování bouřky |
| `warning` + `lightning_only` | Blízká bouřka / blesky poblíž |
| `warning` + radar hail evidence | Možné kroupy poblíž |
| `urgent` + radar hail evidence | Vysoké riziko krup |

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

## Private colleague-test bundle

Build the reviewed local archive from the explicit allowlist with:

```bash
uv run python scripts/build_colleague_bundle.py --output dist/radar_hail_risk-simple-rc.zip
sha256sum dist/radar_hail_risk-simple-rc.zip
```

The generator normalizes ZIP member order, timestamps, and permissions; rejects
symlinked, missing, secret-like, generated, research, and local Home Assistant paths;
and performs clean-room extraction/layout checks before keeping the output. Run it a
second time to a different temporary path and compare SHA-256 values when verifying a
handoff. The archive is for private testing only: building it does not publish a HACS
release, push a tag, or install anything into Home Assistant. For this unpushed RC,
the checksum-verified manual archive remains the only valid current install/test route;
HACS remains conditional on separately authorized publication of the exact reviewed
source and SHA-256 checksum.

The colleague install/test/upgrade/rollback/uninstall procedure is in
[`docs/colleague-test-checklist.md`](docs/colleague-test-checklist.md). The minimal card
shipped in the archive is `examples/lovelace/native-card.yaml`.

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
