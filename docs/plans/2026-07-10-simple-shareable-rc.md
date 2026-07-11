# Simple Shareable RC Technical Design

> **For Hermes:** This is the S0 architecture/UX scope decision for the authorized Simple RC chain. It is planning only. Execute the exact S1-S4 implementation batches below, require S5 independent review, then allow S6 controller verification and colleague handoff. Any failed review or gate returns through a narrow repair and independent re-review before the chain may advance.

**Goal:** Produce the smallest stable Home Assistant Radar Hail Risk release that Petr can privately share with one colleague for testing.

**Architecture:** Keep the existing single-config-entry Home Assistant custom integration. Use one configured location, RainViewer radar as the required evidence source, optional Blitzortung-compatible Home Assistant sensors for lightning context, and a small default entity/automation surface. Preserve the current safety work: stale/unavailable fail-closed behavior, bounded RainViewer workload, per-update deadline, event-loop offloading, and tested tracking/hysteresis.

**Tech stack:** Python 3.10+/3.14 test matrix, Home Assistant custom integration APIs, aiohttp, Pillow, pytest, Ruff, HACS custom repository install.

---

## 1. Problem Summary

The current worktree contains the right technical ingredients for a useful local Home Assistant integration, but the user-facing scope is drifting toward a broad research/observability product:

- many setup/options fields are visible during first install;
- many entities/attributes are exposed even though a tester mostly needs one warning state and one explanation;
- current wording can blur “storm nearby” vs “possible hail nearby”;
- the current classifier can overclaim `urgent` from lightning-only evidence;
- existing plans include future observation/ground-truth work that is valuable later but not needed for a colleague-test RC.

S0 resolves the product boundary so the coding batches can simplify without removing the hardening already implemented in the dirty worktree.

Inspected current state:

- Dirty implementation files include `custom_components/radar_hail_risk/{const.py,config_flow.py,coordinator.py,rainviewer.py,lightning.py,risk.py,sensor.py,binary_sensor.py,device_tracker.py}` plus tests.
- Batch A-C hardening intent is documented in `docs/plans/2026-07-09-production-hardening.md`:
  - Batch A: threshold-aware global radar core detection and min-core filtering.
  - Batch B: Home Assistant runtime/performance hardening, shared session, bounded concurrency, update deadline, off-loop CPU work.
  - Batch C: storm tracking, radial ETA, hysteresis, lightning counter semantics, active-risk signal gating.
- Current README already states the intended product sources: RainViewer radar, optional Blitzortung-compatible sensors, HA location/options, and no Open-Meteo decision path.

## 2. Goal

Ship a private, simple RC for one colleague to install and test locally in Home Assistant.

In scope:

1. One Home Assistant config entry monitoring one location.
2. Location source is either Home Assistant core location or one selected HA entity such as `zone.home`.
3. RainViewer radar is required for hail-core evidence.
4. Blitzortung-compatible lightning is optional and may be autodetected or manually selected.
5. Radar-only mode is valid and must not surface “lightning not configured” as an error.
6. Warning UX clearly separates:
   - thunderstorm / lightning context;
   - possible hail from radar hail-core evidence;
   - unavailable/stale safety states.
7. Setup and default entities are small enough for a non-author colleague to understand.
8. Existing installs and existing entity IDs are not silently broken.

Out of scope for this RC:

- multiple locations or a global dataset;
- Open-Meteo or forecast-model evidence;
- observation recorder, ground-truth collector, calibration pipeline, public research platform, or deployment platform;
- production publication, HACS public listing, tag/release, push, merge, or live Home Assistant mutation;
- calibrated hail probability claims.

## 3. Assumptions

- “One location only” means one `radar_hail_risk` config entry and one monitored coordinate source. It does not require removing Home Assistant’s single-entry guard (`unique_id=DOMAIN`), which already prevents duplicate entries.
- Blank `location_entity_id` means “use `hass.config.latitude/longitude`”. Selecting `zone.home`, `person.*`, or `device_tracker.*` makes that entity the only location source; if it is missing or lacks coordinates, the integration becomes `unavailable` rather than falling back silently.
- Blitzortung is represented only through Home Assistant entities. The integration should not depend on Blitzortung internals or call Blitzortung APIs directly.
- Current compatibility matters more than a perfect clean slate. Entity classes and unique IDs should remain present unless a migration path is explicit.
- The dirty worktree is treated as the implementation baseline for Simple RC; S1 should stabilize it rather than restart from an older commit.
- “Share with one colleague” means a private HACS custom repository install plus a local checklist/bundle, not public release.

## 4. Proposed Solution

### Architecture overview

Keep this pipeline:

