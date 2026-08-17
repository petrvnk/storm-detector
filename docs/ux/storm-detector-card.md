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
- Truthful evidence wording: lightning-only never claims hail; possible-hail wording requires `radar_hail` or `radar_hail_with_lightning`.
- Fail closed: stale/degraded/unavailable data hides old event details instead of presenting them as current.
- No safety overclaim: card copy must remind users that radar activity is not confirmed hail and official warnings remain authoritative.

## Display modes

| Mode | Inputs | Layout | Required behavior |
|---|---|---|---|
| Clear | `level: none`, `evidence_kind: none` | Compact | Show calm/clear copy; no radar, dBZ, ETA, confidence, or diagnostics. |
| Storm | `evidence_kind: radar_storm` | Expanded when current radar facts exist | Show nearby storm core, distance, dBZ/area if current, movement/ETA if reliable. No hail claim. |
| Lightning-only | `evidence_kind: lightning_only` | Expanded lightning state | Show lightning context and explicit no-radar-hail confirmation. Hide radar-hail safety note unless radar facts are also shown. |
| Possible hail | `evidence_kind: radar_hail` or `radar_hail_with_lightning` | Expanded attention state | Show possible radar-supported hail, selected core distance, dBZ, area, motion/ETA, and lightning context when current. |
| Stale | stale flag or stale source gating | Compact unavailable-style | Hide previous storm/hail details; show stale/current-data warning. |
| Degraded | source degraded but still safe to render partial state | Compact or expanded with caution | Show the current valid state plus degraded-source caution; never invent missing source values. |
| Unavailable | `level: unavailable` or invalid state | Compact unavailable | Show detection unavailable; no previous event details. |

## Canonical card copy

| UX state | English title | English body | Czech title | Czech body |
|---|---|---|---|---|
| Clear | Clear nearby | No strong radar core detected nearby. | Klid v okolí | Silné radarové jádro v okolí nezjištěno. |
| Storm | Storm nearby | Radar detected a storm core near the monitored location. | Bouřka v okolí | Radar zachytil bouřkové jádro v okolí. |
| Lightning-only | Lightning nearby | Current lightning activity is nearby; hail is not radar-confirmed. | Blesky poblíž | V okolí byla zaznamenána aktuální blesková aktivita; kroupy nejsou radarově potvrzené. |
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

Whenever RainViewer live radar imagery is visible, the card must show a visible link:

`Weather data by RainViewer` → `https://www.rainviewer.com/`

The attribution must not be hidden behind hover, collapsed diagnostics, or an icon-only affordance. The card may use a schematic fallback without RainViewer tiles when live imagery is unavailable.

## Accessibility

- The live radar module uses `role="img"` with a localized aria label that describes RainViewer radar and storm cores near home.
- Decorative tile images use `alt=""` and `aria-hidden="true"`.
- Marker layers that duplicate textual facts are `aria-hidden="true"`.
- Interactive links, including RainViewer attribution, must expose visible focus states.
- The card must respect `prefers-reduced-motion: reduce` by disabling pulse animations.
- Color must not be the only channel: use text, icons, labels, and facts for meaning.
- No required information may be available only on hover.
- Mobile layouts must avoid horizontal overflow and reduce two-column facts to one column on narrow screens.

## Safety copy

Expanded radar-supported storm/hail modes must include or make available this safety meaning:

- English: `Radar activity is not confirmed hail; follow official warnings.`
- Czech: `Radarová aktivita není potvrzené krupobití; sledujte oficiální výstrahy.`

The copy may be shortened in tight spaces only if it preserves both ideas: radar is not confirmed hail, and official warnings are authoritative.
