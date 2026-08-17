# Storm Detector Card UX Contract

Status: frozen UX contract for `custom:storm-detector-card`.
Scope: card behavior, copy, accessibility, and RainViewer attribution. This document does not implement the card rename.

## Card identity

| Surface | Frozen value |
|---|---|
| Card tag | `custom:storm-detector-card` |
| Resource URL | `/storm_detector/storm-detector-card.js` |
| Source path | `custom_components/storm_detector/frontend/storm-detector-card.js` |
| Default title, English | `Storms nearby` |
| Default title, Czech | `Bouřky v okolí` |
| Default overlay mode | `auto` |

The card uses one card-wide locale from `hass.language`: Czech (`cs`) when `hass.language` is `cs`, English otherwise. This applies to the default title, status/body copy, fact labels, errors, fallbacks, tile notices, RainViewer attribution context and visible link label, safety copy, and ARIA labels. A configured explicit `title` overrides only the displayed title; all other card-owned copy still follows the `hass.language` locale.

Default entities:

- `sensor.storm_detector_level`
- `sensor.storm_detector_summary`
- `sensor.storm_detector_max_dbz`
- `sensor.storm_detector_core_distance`
- `sensor.storm_detector_lightning_distance`
- `binary_sensor.storm_detector_active`
- `binary_sensor.storm_detector_data_stale`

## UX principles

- Status first: the first visible message must answer whether the user should pay attention now.
- Progressive disclosure: clear/unavailable states remain compact; radar facts appear only when current evidence makes them useful.
- Practical, not diagnostic: show distance, dBZ, area, motion, ETA, lightning distance, and source freshness when relevant; hide confidence internals and raw diagnostic markers by default.
- Truthful evidence wording: `radar_storm` and `lightning_only` use generic storm/lightning wording.
- Possible-hail wording requires `radar_hail` or `radar_hail_with_lightning`.
- Fail closed: stale/degraded/unavailable data hides old event details instead of presenting them as current.
- No safety overclaim: generic storm/lightning copy points to official warnings using generic weather/storm language; hail-specific safety copy appears only for current radar-supported possible-hail evidence.

## Display modes

| Mode | Inputs | Layout | Required behavior |
|---|---|---|---|
| Clear | `level: none`, `evidence_kind: none` | Compact | Show calm/clear copy; no radar, dBZ, ETA, confidence, or diagnostics. |
| Storm | `evidence_kind: radar_storm` | Expanded when current radar facts exist | Show nearby storm core, distance, dBZ/area if current, movement/ETA if reliable. |
| Lightning-only | `evidence_kind: lightning_only` | Expanded lightning state | Show current lightning context with storm/lightning wording only; hide radar-specific facts unless current radar evidence is also shown. |
| Possible hail | `evidence_kind: radar_hail` or `radar_hail_with_lightning` | Expanded attention state | Show possible radar-supported hail, selected core distance, dBZ, area, motion/ETA, and lightning context when current. |
| Stale | no trusted current evidence remains after stale/unusable source gating | Compact unavailable-style | Hide previous attention details; show stale/current-data warning. |
| Degraded | one source is stale/degraded while another source still provides current trusted evidence | Compact or expanded with caution | Show the current valid state plus degraded-source caution; suppress only facts from the stale/degraded source and never invent missing source values. |
| Unavailable | `level: unavailable` or invalid state | Compact unavailable | Show detection unavailable; no previous event details. |

Stale/degraded precedence must not be keyed only from `binary_sensor.storm_detector_data_stale` or a generic stale flag. `unavailable` or no trusted current evidence uses compact stale/unavailable rendering. Partial-source staleness with current trusted evidence renders the current evidence in Degraded mode with stale-source caution.

Frontend regression tests must mirror both partial-source precedence cases: stale/degraded radar with current lightning keeps `lightning_only` attention visible and hides radar facts/overlay, while stale/degraded lightning with current radar evidence keeps the radar-driven branch visible and hides lightning facts. Both tests must assert that old attention details from the stale source are not rendered.

## Canonical card copy