```text
HA config/options flow
  -> RadarHailRiskCoordinator
      -> location resolver: hass.config or selected zone/person/device_tracker
      -> RainViewer metadata/color/tile fetch + radar core analysis
      -> optional HA lightning source normalization
      -> risk classification + hysteresis + summary wording
  -> sensor / binary_sensor / device_tracker entities
  -> optional Lovelace snippets + notification blueprint
```

Do not add new infrastructure. The simplification is primarily UX/API surface control and warning semantics, not a new backend.

### Core user journey

1. User installs the repository as a HACS custom integration.
2. User restarts Home Assistant.
3. User adds “Radar Hail Risk” from Settings → Devices & services.
4. First setup screen asks only for:
   - location source: leave blank to use Home Assistant core location, or choose one entity such as `zone.home`;
   - optional lightning distance sensor;
   - optional lightning counter sensor.
5. If Blitzortung-compatible sensors are detected, prefill distance/counter. If neither is selected, continue in radar-only mode.
6. Do not ask for dBZ thresholds, radii, frame count, zoom, stale timeout, min-core pixels, analysis cadence, or azimuth on first install. Keep those in Advanced options.
7. Integration performs first update:
   - if location invalid: level `unavailable`, data stale true, summary explains missing/invalid location;
   - if RainViewer is unavailable/stale and there is no current lightning: level `unavailable`, never `none` or another false-clear state; source diagnostics explain why;
   - if RainViewer is unavailable/stale but lightning is current: at most a degraded lightning-only `warning`, never radar/hail wording or `urgent`;
   - if radar available and no risk: level `none`, active false;
   - if storm/hail evidence exists: level `watch`, `warning`, or `urgent` with explicit evidence wording.
8. User adds either:
   - a minimal dashboard card using `sensor.radar_hail_risk_level`, `sensor.radar_hail_risk_summary`, `binary_sensor.radar_hail_risk_active`, and `binary_sensor.radar_hail_risk_data_stale`; or
   - the notification blueprint with minimum level and notify target.
9. User tests during real weather and reports whether warnings were useful, too noisy, stale, or unclear.

### Default vs advanced entities

Keep all existing entities for compatibility, but reduce the default mental model.

Default enabled for new installs:

| Entity | Purpose | Rationale |
|---|---|---|
| `sensor.radar_hail_risk_level` | `none`, `watch`, `warning`, `urgent`, `unavailable` | Primary automation state. |
| `sensor.radar_hail_risk_summary` | one-line explanation | Human-facing “why”. |
| `binary_sensor.radar_hail_risk_active` | true only when current non-stale evidence supports an active level | Simple automation trigger. |
| `binary_sensor.radar_hail_risk_data_stale` | stale/unavailable safety indicator | Safety state must remain visible. |

Advanced/diagnostic, preferably disabled by default for new installs but preserved for existing installs:

| Entity | Keep? | Default for new installs | Notes |
|---|---:|---:|---|
| `sensor.radar_hail_risk_max_dbz` | yes | disabled/diagnostic | Useful for debugging; not needed for simple warning. |
| `sensor.radar_hail_risk_core_distance` | yes | disabled/diagnostic | Keep attributes on level sensor for templates. |
| `sensor.radar_hail_risk_lightning_distance` | yes | disabled/diagnostic | Lightning context, not primary RC UX. |
| `sensor.radar_hail_risk_frame_age` | yes | disabled/diagnostic | Debug stale behavior. |
| `sensor.radar_hail_risk_last_error` | yes | disabled/diagnostic | Summary/source attributes should still expose user-safe errors. |
| `device_tracker.radar_hail_storm_core` | yes | disabled/advanced | Useful for maps, but too much for first RC dashboard. |

Compatibility strategy:

- Do not rename entity unique IDs in S1-S4.
- Do not delete entity classes.
- Add Home Assistant entity category / enabled-by-default flags only in a way that affects newly created entity registry entries; existing user-enabled entities remain available.
- Keep existing attributes on `sensor.radar_hail_risk_level` so existing Lovelace templates and automations continue to work.
- Add the stable `evidence_kind` attribute required below without changing existing entity unique IDs. It is additive for compatibility; keep existing `level`, `summary`, `source_status`, `degradation_reasons`, `has_current_signal`, `lightning_triggered`, and core-distance attributes.

### Default vs advanced options

Default setup screen:

- `location_entity_id` (optional; blank = HA core location; commonly `zone.home`);
- `lightning_distance_entity_id` (optional);
- `lightning_counter_entity_id` (optional).

Advanced options screen:

