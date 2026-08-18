# RainViewer upstream-load hardening

Date: 2026-08-18
Status: approved implementation scope (public-release item 1)

## Goal

Reduce repeated RainViewer traffic without delaying local lightning evaluation, preserve fail-closed/stale semantics, and make many independent Home Assistant installations naturally de-synchronize.

## Frozen behavior

- Risk thresholds, evidence kinds, storm-core algorithms, entity IDs, attributes, card contract, and blueprint contract do not change.
- Coordinator continues evaluating local lightning roughly once per minute.
- Radar frames remain current according to RainViewer metadata timestamps and the configured stale timeout.
- Failures remain non-fatal and recover automatically.

## Design

### 1. Metadata cadence

- Keep the coordinator's local evaluation interval configurable (default 60 s).
- Increase RainViewer metadata TTL from 120 s to 300 s, matching the upstream frame cadence.
- Preserve the last successful metadata payload during a transient refresh failure so frame age/stale rules, not a single failed request, determine availability.

### 2. Bounded analyzed-frame cache

Cache successful `AnalyzedFrame` values in memory using a bounded LRU.

Key inputs:

- validated RainViewer host and frame path/time;
- monitored latitude/longitude;
- analysis radius, zoom, tile size;
- watch/warning/urgent dBZ thresholds;
- minimum connected-core pixel count.

The cache stores only compact analyzed results, never raw tile bytes. It is process-local, bounded to 64 entries, cleared by restart/update, and does not persist private location data.

Rules:

- successful analyses are cached;
- `None`, partial failures, and zero-coverage results are not cached;
- an unchanged four-frame window performs zero new tile downloads;
- when one new frame arrives, only that frame is downloaded/analyzed;
- changed location/options produce a different key;
- concurrent requests for one key share one in-flight task.

### 3. HTTP retry and cooldown

- Keep at most one immediate retry for transient network/408/5xx failures.
- Use exponential retry delay with bounded jitter.
- Do not immediately retry 429 responses.
- Register a bounded per-origin cooldown for `429`; use an exact-request cooldown after exhausted network/408/5xx failures so one bad tile or metadata endpoint does not suppress healthy sibling URLs. Honor numeric `Retry-After` when present.
- Requests during cooldown fail quietly without touching the network.
- A successful request after cooldown resets the applicable failure state.

### 4. Request jitter

Apply bounded random jitter to retry delays. The coordinator keeps evaluating local lightning at its configured interval; only the RainViewer metadata/tile path is throttled, so upstream hardening does not add several minutes of lightning latency.

## Safety and privacy

- No disk cache.
- No credentials or response bodies in logs.
- Cache keys include coordinates only in process memory.
- Cache and cooldown registries are bounded.
- Cancellation drains shared work and never caches incomplete results.

## Verification gates

1. Existing full suite remains green.
2. Focused tests prove cache hit, one-new-frame behavior, invalidation, boundedness, failure retry, in-flight deduplication, 429 cooldown, 5xx recovery, stale metadata fallback, and jitter bounds.
3. Ruff, mypy in the supported environment, compileall, `git diff --check`, and tracked JSON/YAML parsing pass.
4. Independent spec and quality review run against a clean detached worktree.
5. No release, push, or live Home Assistant deployment in this scope.
