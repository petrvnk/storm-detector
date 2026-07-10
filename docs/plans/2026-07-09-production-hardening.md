# Radar Hail Risk Production Hardening Implementation Plan

> **For Hermes:** Execute sequentially with controller verification and independent review after every batch.

**Goal:** Move the integration from internal beta toward a production-ready HACS prerelease without changing its safety disclaimer.

**Architecture:** Preserve existing public entities where practical, but separate configured risk thresholds from fixed 50/55/60 diagnostic attributes. Analyze each radar frame as one global pixel field across all fetched tiles, then detect/filter connected components once per frame. Subsequent batches move CPU work off the HA event loop and harden temporal tracking/alert semantics.

**Tech stack:** Python, Home Assistant custom integration APIs, aiohttp, Pillow, pytest, Ruff, HACS validation.

---

## Batch A — Radar pipeline correctness

1. Add failing tests proving non-default configured dBZ thresholds affect watch/warning/urgent core detection and classification.
2. Add failing tests for a connected component crossing a horizontal tile boundary.
3. Add failing tests for configurable minimum core size/noise filtering.
4. Refactor frame analysis to aggregate global pixel samples across all downloaded tiles before connected-component detection.
5. Introduce generic configured-threshold core results while preserving existing fixed-threshold diagnostic attributes where reasonable.
6. Ensure isolated sub-minimum cores do not create active risk, while valid compact cores do.
7. Expose bounded options and English translations for minimum core size.
8. Update README/changelog for the new semantics.
9. Run targeted tests, full pytest, Ruff and compileall; commit locally. Do not push or deploy.

## Batch B — Home Assistant runtime and performance

1. Add real HA integration tests using pytest-homeassistant-custom-component.
2. Use Home Assistant's shared aiohttp session.
3. Download tiles with bounded concurrency and a per-update deadline.
4. Move Pillow decode and pixel/component analysis off the HA event loop.
5. Make unload state cleanup conditional on successful platform unload.
6. Add performance tests/benchmarks for default and maximum configurations.
7. Verify full suite, lint, compile, real HA setup/reload/unload; commit locally. Do not push or deploy.

## Batch C — Tracking and alert semantics

1. Match the same storm component across frames using threshold, centroid distance, intensity and plausible speed constraints.
2. Compute ETA from radial closing speed, not total motion speed.
3. Add hysteresis/confirmation state for escalation and clearing.
4. Separate lightning proximity from a new counter-delta strike and handle counter resets.
5. Make active risk explicitly depend on at least one current contributing signal.
6. Add sequence tests for multiple storms, crossing tracks, stale radar + fresh lightning, counter resets and flapping thresholds.
7. Verify full suite, lint, compile; commit locally. Do not push or deploy.

## Pilot question after implementation

Define and approve an observation/ground-truth dataset and privacy policy before collecting real event data or presenting confidence as hail probability.