- `lightning_azimuth_entity_id`;
- `analysis_radius_km`;
- `lightning_trigger_radius_km`;
- `warning_lightning_distance_km`;
- `urgent_lightning_distance_km`;
- `core_watch_dbz`;
- `core_warning_dbz`;
- `core_urgent_dbz`;
- `min_core_pixels`;
- `warning_core_distance_km`;
- `urgent_core_distance_km`;
- `rainviewer_frames`;
- `rainviewer_zoom`;
- `min_analysis_interval_seconds`;
- `stale_clear_seconds`.

Advanced options must keep current validation:

- configured dBZ thresholds strictly increase: watch < warning < urgent;
- warning distances are greater than or equal to urgent distances;
- lightning trigger radius is greater than or equal to warning lightning distance;
- all numeric values stay inside `PARAMETER_SPECS` bounds.

### Warning semantics

Keep the existing level enum for compatibility:

```text
none | watch | warning | urgent | unavailable
```

Clarify meaning by evidence, not by adding more levels.

| Level | User wording | Evidence contract |
|---|---|---|
| `none` | “No radar risk detected” | RainViewer current enough, no current radar core/lightning warning signal. |
| `watch` | “Storm watch” or “Possible hail watch” | Near-threshold or non-warning radar core; useful awareness but not a hail warning. |
| `warning` with radar core | “Possible hail nearby” | Configured warning/urgent radar core is inside warning distance, or strong high-reflectivity core is close enough under current fallback semantics. |
| `warning` lightning-only | “Thunderstorm/lightning nearby; hail not confirmed” | Current Blitzortung-compatible lightning proximity/counter evidence exists, but no current radar hail-core evidence. This may activate notifications, but must not say “hail warning”. |
| `urgent` | “High hail risk nearby” | Requires current radar urgent-core evidence inside urgent distance, optionally strengthened or forced immediate by a new nearby lightning strike. |
| `unavailable` | “Risk unavailable” | Required location/radar evidence is unavailable/stale enough that the integration cannot make a safe claim. |

S2 must fix the lightning-only urgent overclaim:

- A new nearby lightning strike may bypass hysteresis for fast notification.
- Lightning-only evidence must be capped at `warning`, and the summary/title must say thunderstorm/lightning, not hail.
- `urgent` must require current radar hail-core evidence. Lightning can strengthen urgency only when radar already supports possible hail.
- If radar is stale/unavailable and lightning is current, publish a degraded thunderstorm warning at most; do not publish `urgent` or “hail risk” wording.

### Why this approach

- It preserves the technically useful Batch A-C hardening instead of backing it out.
- It reduces first-run complexity by moving tuning to Advanced options, not by deleting capability.
- It keeps automations stable because the primary enum and entity IDs remain unchanged.
- It makes the RC testable by one colleague without requiring research infrastructure or calibrated claims.

## 5. Alternatives & Trade-offs

### Alternative A — Keep all current setup fields visible

Rejected for Simple RC. It preserves power-user control but makes the colleague-test install look experimental and harder to explain.

### Alternative B — Remove diagnostic entities entirely

Rejected. Removing entities risks breaking existing installs and removes useful debug data during early testing. Prefer disabled-by-default diagnostics for new installs.

### Alternative C — Introduce new levels such as `storm_warning` and `hail_warning`

Rejected for RC because it breaks the stable enum and existing automation examples. Use additive summary/evidence attributes and notification wording instead.

### Alternative D — Implement observation/ground-truth recorder before sharing

Deferred. It is valuable for calibration, but it is not required to learn whether the current local integration can be installed and understood by one tester.

### Alternative E — Add Open-Meteo forecast context

Rejected for this product boundary. Forecast/model data increases complexity and uncertainty; this RC is current local radar plus optional lightning only.

## 6. Data Models / APIs / Contracts

### Config entry contract

Existing keys remain valid:

```python
{
    "location_entity_id": str | None,
    "lightning_distance_entity_id": str | None,
    "lightning_counter_entity_id": str | None,
    "lightning_azimuth_entity_id": str | None,  # advanced
    "analysis_radius_km": int,
    "lightning_trigger_radius_km": int,
    "warning_lightning_distance_km": int,
    "urgent_lightning_distance_km": int,
    "core_watch_dbz": int,
    "core_warning_dbz": int,
    "core_urgent_dbz": int,
    "min_core_pixels": int,
    "warning_core_distance_km": int,
    "urgent_core_distance_km": int,
    "rainviewer_frames": int,
    "rainviewer_zoom": int,
    "min_analysis_interval_seconds": int,
    "stale_clear_seconds": int,
}
```

S3 may change which keys appear on the first setup form, but must not stop reading old keys from `entry.data` or `entry.options`.

### Coordinator payload contract

Existing payload fields remain. The simple RC default UI and automation contracts rely on:

