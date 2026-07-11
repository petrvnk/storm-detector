# Observation Mode and Ground-Truth Pilot Plan

> **Status:** Planning and measurement design only. Do not implement, enable collection, deploy, notify, or change production thresholds without Petr's explicit approval.

**Goal:** Evaluate the local hail-risk heuristic against labeled real-world events while it runs silently, measuring false positives, false negatives, alert lead time, stale-data safety, and candidate threshold calibration.

**Architecture:** After approval, an opt-in observation recorder would sample the coordinator's already-computed inputs and outputs into a local, append-only, versioned dataset. Labels would be entered separately from observations and joined only during offline evaluation, so the labeling process can be blinded to the predicted level. Candidate thresholds would be replayed offline; observation mode would never send alerts or alter the live risk entities.

**Current model contract used by this plan:** Stable levels are `none`, `watch`, `warning`, `urgent`, and `unavailable`; escalation/clearing normally requires two consecutive candidates, while a new nearby lightning strike can force an immediate level. Radar evidence older than `stale_clear_seconds` is gated out. The current confidence score is a heuristic quality indicator, not a calibrated hail probability.

---

## 1. Scope and non-goals

### In scope

- Silent accounting of every scheduled coordinator cycle and observation of every successfully completed update.
- Versioned snapshots of prediction outputs, contributing evidence, source health, and effective thresholds.
- A separate, reviewable ground-truth labeling protocol.
- Event-level and update-level metrics with explicit handling of unknown labels and coverage gaps.
- Offline replay of candidate thresholds against a development split, followed by one untouched holdout evaluation.
- Synthetic stale-source drills in a test Home Assistant instance in addition to naturally occurring stale periods.

### Out of scope until separate approval

- User notifications, automations, dashboard warnings, or replacement of an existing alerting setup.
- Uploading observations, exact coordinates, entity state histories, or labels to a cloud service.
- Automatic scraping or publication of personal reports.
- Changing runtime thresholds based on pilot data.
- Describing `confidence_score` as probability or claiming meteorological validation.
- Release, HACS publication, deployment, or collection from third-party installations.

## 2. Observation mode contract

Observation mode must be explicitly opt-in and default off. Enabling it must not change coordinator scheduling, classification, hysteresis, entity state, or notification behavior. Recorder failures must be isolated from coordinator updates and surfaced only as diagnostics.

Each successful coordinator cycle produces at most one observation row. Rows are append-only and use UTC timestamps. A unique key of `(site_id, integration_instance_id, update_count, observed_at)` prevents accidental duplicate ingestion. The recorder flushes atomically so interrupted writes cannot leave a partially valid row.

### Independent scheduled-cycle and write-attempt ledger

Availability cannot be inferred from observation rows because failed coordinator cycles and failed observation writes produce no such row. A later approved implementation must therefore maintain a minimal append-only cycle ledger through an independent write path. Its deterministic `cycle_id` is derived from the pseudonymous integration instance and scheduled UTC slot, not from a successful coordinator result. Before each due slot, the scheduler writes a `scheduled` marker; after the attempt it appends a terminal outcome. The observation writer never owns or updates this ledger.

The ledger records `cycle_id`, `site_id`, `integration_instance_id`, `scheduled_at`, actual start/end times, expected interval, host/service uptime state, coordinator outcome (`success`, `failed`, `timed_out`, `cancelled`, `not_started`), recorder attempt (`committed`, `failed`, `not_attempted`), nullable `observation_id`, normalized failure/downtime code, and ledger schema version. It contains no weather values, predictions, coordinates, entity IDs, or free text. A coordinator success counts as a valid observation cycle only when the referenced observation row committed and passed schema validation.

At export, a deterministic reconciler materializes every expected slot from the opt-in enable/disable intervals, frozen schedule, and host/service uptime intervals, then left-joins terminal ledger entries and observation rows. It classifies absent slots as `missed` when the service was available and `downtime` when it was not, detects duplicate/unterminated attempts, and separately counts scheduled, started, coordinator-successful, coordinator-failed, missed, downtime, recorder-committed, recorder-failed, and recorder-not-attempted cycles. This canonical reconciliation is the denominator for availability and remains able to count coordinator or recorder failures that could not create an observation row. A ledger-write failure must raise a local diagnostic; any interval whose expected slots or uptime cannot be reconstructed is `coverage_unknown` and makes availability-based acceptance inconclusive rather than silently reducing the denominator.

