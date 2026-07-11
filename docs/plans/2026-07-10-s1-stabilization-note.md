# S1 Stabilization Inventory

This note records the audited working-tree scope for S1 before any Simple RC UX or warning-semantics changes. The starting checkpoint is `014b8efc35cad13fb4d63bd27ec53962df3007fd` (`Fix radar-core pipeline thresholds, global components, and min-core filtering`), which already contains the approved Batch A implementation.

## Audit commands

```bash
git status --short --untracked-files=all
git diff --stat
git diff --name-status
git diff --numstat
```

Every path reported by those commands was inspected individually. No status-visible cache, coverage, build, log, editor, or other generated artifact was found, so cleanup removed nothing. Unexplained files were not deleted or reset.

## Authorized runtime hardening

Batch B runtime/performance changes:

- `custom_components/radar_hail_risk/__init__.py` — retain config-entry state when platform unload fails.
- `custom_components/radar_hail_risk/coordinator.py` — shared Home Assistant aiohttp session and bounded analysis deadline/drain behavior.
- `custom_components/radar_hail_risk/ha_fallback.py` — coordinator compatibility for the config-entry-aware Home Assistant API.
- `custom_components/radar_hail_risk/rainviewer.py` — bounded tile concurrency, off-loop image/core processing, and cancellation drain.
- `custom_components/radar_hail_risk/async_utils.py` — shared cancellation-drain helper.
- `pyproject.toml` — guarded Home Assistant custom-component test dependency for Python 3.14.2+.

Batch C tracking/alert changes:

- `custom_components/radar_hail_risk/binary_sensor.py` — active state depends on current contributing evidence.
- `custom_components/radar_hail_risk/const.py` — additive current-signal/new-strike payload attributes.
- `custom_components/radar_hail_risk/coordinator.py` — stable-level hysteresis and independent current radar/lightning signal handling.
- `custom_components/radar_hail_risk/lightning.py` — separate proximity, counter-delta strike, stale channels, and counter reset.
- `custom_components/radar_hail_risk/rainviewer.py` — component matching and radial-closing-speed ETA.
- `custom_components/radar_hail_risk/risk.py` — hysteresis and lightning event semantics.
- `custom_components/radar_hail_risk/sensor.py` — expose additive current-signal/new-strike diagnostics.

## Authorized regression coverage

- `tests/conftest.py` — conditionally enable custom integrations in HA-backed tests.
- `tests/test_ha_lifecycle.py` — minimum/current HA coordinator-constructor compatibility plus real HA setup/reload/unload and shared-session lifecycle.
- `tests/test_lightning_stage4.py` — stale channel, new strike, and counter-reset behavior.
- `tests/test_rainviewer_stage3.py` — centroid fields retained in component summaries.
- `tests/test_runtime_hardening.py` — concurrency bounds, off-loop work, cancellation drain, unload behavior, and workload bounds.
- `tests/test_stage5_coordinator_entities.py` — payload/entity current-signal and hysteresis behavior.
- `tests/test_stage6_resilience.py` — schema-default compatibility with real voluptuous schemas.
- `tests/test_tracking_alert_semantics.py` — component tracking, radial ETA, hysteresis, lightning semantics, and active-signal gating.
- `tests/test_update_deadline.py` — deadline timeout and inflight/queued task drain behavior.

## Intentional documentation and controller provenance

These are intentional source-controlled planning/control artifacts, not runtime implementation or generated output:

- `CODER_BATCH_A_PROMPT.md` — original bounded Batch A implementation brief.
- `docs/DEVELOPMENT_CYCLE.md` — controller/reviewer workflow contract.
- `docs/plans/2026-07-09-production-hardening.md` — approved Batch A-C scope.
- `docs/plans/2026-07-10-observation-ground-truth-pilot.md` — planning-only deferred pilot; no recorder or collection runtime is present.
- `docs/plans/2026-07-10-simple-shareable-rc.md` — approved Simple RC design and exact S1-S6 gates.
- `docs/plans/AUTOPILOT_CONTROLLER_TICK.md` — historical hardening controller tick contract.
- `docs/plans/SIMPLE_RC_AUTOPILOT_CONTROLLER_TICK.md` — bounded Simple RC controller tick contract.
- `docs/plans/2026-07-10-s1-stabilization-note.md` — this audit record.

## Cleanup outcome

- Removed generated/accidental paths: none.
- Reset or deleted unexplained paths: none.
- Deferred product work: the observation/ground-truth document remains planning-only and does not authorize implementation.
- Forbidden operations performed: none; no push, merge, tag, release, deployment, production Home Assistant mutation, or history rewrite.

The exact post-audit status and verification results are recorded in the S1 Kanban handoff before controller verification and independent review. A local S1 milestone commit is intentionally deferred until both gates approve it.