```python
{
    "level": "none" | "watch" | "warning" | "urgent" | "unavailable",
    "summary": str,
    "evidence_kind": "none" | "radar_storm" | "radar_hail" | "lightning_only" | "radar_hail_with_lightning" | "unavailable",
    "is_stale": bool,
    "has_current_signal": bool,
    "source_status": {"location": str, "radar": str, "lightning": str},
    "degradation_reasons": tuple[str, ...] | list[str],
}
```

`evidence_kind` is required as a stable, machine-readable discriminator. It must be exposed additively on the primary level entity, produced deterministically for every published payload, and remain independent of translated or human-edited `summary` text. The notification blueprint must branch on this discriminator (together with `level`), and regression tests must prove lightning-only and radar-supported warning titles/messages remain distinct. Existing automations that only consume `level` continue to work.

### Entity contract

Default automation contract:

- `sensor.radar_hail_risk_level` state is the stable level after hysteresis.
- `sensor.radar_hail_risk_summary` is user-safe, no internal diagnostics such as `lightning_counter_delta`.
- `binary_sensor.radar_hail_risk_active` is true only when level is active and `has_current_signal` is not false.
- `binary_sensor.radar_hail_risk_data_stale` reflects stale safety state.

Diagnostic contract:

- Keep fixed 50/55/60 attributes for compatibility.
- Keep configured-threshold attributes (`core_watch_distance_km`, `core_warning_distance_km`, `core_urgent_distance_km`) authoritative for classification.
- Keep `source_status`, `degradation_reasons`, `radar_diagnostics`, and `lightning_diagnostics` for troubleshooting.

### Notification contract

Blueprint titles/messages must branch on the stable `evidence_kind` attribute rather than parsing `summary`, and must not overclaim:

- `warning` + lightning-only evidence: storm/lightning wording, not “hail warning”.
- `warning` + radar hail evidence: “possible hail”.
- `urgent`: only radar-supported high hail risk.

Blueprint tests must consume the same machine-readable discriminator and assert distinct English and Czech titles/messages for `lightning_only`, `radar_hail`, and `radar_hail_with_lightning` evidence. Unknown/missing discriminator values from a transitional existing entity must fall back conservatively without hail wording.

Czech wording should follow the same distinction:

- lightning-only warning: “Blízká bouřka / blesky poblíž”;
- radar hail warning: “Možné kroupy poblíž”;
- urgent radar hail: “Vysoké riziko krup”.

## 7. Implementation Notes

### S1 — Stabilize and checkpoint the approved runtime worktree

Objective: turn the existing dirty Batch A-C worktree into an exact, auditable, green baseline before UX changes.

Required scope audit and cleanup, before any runtime fix:

1. Capture the exact tracked and untracked inventory with `git status --short`, `git diff --stat`, `git diff --name-status`, and explicit inspection of every untracked path; record a concise categorized change inventory in this plan or a linked stabilization note.
2. Compare each path to the authorized Batch A-C runtime hardening and regression scope. Preserve approved source/tests/docs even when untracked.
3. Remove only artifacts positively identified as accidental or generated (for example caches, coverage/build output, temporary logs, or editor files). Do not delete or reset an unexplained file merely to make status smaller.
4. Re-run the exact inventory after cleanup and include the remaining tracked/untracked list in the S1 handoff so controller and reviewer can account for every path.

Files likely touched only for fixes:

- `custom_components/radar_hail_risk/rainviewer.py`
- `custom_components/radar_hail_risk/coordinator.py`
- `custom_components/radar_hail_risk/risk.py`
- `custom_components/radar_hail_risk/lightning.py`
- `custom_components/radar_hail_risk/async_utils.py`
- existing tests under `tests/`

Required checks:

- Targeted: `tests/test_rainviewer_stage3.py`, `tests/test_runtime_hardening.py`, `tests/test_tracking_alert_semantics.py`, `tests/test_stage5_coordinator_entities.py`, `tests/test_stage6_resilience.py`.
- Full controller gate commands listed below.

Acceptance:

- Configured thresholds drive core detection/classification.
- Global connected components across tiles are preserved.
- Min-core filtering prevents isolated noise from activating risk.
- RainViewer workload is bounded and off-loop.
- Update deadline and cancellation drain behavior remain tested.
- Tracking/hysteresis/current-signal semantics remain tested.
- Every remaining tracked/untracked path is represented in the concise inventory; accidental/generated cleanup is itemized separately.
- The full Python 3.14/3.10, Ruff, compileall, diff, and exact status/diff controller gate passes before any local checkpoint.
- Only after the controller verification gate passes may S1 create local milestone commit(s). Record resulting local commit ID(s) and exact status, then require independent read-only review before S1 completion; never push, merge, tag, release, deploy, or rewrite unrelated history.