### Required observation fields

| Group | Fields |
|---|---|
| Schema/provenance | `schema_version`, `model_version`, `integration_version`, `observation_id`, `site_id`, `integration_instance_id` |
| Timing | `observed_at`, `frame_time`, `frame_age_seconds`, `update_count`, `analysis_interval_seconds` |
| Prediction | stable `level`, pre-hysteresis `candidate_level`, `has_current_signal`, `active`, `summary_code` (not free text), `confidence_score`, `confidence_level` |
| Radar evidence | `max_dbz`, configured watch/warning/urgent core distances, fixed 50/55/60 dBZ distances, selected-core threshold/distance/area/pixel count/max dBZ, `core_count`, approach flag, radial ETA, motion speed/bearing, dBZ and distance trends, frames analyzed |
| Lightning evidence | configured/not-configured mode, distance, new-strike boolean, counter delta, trigger boolean, lightning-to-core distance; omit raw entity IDs and raw counter totals |
| Health | `is_stale`, source statuses, normalized degradation/diagnostic codes, update duration, linked `cycle_id` |
| Effective configuration | analysis radius, dBZ thresholds, core-distance thresholds, lightning-distance thresholds, trigger radius, minimum core pixels, frame count, zoom, stale timeout |

For offline calibration, `candidate_level` must be recorded before hysteresis and `stable level` after hysteresis. If exposing the candidate requires a code change, that change belongs to a later approved implementation task and must have tests proving it cannot affect the stable output.

### Data intentionally excluded

- Exact home, person, device-tracker, radar-core, or lightning latitude/longitude.
- Home Assistant entity IDs, friendly names, device identifiers, credentials, IP addresses, or arbitrary state attributes.
- Free-text summaries, logs, diagnostics downloads, screenshots, or comments in observation rows.
- Raw radar tiles. A short-lived encrypted diagnostic capture may be proposed later for selected disputed cases, but is not part of this pilot.

## 3. Ground-truth dataset

Ground truth is event-centered and stored separately from model observations. A label describes conditions within the configured evaluation radius around the site, not an entire town or radar footprint.

### Label schema

| Field | Meaning |
|---|---|
| `label_id`, `schema_version`, `site_id` | Stable, pseudonymous identity and schema |
| `window_start`, `window_end` | UTC interval reviewed |
| `sampling_frame_version`, `window_provenance`, `selection_probability` | Frozen-frame traceability; provenance is `opportunity`, `background_control`, or `alert_triggered` |
| `coverage` | `complete`, `partial`, or `none` |
| `coverage_grid_version`, `coverage_matrix_ref` | Versioned cell/bin completeness artifact, stored separately without coordinates |
| `hail_outcome` | `confirmed_hail`, `verified_no_hail`, `unknown` |
| `onset_time`, `end_time` | Best estimate with explicit uncertainty; nullable |
| `onset_uncertainty_minutes` | Accuracy bound for lead-time reporting |
| `max_hail_size_class` | `unknown`, `<5mm`, `5-19mm`, `20-39mm`, `>=40mm` |
| `distance_band_from_site` | `0-2km`, `2-5km`, `5-10km`, `10-25km`, `outside`, or `unknown` |
| `evidence_types` | Controlled values such as `direct_observer`, `photo_video`, `weather_station`, `official_report`, `trusted_local_report` |
| `source_count` | Number of independent evidence sources |
| `labeler_id`, `reviewer_id`, `labeled_at` | Pseudonymous audit fields |
| `adjudication_status`, `notes_code` | Review state and controlled ambiguity reason; no free-form PII |

### Spatial and temporal coverage contract

Before Gate P3, freeze a 2 km square coverage grid anchored to a public, rounded origin for each site. A label window is divided into fixed 10-minute bins. `coverage=complete` for the proposed 10 km evaluation radius requires every grid cell intersecting that radius to be covered in every bin by at least one approved negative-capable source whose declared footprint contains the cell. Overlap does not repair a temporal gap. If any cell/bin is uncovered, source uptime is unknown, or evidence conflicts, coverage is `partial` or `none` and the outcome cannot be `verified_no_hail` for the 10 km headline analysis. Gate P0 may approve a smaller evidence-supported radius, but the radius and grid must be frozen and reported; point evidence must never be generalized to 10 km.

