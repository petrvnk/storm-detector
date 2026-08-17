# Storm Detector Product Contract

Status: frozen for the `storm_detector` rename refactor.
Scope: product and runtime semantics only; this document does not change thresholds, algorithms, feeds, Home Assistant state, or release behavior.

## Product promise

Storm Detector monitors storm activity near a configured Home Assistant location and reports a truthful current state: clear, storm nearby, lightning-only storm context, possible radar-supported hail, stale/degraded data, or unavailable data.

The product is storm-first. Possible hail is a capability within storm detection, not the primary product identity and not a claim that hail has been observed on the ground.

## Minimum user journey

1. Install Storm Detector.
2. Choose a location source, or leave it empty to use the Home Assistant core location.
3. Optionally connect lightning distance/counter sensors from a Blitzortung-compatible source.
4. Receive one truthful storm state and a short human-readable summary.
5. Optionally enable the Storm Detector notification blueprint.

The minimum journey must remain compact. Advanced thresholds, frame counts, stale timeouts, and diagnostics belong in options or diagnostic entities, not in the primary setup path.

## Source contract

Storm Detector uses:

- RainViewer radar as the radar evidence source.
- Optional Home Assistant lightning entities as context.
- Home Assistant location or a configured `zone`, `person`, or `device_tracker` location entity as the monitored center.

Storm Detector does not use Open-Meteo or any new forecast/source feed in the rename refactor.

## Runtime state contract

The level sensor exposes exactly these risk levels:

| Level | Meaning | User promise |
|---|---|---|
| `none` | No current qualifying nearby radar/lightning signal after freshness gates | Show a calm/clear state, but do not imply all weather is safe. |
| `watch` | Current radar storm evidence or lower attention state | Show nearby storm monitoring. |
| `warning` | Current nearby storm/lightning evidence that deserves attention | Show storm or possible-hail wording based on `evidence_kind`. |
| `urgent` | Current urgent radar-core evidence only | Show the strongest possible-hail attention state; lightning alone must never produce urgent. |
| `unavailable` | Current detection cannot be trusted | Hide previous event details and tell the user data is unavailable. |

## Evidence semantics

The level tells how much attention is needed. `evidence_kind` tells why.

| Evidence kind | Meaning | Hail wording allowed? |
|---|---|---|
| `none` | No current qualifying evidence | No. |
| `radar_storm` | Current radar storm core evidence, below possible-hail claim threshold | No. Use storm wording. |
| `lightning_only` | Current lightning nearby without current radar-supported hail evidence | No. Say thunderstorm/lightning; explicitly avoid hail claims. |
| `radar_hail` | Current radar evidence supports possible hail | Yes, only as possible radar-supported hail. |
| `radar_hail_with_lightning` | Current radar-supported possible hail plus current nearby lightning | Yes, only as possible radar-supported hail with lightning context. |
| `unavailable` | Evidence cannot be trusted | No. |

`radar_hail` and `radar_hail_with_lightning` are intentionally preserved names because they describe real radar-supported possible-hail evidence. They must not be generalized away during the rename unless the underlying evidence model changes in a separately approved feature phase.

## Freshness, stale, degraded, and unavailable semantics

- Stale radar data is gated out of radar classification.
- Stale lightning data is gated out of lightning classification.
- Stale source data may set the data-stale binary sensor even if another current source still produces a valid attention state.
- A stale or unusable radar source with no current contributing lightning must fail closed to `unavailable`, not false-clear `none`.
- A current nearby lightning signal while radar is stale/degraded may produce `warning` with `evidence_kind: lightning_only`, never hail and never urgent.
- `source_status` is diagnostic context. It can explain degraded radar/lightning/location inputs, but it must not be exposed as scary raw diagnostic text in the primary summary.

## Safety limitations

Storm Detector is not an official warning source. It does not detect hail on the ground, does not provide a calibrated hail probability, and must not be the only input for safety-critical automation.

Radar and lightning feeds can be delayed, unavailable, blocked, inaccurate, or spatially imprecise. Users must follow official weather warnings and local safety procedures as the authority.

## Rename refactor guardrails

During the Storm Detector rename refactor:

- Do not change detection thresholds.
- Do not tune algorithms.
- Do not add new weather feeds.
- Do not change hysteresis, stale gates, confidence scoring, or alert escalation semantics except where a test must be renamed to the new public identifiers without behavior change.
- Do not create compatibility aliases for old public identifiers.
- Do not claim observed hail, guaranteed hail, or official warning equivalence.

All runtime behavior changes must be proposed as separate, explicitly approved feature work after the public contract is accepted.

## Frozen decisions

- Product name: Storm Detector.
- Public Home Assistant domain: `storm_detector`.
- Product framing: storm-first monitoring with possible radar-supported hail as one evidence type.
- Minimum journey: install, choose location, optionally choose lightning sensors, receive state, optionally enable notifications.
- User-facing copy must distinguish storm, lightning-only, possible hail, stale/degraded, and unavailable states.
- RainViewer attribution remains visible wherever live radar imagery is shown.

## Open questions

- Whether Czech integration translations should be added in Phase 4 alongside English translations, or whether Czech remains limited to card and notification copy until a later localization pass.
- Whether the default card title should ship as English (`Storms nearby`) or preserve the current Czech-friendly default (`Bouřky v okolí`) for Petr's live deployment. The public tag/resource/entity identifiers are frozen either way.
