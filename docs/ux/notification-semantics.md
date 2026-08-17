# Storm Detector Notification Semantics

Status: frozen notification and copy contract for the Storm Detector rename.
Scope: optional Home Assistant notification blueprint, evidence-based text, and safe alert semantics.

## Blueprint identity

| Surface | Frozen value |
|---|---|
| Blueprint path | `blueprints/automation/storm_detector/storm_notification.yaml` |
| Blueprint name | `Storm Detector notification` |
| Notification tag | `storm_detector` |
| Source sensor | `sensor.storm_detector_level` |
| Optional summary sensor | `sensor.storm_detector_summary` |

The blueprint is opt-in. Storm Detector must not create automations, helpers, dashboards, or notification targets automatically.

## Required blueprint inputs

- `storm_level_sensor`: level sensor exposing `none`, `watch`, `warning`, `urgent`, or `unavailable`.
- `storm_summary_sensor`: optional summary sensor for body text fallback.
- `notify_service`: Home Assistant notify service.
- `minimum_level`: `watch`, `warning`, or `urgent`.
- `title_language`: `en` or `cs`.
- `cooldown_minutes`: minimum time between repeated notifications from the same automation.

The blueprint must not require max-dBZ, core-distance, lightning-distance, or diagnostic sensors as user inputs.

## Trigger and ranking semantics

Notifications are evaluated on `storm_level_sensor` state changes.

Ranking:

| Level | Rank |
|---|---:|
| `none` | 0 |
| `unavailable` | 0 |
| `watch` | 1 |
| `warning` | 2 |
| `urgent` | 3 |

A notification can be sent only when `rank(current_level) >= rank(minimum_level)` and cooldown allows it.

`evidence_kind` from the level sensor attribute is the primary branch key. Do not parse localized summary text to decide whether to mention hail.

## Evidence-based notification contract

| Evidence kind | Allowed notification meaning |
|---|---|
| `none` | No attention notification by default. |
| `radar_storm` | Storm watch/nearby storm, no hail claim. |
| `lightning_only` | Thunderstorm/lightning nearby; explicitly says hail is not radar-confirmed. |
| `radar_hail` | Possible radar-supported hail. |
| `radar_hail_with_lightning` | Possible radar-supported hail plus lightning context. |
| `unavailable` | Data unavailable/degraded; no storm or hail claim. |

Lightning-only can produce attention up to `warning`, never `urgent`. `urgent` copy must require current urgent radar-supported possible-hail evidence.

## Canonical copy table

This table freezes the required Czech and English meanings for shared card/notification UX. Notifications may shorten body text, but must not change the semantics.

| UX state | English title | English message | Czech title | Czech message |
|---|---|---|---|---|
| Clear | Clear nearby | No strong radar core detected nearby. | Klid v okolí | Silné radarové jádro v okolí nezjištěno. |
| Storm | Storm watch | Storm activity detected nearby. | Sledování bouřky | V okolí byla detekována bouřková aktivita. |
| Lightning-only | Thunderstorm / lightning nearby | Thunderstorm / lightning nearby; hail not radar-confirmed. | Blízká bouřka / blesky poblíž | Blízká bouřka / blesky poblíž; kroupy nejsou radarově potvrzené. |
| Possible hail | Possible hail nearby | Radar indicates possible hail nearby. | Možné kroupy poblíž | Radar ukazuje možné kroupy poblíž. |
| Stale | Data stale | Detection data is stale; previous event details are hidden. | Data jsou zastaralá | Detekční data jsou zastaralá; předchozí hodnoty jsou skryté. |
| Degraded | Detection degraded | Some data sources are unavailable; use only current trusted evidence. | Detekce je omezená | Některé zdroje dat nejsou dostupné; používejte jen aktuální důvěryhodné údaje. |
| Unavailable | Detection unavailable | Current storm detection data is unavailable. | Detekce není dostupná | Aktuální data pro detekci bouřek nejsou dostupná. |

Urgent radar-supported possible hail may use:

| Language | Title | Message |
|---|---|---|
| English | High possible hail risk nearby | Radar indicates high possible hail risk nearby. |
| Czech | Vysoká možnost krup | Radar ukazuje vysokou možnost krup poblíž. |

## Recommended notification branch behavior

- `radar_storm` + `watch`: title `Storm watch` / `Sledování bouřky`.
- `lightning_only`: title `Thunderstorm / lightning nearby` / `Blízká bouřka / blesky poblíž`; message must include hail-not-radar-confirmed wording.
- `radar_hail` + `warning`: title `Possible hail nearby` / `Možné kroupy poblíž`.
- `radar_hail_with_lightning` + `warning`: possible-hail title; message adds lightning also nearby.
- `radar_hail` + `urgent`: urgent possible-hail title.
- `radar_hail_with_lightning` + `urgent`: urgent possible-hail title; message adds lightning also nearby.
- Unknown or missing `evidence_kind`: use degraded/unavailable weather-risk copy without hail wording.

## Safety and stale/degraded behavior

- Clear states normally do not notify; if a user builds a clear notification, it must not imply all weather is safe.
- Stale/unavailable states hide old storm, hail, distance, dBZ, and ETA details.
- Degraded source states can notify only about degraded detection unless there is separate current trusted evidence.
- Notification text must never say confirmed hail, observed hail, official warning, calibrated probability, or guaranteed arrival.
- The notification is advisory and must leave official weather warnings and local safety procedures as the authority.

## Rename guardrails

During the rename refactor, only identifiers and user-facing product language may change. Do not adjust level ranking, cooldown semantics, threshold semantics, stale gates, or evidence escalation rules.