Evidence types have these proposed completeness rules, to be confirmed with source-specific capabilities at Gate P0:

| Evidence type | Positive use | Negative-capable footprint and temporal rule |
|---|---|---|
| Direct observer | Timestamped observation at a bounded location | Only the pre-registered visibility footprint, capped at 1 km; explicit precipitation checks at least once per 10-minute bin and an end-of-window confirmation |
| Hail-discriminating station/instrument | Instrument event within its documented footprint | Only the manufacturer/validation-documented footprint; uninterrupted uptime and a valid hail/no-hail reading in every 10-minute bin |
| Continuous calibrated camera/video | Visible timestamped hail in field of view | Only its pre-registered field-of-view footprint when visibility/precipitation quality checks pass in every bin; ordinary photos or intermittent video are positive-only |
| Official report or timestamped/location-bounded artifact | Positive within its stated spatial/time bound | Positive-only unless the issuing source explicitly certifies exhaustive surveillance for the full cell/bin; absence from an archive is never negative evidence |
| Trusted local report | Positive when corroborated as required below | Negative-capable only for a pre-registered footprint, capped at 1 km, with explicit no-hail check-ins in every bin; silence is not evidence |

`confirmed_hail` means hail within the frozen evaluation radius and window, supported by either direct observation, one timestamped/location-bounded artifact, one official report, or two independent trusted local reports. `verified_no_hail` requires the complete cell/bin matrix above and explicit negative-capable evidence; absence of reports is insufficient. `unknown` applies when coverage is incomplete, reports conflict, location/time cannot be bounded, or precipitation type cannot be distinguished.

A positive report outside the evaluation radius is not local ground truth; it may be retained as `outside` context. Every positive and every sampled negative used in headline metrics requires second-person review. Disagreement is resolved without looking at model predictions; unresolved cases become `unknown`.

### Frozen model-independent sampling frame and blinding

Before collection, Gate P0 must freeze a versioned sampling-frame manifest containing the source product, product/version identifier, retrieval timing, inclusion algorithm, grid/radius, slot duration, strata, pseudorandom seed, and selection probability. The proposed opportunity source is the archived Czech Hydrometeorological Institute (CHMI) radar-composite reflectivity product, retrieved through a separately frozen source path. The frame generator must have no access to this integration's observations, inputs, or predictions. P0 cannot pass until source access, archive completeness, licensing, and the exact product identifier are verified; the source cannot be silently substituted during the pilot.

The proposed frozen procedure is:

1. Generate a convective-opportunity window when the external composite contains at least 35 dBZ in any source pixel within 25 km of the site on two scans no more than 15 minutes apart. Start the window 60 minutes before the first qualifying scan, end it 60 minutes after the last, and merge windows separated by at most 60 minutes. Materialize the frame once daily after source completeness checks, without reading model observations or predictions.
2. Include every generated opportunity window (`selection_probability=1`). Partition all remaining recorder-enabled, externally source-complete time into fixed two-hour UTC slots. Stratify by calendar month and UTC six-hour block, then select each slot with probability 0.10 using the frozen seed and deterministic hash of `(site_id, slot_start, frame_version)`. Persist eligible count, selected count, and each slot's probability.
3. Schedule labeling for all selected opportunity and control windows, including windows that ultimately have partial/no coverage. Hide predicted level, confidence, thresholds, and alert timing from labelers and reviewers until labels are locked.
4. Group adjacent frame windows from the same meteorological episode under one `storm_id`; all windows from a storm stay in one development or holdout phase.
5. Alert-triggered windows may be collected separately to audit individual warning/urgent episodes and stale safety, but mark their provenance `alert_triggered`. They are excluded from headline recall and specificity denominators and cannot repair missing independently scheduled labels. Any externally discovered positive outside the frozen frame is reported as a case study, not added retrospectively to headline recall.

This frame makes the opportunity/control inclusion mechanism reproducible, records its probability, avoids treating “no report” as “no hail,” and prevents model alerts from selecting the headline recall/specificity sample.

## 4. Event matching and metrics

### Evaluation units