### S2 — Correct warning semantics and define the minimal HA contract

Objective: make levels and wording safe for non-expert testers.

Files expected:

- `custom_components/radar_hail_risk/risk.py`
- `custom_components/radar_hail_risk/coordinator.py`
- `custom_components/radar_hail_risk/const.py` for stable `evidence_kind` values/constants if consistent with local patterns
- `custom_components/radar_hail_risk/sensor.py` to expose the required additive `evidence_kind` attribute
- `custom_components/radar_hail_risk/manifest.json` to correct `iot_class` from `local_polling` to `cloud_polling`, because runtime decisions poll RainViewer cloud services
- `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`
- `README.md`
- `CHANGELOG.md`
- `custom_components/radar_hail_risk/translations/en.json` and Czech translations/resources used by the integration or blueprint
- `tests/test_tracking_alert_semantics.py`
- `tests/test_stage5_coordinator_entities.py`

Tests to add/update:

1. Lightning-only current proximity inside urgent distance with counter delta produces at most `warning`, not `urgent`.
2. New nearby lightning can still force immediate publication of a warning without waiting for two confirmations.
3. Radar urgent core still produces `urgent`.
4. Radar urgent core plus new lightning remains `urgent` and may force immediate publication.
5. Summary/notification title for lightning-only warning does not contain hail wording.
6. Internal event diagnostics do not appear in `summary` or `last_error`.
7. Stale/unusable radar with no current lightning always publishes `unavailable`, never `none`, inactive-clear, or any other false-clear state.
8. Stale/unusable radar with current lightning may publish only degraded `lightning_only` warning semantics; it cannot publish radar/hail wording or `urgent`.
9. Every payload exposes a valid `evidence_kind`; the level entity and notification blueprint consume it, and blueprint tests distinguish lightning-only from radar-supported titles/messages without parsing `summary`.
10. `manifest.json` declares `cloud_polling`, and its manifest contract test is updated.

### S3 — Simplify installation, options, and default entity UX

Objective: make first install understandable and preserve compatibility.

Files expected:

- `custom_components/radar_hail_risk/config_flow.py`
- `custom_components/radar_hail_risk/translations/en.json`
- `custom_components/radar_hail_risk/sensor.py`
- `custom_components/radar_hail_risk/binary_sensor.py`
- `custom_components/radar_hail_risk/device_tracker.py`
- `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`
- `README.md`
- `tests/test_stage6_resilience.py`
- `tests/test_ha_lifecycle.py`

Implementation direction:

1. First config step shows only location + optional lightning distance/counter.
2. Advanced options keep all numeric tuning and optional azimuth.
3. Existing config entries continue to merge `entry.data`, `entry.options`, and `OPTIONAL_CONF_DEFAULTS` as today.
4. Mark diagnostic entities with `EntityCategory.DIAGNOSTIC` where Home Assistant APIs are available.
5. Prefer `_attr_entity_registry_enabled_default = False` for diagnostic/advanced entities on new installs only; verify existing entity unique IDs remain unchanged.
6. Keep `Data Stale` default enabled.
7. Update README install journey and minimal card to use only default entities.
8. Simplify the README notification-blueprint instructions alongside the quick start, using the minimal default entity contract, and keep them synchronized with the actual inputs in `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`.

Tests to add/update:

1. Config flow initial schema contains only location/distance/counter defaults.
2. Options flow schema contains advanced numeric fields and current saved values.
3. Blank lightning fields remain valid radar-only mode.
4. Partial lightning pair is still rejected.
5. Existing `entry.data` numeric keys are still honored by coordinator.
6. Entity unique IDs stay unchanged.
7. Diagnostic entity default flags/categories are correct where available and fallback-safe in local tests.
8. Simplified notification-blueprint instructions use the minimal default entity contract and match the actual blueprint inputs.

### S4 — Reproducible colleague test bundle and demo procedure

Objective: produce a deterministic, locally shareable colleague-test archive and mechanically verify it without publishing or deploying.

Files expected:

- `scripts/build_colleague_bundle.py` (new deterministic archive generator)
- `README.md`
- `docs/release-checklist.md`
- `docs/colleague-test-checklist.md` (new install/test/upgrade/rollback/uninstall handoff)
- `hacs.json` and `custom_components/radar_hail_risk/manifest.json` only for required HACS/layout corrections
- relevant notification blueprint and Lovelace/card examples when they are part of the colleague handoff

Deterministic archive contract:

1. The committed generator command is exactly:

   ```bash
   uv run python scripts/build_colleague_bundle.py --output dist/radar_hail_risk-simple-rc.zip
   ```

