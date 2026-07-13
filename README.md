# Radar Hail Risk

A Home Assistant integration that monitors **nearby thunderstorms and possible hail**.

It combines RainViewer radar with optional Home Assistant lightning sensors. The integration only reports possible hail when current radar data supports that conclusion; lightning alone is shown as a nearby thunderstorm, never as hail.

## What it does

- Detects nearby radar storm cores.
- Distinguishes a storm, lightning-only activity, and radar-supported possible hail.
- Estimates direction and arrival time when recent radar frames support a reliable estimate.
- Hides stale values and reports unavailable data instead of presenting an old event as current.
- Provides a compact adaptive Lovelace card and an optional notification blueprint.

| Evidence | User-facing meaning |
|---|---|
| `none` | No significant current activity |
| `radar_storm` | Storm core nearby |
| `lightning_only` | Lightning nearby; hail is not radar-confirmed |
| `radar_hail` | Radar indicates possible hail |
| `radar_hail_with_lightning` | Possible hail with nearby lightning |
| `unavailable` | Current detection data is unavailable |

Radar Hail Risk is heuristic only. It does not detect hail on the ground and does not provide a calibrated hail probability.

## Install with HACS

Minimum Home Assistant version: **2024.10.0**.

1. In HACS, open **Integrations**.
2. Open the menu and select **Custom repositories**.
3. Add `https://github.com/petrvnk/radar-hail-risk` as category **Integration**.
4. Install **Radar Hail Risk**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and select **Radar Hail Risk**.

### Manual installation

1. Copy `custom_components/radar_hail_risk/` into `<HA config>/custom_components/`.
2. Restart Home Assistant.
3. Add **Radar Hail Risk** from **Settings → Devices & services**.

## Setup

The initial setup has only three optional fields:

- **Location** — leave empty to use Home Assistant's configured coordinates, or select a `zone`, `person`, or `device_tracker` with latitude and longitude.
- **Lightning distance sensor** — optional distance sensor from a Blitzortung-compatible or similar integration.
- **Lightning counter sensor** — optional matching strike counter.

For radar-only mode, leave both lightning fields empty. If lightning is enabled, configure both distance and counter sensors.

The integration tries to detect compatible lightning sensors automatically. Open **Configure → Options** only when you need to change the analysis radius, radar thresholds, distance thresholds, frame count, refresh interval, stale timeout, or optional lightning azimuth. The defaults are intended to be a safe starting point.

Open-Meteo is intentionally **not** part of the detection path.

## Main entities

| Entity | Purpose |
|---|---|
| `sensor.radar_hail_risk_level` | `none`, `watch`, `warning`, `urgent`, or `unavailable` |
| `sensor.radar_hail_risk_summary` | Short human-readable status |
| `binary_sensor.radar_hail_risk_active` | Current storm or warning is active |
| `binary_sensor.radar_hail_risk_data_stale` | Source data is no longer current |

These four entities are enabled by default. Detailed radar, lightning, frame-age, and storm-core entities are disabled by default and can be enabled for diagnostics.

For automations, use the `evidence_kind` attribute on the level sensor instead of parsing the summary text.

## Lovelace dashboard snippets

Dashboard files are **manual examples only**; the integration never writes dashboards automatically.

Recommended ready-made example:

```text
examples/lovelace/native-card.yaml
```

Additional examples are available in `examples/lovelace/`.

### Adaptive custom card

Add this JavaScript resource in **Settings → Dashboards → Resources**:

```text
URL: /radar_hail_risk/radar-hail-risk-card.js
Type: JavaScript module
```

Then add a manual card:

```yaml
type: custom:radar-hail-risk-card
title: Bouřky v okolí
```

The clear and unavailable states stay minimal. Storm details appear only during current activity, and hail wording appears only with radar-supported evidence.

## Notification blueprint

The optional blueprint is located at:

```text
blueprints/automation/radar_hail_risk/hail_risk_notification.yaml
```

Import it into Home Assistant, create an automation, and select:

- the level sensor;
- the optional summary sensor;
- a notify service;
- minimum level (`watch`, `warning`, or `urgent`);
- Czech or English titles;
- notification cooldown.

The blueprint uses `evidence_kind`, so its Czech wording distinguishes:

- **Sledování bouřky**;
- **Blízká bouřka / blesky poblíž**;
- **Možné kroupy poblíž**;
- **Vysoké riziko krup**.

It is opt-in and does not create automations by itself.

## Limitations

- Radar Hail Risk is **not an official warning source**.
- Radar and lightning feeds can be delayed, unavailable, or inaccurate.
- Radar reflectivity can overestimate or miss local hail conditions.
- Do not use it as the only input for safety-critical automation.
- Keep official weather warnings and local safety guidance as the authority.

## Credits

- Radar data: [RainViewer](https://www.rainviewer.com/api.html)
- Optional lightning context: Home Assistant sensors from Blitzortung-compatible integrations
- Platform: [Home Assistant](https://www.home-assistant.io/) and [HACS](https://www.hacs.xyz/)

Development and release checks are documented in [`docs/release-checklist.md`](docs/release-checklist.md).