- A **prediction episode** starts when the stable level first reaches the evaluated operating point and ends when it remains below that point for 15 minutes. Gaps caused by missing observations do not close or validate an episode; they mark coverage incomplete.
- A **hail event** is one `confirmed_hail` interval. Adjacent positive windows separated by less than 30 minutes are merged when evidence indicates the same storm.
- Primary operating point: stable `warning` or `urgent` versus confirmed local hail within 10 km.
- Secondary operating points: `watch+`, `urgent` alone, radar-only installations, and radar-plus-lightning installations. These are reported separately and not pooled without stratification.

### Matching rule

A prediction episode matches a hail event when it overlaps `[onset_time - 60 minutes, end_time]`. One prediction episode can match only one event and one event can match only one prediction episode; choose the nearest onset when intervals overlap multiple candidates. The 60-minute horizon must be frozen before the pilot starts. Sensitivity tables may additionally show 30- and 90-minute horizons, clearly marked secondary.

### Headline metrics

- **True positive (TP):** a confirmed hail event with a matched prediction episode.
- **False negative (FN):** a confirmed hail event without a matched prediction episode while observation coverage is complete.
- **False positive (FP):** a prediction episode with complete label coverage and no confirmed hail event through 30 minutes after the episode ends, where the covered window is explicitly `verified_no_hail`.
- **True negative (TN):** a pre-sampled control window with complete coverage, explicitly `verified_no_hail`, and no prediction episode at the operating point.
- **Recall / probability of detection:** `TP / (TP + FN)`.
- **Precision / success ratio:** `TP / (TP + FP)`.
- **False-alarm ratio:** `FP / (TP + FP)`.
- **Window-level specificity:** on independently scheduled, verified-negative windows, count a window as positive if any qualifying prediction episode overlaps it, then compute `negative windows without an alert / all verified-negative windows`. Report opportunity-window specificity as primary and background-control specificity separately; do not pool the strata or include alert-triggered windows. Keep these window-level confusion matrices separate from event/episode TP and FP counts.
- **Alert burden:** prediction episodes and minutes in alert per 30 observed days, reported by level.
- **Lead time:** `hail onset - first qualifying stable alert`. Positive means early, zero means at onset, negative means late. Report median, interquartile range, minimum, and the fraction at least 10/20/30 minutes early. Exclude unknown onset times from lead-time statistics but not detection metrics.
- **Availability:** recorder-committed, schema-valid observation cycles divided by all expected scheduled slots from the reconciled cycle ledger; also report coordinator success, recorder-write success conditional on coordinator success, missed-cycle, downtime, unknown-coverage, and labeled-window coverage rates separately.

Always report raw counts, denominators, exposure, exclusions, and the predeclared 95% interval method. Use exact binomial intervals only for proportions such as recall, specificity, precision, false-alarm ratio, and coverage. Use an exposure-aware exact Poisson count-rate interval for episode counts per valid observed day; if storm clustering produces material overdispersion, add a storm-block bootstrap sensitivity interval without replacing the predeclared primary interval. Use a storm-grouped bootstrap for lead-time summaries, alert-minute burden, paired baseline/candidate differences, and other clustered non-binomial comparative metrics. Never apply a binomial interval to an episode-per-day rate or a lead-time statistic, never treat correlated alert minutes as independent Poisson events, and do not publish a percentage alone when the denominator is below 20.

### Stale-data metrics

For every natural stale period and controlled test drill, record:

- Time from `frame_age_seconds > stale_clear_seconds` to `is_stale=true`.
- Count of cycles where stale radar evidence remains populated or contributes to `candidate_level`/`has_current_signal` after the boundary; target is zero.
- Count and duration of active alerts supported only by stale signals; target is zero.
- Transition of `source_status.radar`, stable level, active state, and diagnostics at the stale boundary.
- Recovery latency from the first fresh frame to a valid current classification.
- Behavior for stale radar + fresh lightning, fresh radar + stale lightning, both stale, metadata failure, analysis timeout, and restart with unknown lightning counter.

Natural outages measure real behavior. Deterministic synthetic drills establish safety coverage even if no outage occurs during the pilot.

## 5. Calibration protocol

Calibration is offline only. Preserve the source observations and labels only within their approved retention period; produce candidate results as derived artifacts. No expired record may be retained or counted merely to reach a denominator, so an extension requires explicit approval before expiry or the affected phase becomes inconclusive.