2. The generator uses an explicit allowlist containing only the required `custom_components/radar_hail_risk/` integration package, `hacs.json`, the Radar Hail Risk notification blueprint, the minimal card/example assets referenced by the checklist, and the colleague-facing install/checklist/license/credit documents. Adding any other archive member requires updating and reviewing the allowlist.
3. ZIP members are sorted by POSIX path, use normalized permissions and one fixed ZIP timestamp, and contain byte-identical source content. Running the command twice from the same verified source tree must produce the same SHA-256.
4. The command prints the archive path and SHA-256. S4 records the checksum using `sha256sum dist/radar_hail_risk-simple-rc.zip` and verifies a second generation has the identical digest.
5. The generator rejects symlinks, missing allowlisted files, unexpected output members, and any secret-like/local-only path. It must never package `.git/`, `.github/` unless specifically required by a local validation command and excluded from the final archive, caches (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`), virtual environments, `dist/` inputs, coverage/build output, logs, `.env*`, credential/token/key files, `.storage/`, `secrets.yaml`, `configuration.yaml`, local Home Assistant state/configuration, observations, recorder output, research datasets, or research-only artifacts.

HACS/layout and clean-room verification:

1. Validate repository `hacs.json`, `custom_components/radar_hail_risk/manifest.json`, integration directory naming, blueprint path/YAML, and all referenced card/example paths. Run any HACS validation already available locally; do not publish to HACS.
2. Extract the archive into a newly created temporary directory, reject path traversal/duplicate members, and compare the extracted tree exactly to the allowlist.
3. Mechanically copy/install the extracted integration into a clean temporary `config/custom_components/radar_hail_risk/` layout and verify required Python modules, translations, manifest JSON, blueprint, and card/example assets parse or compile using the repository's existing local tooling.
4. Run the automated Python 3.14/3.10 tests, Ruff, compileall, diff checks, and archive exclusion scan. The temporary clean-room install must not read or mutate Petr's real Home Assistant configuration.

Colleague checklist contents:

- private HACS custom repository and manual archive install paths, with minimum Home Assistant version assumptions;
- simple setup with `zone.home`, radar-only operation, and optional Blitzortung sensors;
- minimal dashboard and notification blueprint instructions;
- test steps for first update, normal refresh, radar-supported strong event, lightning-only wording, stale/outage, restart/reload, upgrade, and optional Blitzortung;
- rollback/uninstall: remove the config entry, automation/card snippets, integration files/HACS custom repository, and restart Home Assistant;
- privacy/data-source credits, heuristic/unofficial-warning and no-safety-critical-automation limitations.

S4 is not docs-only: the deterministic artifact, exact generator, checksum reproducibility, exclusion scan, HACS/layout validation, and clean-room extraction/install evidence are required acceptance artifacts. No push, tag, GitHub release, HACS publication, deployment, public tunnel, or production Home Assistant mutation is allowed.

### S5 — Independent RC review and final colleague handoff gate

Objective: read-only review that the final Simple RC matches S0 and is safe to hand to one colleague.

Reviewer should inspect:

- diff scope against S0/S1-S4;
- setup path and options complexity;
- warning semantics and blueprint wording;
- compatibility of entity IDs and config/options keys;
- test coverage for stale/unavailable, bounded concurrency, timeout, hysteresis, and lightning-only urgent cap;
- README/checklist correctness;
- no Open-Meteo, recorder, global dataset, public release, push/tag/deploy, or production HA mutation.

S5 approval is required before S6 controller verification and handoff.

Required verdict is `APPROVE`, `APPROVE_WITH_COMMENTS`, or `REQUEST_CHANGES`, with severity and file/line evidence. Approval requires exact diff/local commit inspection, verified archive contents and SHA-256, clean-room install evidence, warning/evidence contracts, compatibility, all controller checks, and the explicit exclusions. `APPROVE_WITH_COMMENTS` advances only when every comment is explicitly non-blocking. `REQUEST_CHANGES` creates a narrow linked repair assigned to `jarvis-coder`; S5 must independently re-review the repaired result before S6 can start.

### S6 — Final controller verification and colleague handoff

Objective: after S5 approval, independently prove the complete RC and package are ready for Petr without changing product behavior.

Controller actions:

1. Independently rerun the required Python 3.14/3.10 tests, Ruff, compileall, exact status/diff review, HACS/layout checks, deterministic double-generation, SHA-256 comparison, archive member/exclusion scan, and clean-room extraction/install verification.
2. Verify the local share artifact exists at the recorded path, its checksum matches, it contains only allowlisted assets, and install/upgrade/rollback/uninstall instructions are complete.
3. Confirm no secret, cache, local Home Assistant configuration/state, recorder/observation/research artifact, push, merge, tag, release, HACS publication, deployment, public tunnel, or production Home Assistant mutation occurred.
4. Write or update `dist/radar_hail_risk-simple-rc-handoff.md` with the exact artifact path, SHA-256, source checkpoint/local commit IDs, generation command, verification commands/results, installation/upgrade/rollback steps, data-source credits, and known limitations. Complete the S6 controller card with the same exact evidence.

S6 failure behavior is mandatory: if any check fails or the handoff evidence is incomplete, do not patch product behavior in S6 and do not hand off the archive. Create a narrow linked repair card assigned to `jarvis-coder`, keep S6 blocked, route the repaired scope through independent `jarvis-reviewer` re-review, and rerun all affected S6 checks only after that approval. Repeat repair/re-review until approved or surface a genuine capability/product blocker to Petr.

### Controller gates for S1-S6

For S1-S3 code changes, S4 package creation, S5 review evidence, and S6 final verification, controller must run:

```bash
uv run --isolated --python 3.14 --extra dev pytest -q
uv run --isolated --python 3.14 --extra dev ruff check .
uv run --isolated --python 3.10 --extra dev pytest -q
uv run --isolated --python 3.10 --extra dev python -m compileall -q custom_components tests
git diff --check
git status --short
```

If Python 3.14 is unavailable in the runner, controller must report the capability blocker rather than substituting unverified results.

For S4-S6 artifact verification, also run the committed generator and perform the deterministic, checksum, archive allowlist/exclusion, HACS/layout, and clean-room checks specified in S4. The minimum reproducibility commands are:

```bash
rm -f dist/radar_hail_risk-simple-rc.zip
uv run python scripts/build_colleague_bundle.py --output dist/radar_hail_risk-simple-rc.zip
sha256sum dist/radar_hail_risk-simple-rc.zip
```

Generate a second archive into a separate temporary path and assert its SHA-256 and member list equal the first before restoring/recording the canonical artifact. Use a newly created temporary directory for extraction/install verification; never point a check at the real Home Assistant config. Add available markdown/YAML/HACS checks already configured locally; do not introduce a new docs toolchain solely for RC.

## 8. Risks

- Lightning-only warning may still be interpreted as hail risk if dashboard/notification wording is not explicit enough.
- Disabling diagnostic entities by default can surprise testers who expect the current README’s detailed glance card; docs must show how to enable diagnostics if needed.
- Home Assistant entity registry behavior differs between “new default disabled” and existing user-enabled entities; S3 must test/fallback carefully.
- RainViewer color tables and metadata endpoints can change; current fallback/retry/stale behavior must remain visible.
- Sharing with one colleague can expose rough HACS/custom integration assumptions; S4 checklist must include rollback and limitations.
- Current `confidence_score` can be misunderstood as probability; keep it diagnostic and document as heuristic quality only.

## 9. Recommendation

Proceed with the Simple RC chain as defined here:

1. Stabilize the current hardening baseline.
2. Fix warning semantics so lightning-only evidence never produces hail-urgent claims.
3. Simplify setup and default entities while preserving compatibility.
4. Produce a private colleague-test bundle.
5. Require independent review of the complete RC.
6. Require final controller verification and an exact local handoff manifest before colleague handoff.

Do not implement observation/ground-truth, Open-Meteo, multi-location, deployment, or public release work until after the colleague RC feedback and an explicit new approval gate.

## 10. Handover for Coding Agent

### What to implement

Implement S1-S4 only after S0 review approval. Do not implement S5; that is independent read-only reviewer work. Do not perform S6 as a coding batch; it belongs to `jarvis-controller` after S5 approval. Failed S5/S6 checks return only through a narrow linked repair and independent re-review.

### Suggested order

1. S1: stabilize current hardening baseline and make tests green.
2. S2: warning semantics and lightning-only urgent cap.
3. S3: setup/options/entity simplification with compatibility preserved.
4. S4: reproducible colleague test bundle/archive.
5. S5: independent review by `jarvis-reviewer`.
6. S6: final verification and handoff by `jarvis-controller`.

### Expected modules/files

S1 likely:

- `custom_components/radar_hail_risk/rainviewer.py`
- `custom_components/radar_hail_risk/coordinator.py`
- `custom_components/radar_hail_risk/risk.py`
- `custom_components/radar_hail_risk/lightning.py`
- `custom_components/radar_hail_risk/async_utils.py`
- `tests/test_rainviewer_stage3.py`
- `tests/test_runtime_hardening.py`
- `tests/test_tracking_alert_semantics.py`
- `tests/test_stage5_coordinator_entities.py`
- `tests/test_stage6_resilience.py`

S2 likely:

- `custom_components/radar_hail_risk/risk.py`
- `custom_components/radar_hail_risk/coordinator.py`
- `custom_components/radar_hail_risk/sensor.py` for the required additive evidence attribute
- `custom_components/radar_hail_risk/const.py` for its stable values/constant if consistent with local patterns
- `custom_components/radar_hail_risk/manifest.json`
- `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`
- `tests/test_tracking_alert_semantics.py`
- `tests/test_stage5_coordinator_entities.py`
- `README.md`
- `CHANGELOG.md`

S3 likely:

- `custom_components/radar_hail_risk/config_flow.py`
- `custom_components/radar_hail_risk/translations/en.json`
- `custom_components/radar_hail_risk/sensor.py`
- `custom_components/radar_hail_risk/binary_sensor.py`
- `custom_components/radar_hail_risk/device_tracker.py`
- `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`
- `tests/test_stage6_resilience.py`
- `tests/test_ha_lifecycle.py`
- `README.md`

S4 likely:

- `scripts/build_colleague_bundle.py`
- `README.md`
- `docs/release-checklist.md`
- `docs/colleague-test-checklist.md`
- allowlisted `examples/lovelace/*.yaml`
- `hacs.json` and manifest/layout files only if validation requires correction

### Required interfaces/contracts

- Preserve `level` enum exactly: `none`, `watch`, `warning`, `urgent`, `unavailable`.
- Preserve current entity unique IDs.
- Preserve current config/options keys and defaults.
- Add and preserve the stable machine-readable `evidence_kind` contract; blueprint/tests must consume it rather than infer evidence from human summary text.
- Preserve `RadarHailRiskCoordinator._effective_config()` merge behavior: defaults < entry data < entry options.
- Preserve stale/unavailable safety:
  - invalid location => unavailable/stale;
  - stale/unusable radar with no current lightning => `unavailable`, never false clear/`none`;
  - stale radar evidence cannot activate hail risk; current lightning may produce degraded storm warning at most;
  - stale lightning cannot trigger urgent/warning;
  - source diagnostics explain degraded behavior.
- Preserve bounded RainViewer workload and update deadline.
- Preserve hysteresis confirmation except explicit force cases.

### Edge cases to handle

- `zone.home` selected but missing or without coordinates.
- Blank location uses Home Assistant core coordinates.
- Blank lightning fields are valid radar-only mode.
- Exactly one of lightning distance/counter is selected: reject in flow.
- Lightning distance/counter states are `unknown`, `unavailable`, empty, stale, invalid, or reset backwards.
- New nearby lightning strike without radar evidence: warning at most, non-hail wording.
- Radar urgent core with lightning: urgent allowed.
- Radar stale with current lightning: degraded storm warning at most; no hail urgent.
- Existing users with diagnostic entities enabled must not lose entity IDs.
- New users should not see a noisy entity list by default.

### What to test

Minimum targeted tests by batch:

- S1:
  - global connected components across tiles;
  - configured thresholds and min-core filtering;
  - bounded tile concurrency;
  - off-loop image/core analysis;
  - update deadline cancellation/drain;
  - storm tracking/hysteresis/current signal.
- S2:
  - lightning-only urgent cap;
  - radar-supported urgent still works;
  - forced immediate warning/urgent behavior is correct;
  - summary/blueprint wording distinguishes storm vs possible hail;
  - stable `evidence_kind` drives blueprint branches and is covered by entity/blueprint tests;
  - stale/unusable radar without current lightning is unavailable, never false clear;
  - manifest declares `cloud_polling`;
  - internal diagnostics remain hidden from user text.
- S3:
  - simple setup schema;
  - advanced options schema/defaults;
  - compatibility with existing entry data/options;
  - entity unique IDs unchanged;
  - diagnostic entity category/default-enabled behavior.
- S4:
  - README and checklist match actual setup flow/entities;
  - deterministic archive generation produces identical SHA-256 twice;
  - HACS/layout and clean-room extraction/install checks pass;
  - archive member allowlist and exclusions prove no Git/cache/secret/local HA/research payload;
  - no public release/deploy instructions beyond private HACS custom repository install;
  - install, upgrade, rollback and uninstall instructions are present.
- S5: independent read-only verdict covers exact diff/commits, package/checksum, clean-room install, contracts, compatibility, complete verification, and exclusions.
- S6: controller independently repeats full code/package verification and writes the exact local handoff manifest; any failure routes to narrow repair plus independent re-review.

### Stop conditions

Block instead of guessing if:

- Home Assistant API behavior around diagnostic default disabling cannot be verified locally;
- Python 3.14 verification cannot run in the required controller environment;
- S2 needs a product decision about whether lightning-only `warning` should activate mobile notifications by default.