| UX state | English title | English body | Czech title | Czech body |
|---|---|---|---|---|
| Clear | Clear nearby | No strong radar core detected nearby. | Klid v okolí | Silné radarové jádro v okolí nezjištěno. |
| Storm | Storm nearby | Radar detected a storm core near the monitored location. | Bouřka v okolí | Radar zachytil bouřkové jádro v okolí. |
| Lightning-only | Lightning nearby | Current lightning activity is near the monitored location. | Blesky poblíž | V okolí byla zaznamenána aktuální blesková aktivita. |
| Possible hail | Possible hail nearby | Radar indicates a strong core that may support hail. | Možné kroupy poblíž | Radar ukazuje silné jádro s možností krup. |
| Stale | Data is stale | Detection data is too old; previous event details are hidden. | Data jsou zastaralá | Detekční data jsou příliš stará; předchozí hodnoty jsou skryté. |
| Degraded | Detection degraded | Some data sources are unavailable; only current trusted evidence is shown. | Detekce je omezená | Některé zdroje dat nejsou dostupné; zobrazují se jen aktuální důvěryhodné údaje. |
| Unavailable | Detection unavailable | Current storm detection data is unavailable. | Detekce není dostupná | Aktuální data pro detekci bouřek nejsou dostupná. |

Urgent possible-hail may use a stronger title (`High possible hail risk nearby` / `Vysoká možnost krup`) only when `level: urgent` and radar-supported possible-hail evidence is current.

## Facts and ordering

When current attention evidence exists, show facts in this order when available and trustworthy:

1. Selected/nearest storm core distance.
2. Selected core intensity in dBZ.
3. Selected core area.
4. Rendered/total core count when the live overlay caps visible cores.
5. Motion: approaching or receding.
6. ETA when the storm is approaching and ETA is reliable.
7. Lightning distance or lightning-also-detected note.

Do not show stale facts, unknown/unavailable values, raw diagnostics, raw confidence score, or hover-only details in the default card.

## Radar overlay behavior

`radar_overlay` configuration:

- `auto`: show live RainViewer radar only for current `radar_storm`, `radar_hail`, or `radar_hail_with_lightning` evidence.
- `off`: always use the schematic radar view when radar facts are shown.
- `always`: show a valid current radar layer even in clear state; stale/unavailable overlays stay hidden.

Live overlay contract:

- Use backend-provided `radar_overlay.schema_version: 1` only when status is `ok` and synchronized with `frame_time` and selected-core attributes.
- Render a square, centered, north-up viewport around the monitored location.
- Keep home marker centered and storm markers geographically aligned to the same Web Mercator viewport as RainViewer tiles.
- Highlight exactly one selected risk-driving core when `selected_core_id` is present.
- Show rendered/total core counts if the backend caps visible cores.
- On tile load failure, fall back to the schematic radar view for that frame and show a short non-alarming notice.

## RainViewer attribution

Whenever RainViewer live radar imagery is visible, the card must show one visible attribution link selected by the card-wide locale:

| Card locale | Visible link label | URL |
|---|---|---|
| English fallback (`en`) | `Weather data by RainViewer` | `https://www.rainviewer.com/` |
| Czech (`cs`) | `Data o počasí od RainViewer` | `https://www.rainviewer.com/` |

The attribution must not be hidden behind hover, collapsed diagnostics, or an icon-only affordance. The card may use a schematic fallback without RainViewer tiles when live imagery is unavailable.

## Accessibility

- The live radar module uses `role="img"` with an aria label in the card-wide locale that describes RainViewer radar and storm cores near home.
- Decorative tile images use `alt=""` and `aria-hidden="true"`.
- Marker layers that duplicate textual facts are `aria-hidden="true"`.
- Interactive links, including RainViewer attribution, must expose visible focus states.
- The card must respect `prefers-reduced-motion: reduce` by disabling pulse animations.
- Color must not be the only channel: use text, icons, labels, and facts for meaning.
- No required information may be available only on hover.
- Mobile layouts must avoid horizontal overflow and reduce two-column facts to one column on narrow screens.

## Safety copy

Generic storm or lightning-only modes must include or make available this safety meaning:

- English: `Follow official weather warnings.`
- Czech: `Sledujte oficiální výstrahy.`

This generic safety copy must use only storm/weather language.

Expanded radar-supported possible-hail modes must include or make available this hail-specific safety meaning only when current `radar_hail` or `radar_hail_with_lightning` evidence is rendered:

- English: `Radar activity is not confirmed hail; follow official warnings.`
- Czech: `Radarová aktivita není potvrzené krupobití; sledujte oficiální výstrahy.`

The copy may be shortened in tight spaces only if generic storm/lightning states still preserve official-warning authority using storm/weather language, and possible-hail states still preserve both ideas: radar is not confirmed hail, and official warnings are authoritative.