1. Freeze the baseline configuration, sampling-frame manifest, metric definitions, interval implementations, and decision rules before collection starts.
2. Use a sequential chronological split by `storm_id`. Collect the development phase until it contains at least 30 confirmed local hail events with complete observation coverage across at least 15 storms, then freeze the single candidate, evaluator version, and a UTC holdout boundary. Everything after that boundary is prospective untouched holdout; do not reopen development or tune against holdout. Leave-one-storm-out estimates before the boundary are exploratory only. Continue holdout collection until the predeclared denominators below are met or declare the result inconclusive.
3. Replay only a bounded, predeclared grid around current defaults: dBZ thresholds, core distances, lightning distances, minimum core pixels, and stale timeout. Preserve ordering constraints (`watch < warning < urgent`; warning distances >= urgent distances).
4. Reconstruct candidate episodes with the same hysteresis and deduplication rules as runtime. Never score isolated rows as if hysteresis did not exist.
5. Rank candidates using a predeclared objective: maximize warning+ recall subject to false-alarm ratio no worse than baseline and alert burden no more than 20% above baseline. Safety tie-breaker: higher recall, then longer median lead time, then lower alert burden.
6. Evaluate the single selected candidate once on holdout and compare it with the frozen baseline. Use exact binomial intervals for unpaired proportions, exposure-aware exact Poisson intervals for alert-episode count rates, and 10,000-resample storm-grouped bootstrap intervals with a frozen seed for alert-minute burden, lead-time summaries, and paired candidate-minus-baseline differences.
7. Treat confidence score only as a ranking feature. Reliability/calibration plots may be exploratory, but no probability wording is allowed unless a later dataset is sufficiently large and independently validated.
8. Any proposed runtime threshold change requires a separate approval, tests, release note, rollback plan, and a new observation period.

## 6. Pilot duration and decision gates

### Collection target

Run the development phase for at least 6 weeks and until its calibration threshold above is met. After the candidate is frozen, continue the prospective holdout until all of these are available:

- At least 20 independently framed, completely labeled confirmed local hail events with complete observation coverage, across at least 10 holdout storms. One or two holdout positives are explicitly inconclusive.
- At least 20 matched holdout events with onset uncertainty no greater than 10 minutes, across at least 10 storms, for the lead-time acceptance test.
- At least 90 valid observed holdout days from the scheduled-cycle ledger, at least 95% ledger reconstruction coverage, and complete adjudication of every holdout warning/urgent episode for the false-alert rate test.
- At least 60 independently scheduled, completely covered `verified_no_hail` windows for specificity, including at least 30 opportunity windows and 30 background controls; report the strata separately, and do not count alert-triggered windows.
- All six stale/degraded scenarios above exercised in deterministic tests, plus every natural stale period observed.

Hail is rare; a calendar deadline does not override evidence requirements. If any denominator or coverage target is not met, the result is `inconclusive`, not a pass. Collection may stop for feasibility or privacy reasons without converting an underpowered holdout into a success.

### Approval gates

- **Gate P0 — plan approval:** Petr approves schema, privacy/retention policy, matching horizon, evaluation radius/grid, evidence sources, sampling-frame manifest, minimum denominators, interval methods, decision rules, and collection site(s). No implementation or collection before this gate.
- **Gate P1 — implementation review:** independent cycle ledger, recorder, frame generator, label tooling, evaluator, tests, retention controls, and export format pass independent review. No deployment before this gate.
- **Gate P2 — dry run:** synthetic fixtures prove observation mode is side-effect-free, append-safe, measurable when coordinator/recorder writes fail, redacted, retention-safe, and stale-safe.
- **Gate P3 — pilot start:** Petr explicitly enables local collection with frozen baseline settings.
- **Gate P4 — analysis review:** reviewer checks label audit trail, exclusions, metric code, leakage controls, and baseline/candidate comparison.
- **Gate P5 — operational decision:** Petr chooses continue observation, revise the model, or approve a separately planned threshold/deployment change.

### Pilot success criteria

This pilot validates measurement safety, not that hail can always be predicted. Gate P4 assigns each criterion `pass`, `fail`, or `inconclusive` using only these predeclared rules:

- **Measurement/privacy safety:** pass only with zero privacy-schema violations, zero observation-mode effects on runtime classification/notifications, zero stale-evidence leakage, zero stale-only active alerts, and complete auditability from scheduled ledger slots through locked labels and prediction episodes. Any violation fails; incomplete audit or unknown ledger coverage is inconclusive unless it proves a violation.
- **Warning+ recall:** evaluate only independently framed holdout positives with complete label and observation coverage. Pass only when there are at least 20 across at least 10 storms, point recall is at least 0.80, and the one-sided 95% exact-binomial lower confidence bound is at least 0.80. With fewer events—including one or two positives—the criterion is inconclusive. With the denominator met but either threshold missed, it fails.
- **False warning/urgent rate:** count fully adjudicated false warning/urgent episodes and divide by valid scheduled-cycle exposure. Pass only with at least 90 valid observed days, all holdout warning/urgent episodes adjudicated, at least 95% ledger reconstruction coverage, and the one-sided 95% exact-Poisson upper bound no greater than 1 false episode per 30 valid observed days. Missing adjudications or insufficient exposure are inconclusive; a complete qualifying holdout whose upper bound exceeds the limit fails. Report alert minutes per 30 valid observed days as a secondary burden measure with a storm-grouped bootstrap interval; do not model individual minutes as independent counts.
- **Lead time:** among matched holdout events with onset uncertainty no greater than 10 minutes, pass only with at least 20 events across at least 10 storms, median lead time at least 15 minutes, and the one-sided 95% lower bound from the frozen 10,000-resample storm-grouped bootstrap at least 15 minutes. Insufficient events/storms are inconclusive; a qualifying holdout below either threshold fails.
- **Specificity:** report separate exact-binomial 95% intervals for at least 30 independently scheduled, completely covered verified-negative opportunity windows and at least 30 independently sampled background controls. Alert-triggered negatives are excluded and strata are not pooled. Specificity is descriptive in this pilot and cannot override a failed recall, false-alert-rate, lead-time, privacy, or stale-safety criterion.

A recommendation to proceed requires every safety, recall, false-alert-rate, and lead-time criterion to pass; any required criterion that is inconclusive permits only continued observation or stopping without a performance claim. These numerical thresholds and interval directions are proposed acceptance criteria and must be approved at Gate P0. They are not claims about current performance.

## 7. Privacy, retention, and access policy

- Store data locally on the Home Assistant host or another Petr-controlled system; no default network export.
- Generate random `site_id` and `integration_instance_id`; never derive them from address, coordinates, entity ID, or device serial.
- Keep exact location only in normal Home Assistant configuration. Observation exports contain distance bands/relative distances, never coordinates.
- Encrypt backups and dataset exports at rest. Restrict file permissions to the service account and named reviewers.
- Before sharing a dataset, run an automated schema allowlist and a manual sample review. Sharing remains a separate explicit approval.

The proposed retention clock starts at creation unless a shorter source/consent limit applies:

| Data class | Maximum retention and deletion behavior |
|---|---|
| Raw observations, scheduled-cycle ledger, and source-health records | 12 months; rolling hard deletion by site/instance, including indexes and temporary files; a shorter Gate P0 limit takes precedence |
| Locked labels and adjudication records | 12 months; delete or irreversibly aggregate at expiry, with renewal requiring explicit approval |
| Derived replay outputs, candidate tables, metric extracts, plots, and reports | 12 months or the expiry of their last source record, whichever is earlier; regenerate rather than extend source retention |
| Locally staged exports | Seven days after verified transfer or 14 days after creation, whichever is earlier; recipient, purpose, scope, and due deletion date belong in an export manifest |
| Encrypted backups | Rolling maximum 30 days and never a reason to extend a source category's retention; backup catalog records snapshot expiry and contained site pseudonyms |
| Opaque evidence references | 12 months or evidence-source expiry, whichever is earlier; delete the reference when its label/site is deleted |
| External evidence or approved local evidence copies | Prefer no copy. When retained, use the evidence owner's consent/source policy and at most 90 days unless Gate P0 approves a shorter period; delete controlled copies and request deletion from controlled external stores. Uncontrolled third-party archives must be documented as outside deletion control before consent and are never represented as deleted by this pilot. |
| Access/export/deletion audit material | 24 months, containing event time, action, policy version, non-reversible request ID, and counts only—no site ID, evidence reference, location, prediction, or label content |

Site/instance deletion immediately removes active raw data, labels, derived artifacts/reports, local exports, and opaque references, and revokes the per-site encryption key so remaining encrypted backup blocks are cryptographically inaccessible. The deletion tombstone uses only a keyed non-reversible token and is applied before any backup restore becomes readable; restore tooling must re-delete tombstoned records. Backup snapshots containing the site are purged or expire within 30 days, after which a counts-only audit entry records propagation complete. If a recipient received an approved export, the operator sends the manifest's deletion request and records confirmation or the unresolved external limitation. Expiry/deletion jobs, restore-time tombstone enforcement, and counts-only audit output are mandatory Gate P1/P2 tests.

## 8. Proposed implementation slices after approval

No slice below is authorized by this document.

1. **Schema and redaction tests:** define versioned observation/label/ledger schemas and fail closed on unknown fields, coordinates, entity IDs, or free text.
2. **Independent ledger and side-effect-free recorder:** add scheduled-slot accounting independent of the observation writer, plus opt-in local append-only recording around completed coordinator payloads, including candidate/stable levels and effective config snapshot.
3. **Sampling and label workflow:** materialize the frozen external opportunity/control frame without model access; provide a local template/CLI for cell/bin coverage, blinded labels, second review, locking, and adjudication.
4. **Offline evaluator:** build ledger reconciliation, episode matching, provenance/coverage exclusions, metric-appropriate confidence intervals, stale audits, and traceable report tables.
5. **Replay calibrator:** replay bounded configurations with runtime-equivalent classification, hysteresis, and deduplication; enforce storm-grouped split and holdout lock.
6. **Synthetic pilot verification:** test coordinator failure, missed/downtime slots, recorder and ledger failure isolation, restarts/deduplication, redaction, all stale/degraded scenarios, and no notifications/threshold mutation.
7. **Documentation and operator runbook:** consent/enable/disable/export/delete/restore steps, evidence labeling guide, backup tombstone enforcement, rollback, and Gate P3 checklist.

## 9. Required Gate P0 decisions

Petr must explicitly approve or amend these items before implementation or collection:

1. Evaluation radius: proposed primary ground truth within 10 km of the configured site.
2. Matching horizon: proposed alert window from 60 minutes before hail onset through event end.
3. Sampling frame: exact CHMI product/version and access terms, 35 dBZ/two-scan opportunity rule, two-hour control slots, strata, 0.10 probability, and frozen seed.
4. Data location and the complete retention/deletion table, including proposed 12-month source-data retention, 30-day backup propagation, and external-evidence limits.
5. Collection sites, coverage grids, permitted evidence sources, and whether the evidence-supported headline radius must be smaller than 10 km.
6. Proposed pilot success criteria, minimum holdout denominators, one-sided decision intervals, and inconclusive rules.

## 10. Proposed design verification criteria

Before Gate P1/P2 can pass, tests and review must demonstrate:

1. A fixture containing successful, failed, timed-out, cancelled, never-started, missed, downtime, recorder-write-failed, and ledger-gap cycles reconciles to the exact expected counts without requiring an observation row; unknown schedule/uptime produces `coverage_unknown` and an inconclusive acceptance result.
2. The same external-source fixture, sampling-frame version, site pseudonym, and seed reproduce byte-identical opportunity/control selections and probabilities. Static analysis or an injected forbidden-access test proves frame generation cannot read prediction level, confidence, thresholds, or alert timing.
3. Coverage-matrix fixtures prove point evidence cannot verify a 10 km negative, one missing cell/bin yields partial coverage, positive-only evidence cannot create a negative, and alert-triggered windows are excluded from recall/specificity denominators.
4. Metric fixtures compare exact-binomial proportion intervals, exposure-aware exact-Poisson rate intervals, and seeded storm-grouped bootstrap lead-time/comparison intervals against independently calculated reference values. Holdouts with one, two, or otherwise insufficient positives, storms, exposure days, adjudications, or controls must return `inconclusive`.
5. Retention tests expire every data class on schedule, delete site-scoped raw/label/derived/export/reference data, revoke its key, apply tombstones before backup restore, and produce only the allowed counts-only audit fields.
6. Existing stale/degraded fixtures plus the six required synthetic scenarios prove stale evidence cannot contribute after the boundary. Observation/ledger write failures remain isolated and observation mode causes no classification, hysteresis, entity, notification, scheduling, or threshold mutation.
7. The final Gate P4 report traces every count to a ledger slot, frozen-frame provenance, locked blinded label, coverage matrix, and prediction episode, and labels every required criterion `pass`, `fail`, or `inconclusive` without subjective overrides.
