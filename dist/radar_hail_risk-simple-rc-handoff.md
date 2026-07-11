# Radar Hail Risk — Simple RC private colleague handoff

Verified on 2026-07-10 by the S6 controller. This is a private, local test candidate. It is not published, pushed, tagged, released, deployed, or listed in HACS.

## Exact artifact

- Archive: `/home/jarvis/projects/radar-hail-risk/dist/radar_hail_risk-simple-rc.zip`
- SHA-256: `b434ecc708274992b325bf8517a4ea6a71218d7f6a89d4f0784b93f535214c69`
- Archive members: 28, exactly matching the reviewed allowlist
- Source mismatches, duplicate members, forbidden members: 0
- Clean-room result: passed; 13 Python modules compiled, 5 YAML assets parsed, JavaScript syntax checked, temporary layout `config/custom_components/radar_hail_risk` verified

Verify before use:

```text
sha256sum radar_hail_risk-simple-rc.zip
```

The complete output digest must equal the value above.

## Source checkpoint

- Branch: `feat/production-hardening-a`
- Current local HEAD: `26737b922ae4f10dba05e7ab8ff88aed3affaa16` (`chore: checkpoint production hardening baseline`)
- Earlier local runtime checkpoint: `014b8ef` (`Fix radar-core pipeline thresholds, global components, and min-core filtering`)
- The reviewed S2–S4/S5 repair candidate is the exact local working tree above HEAD: 22 modified tracked paths plus 5 untracked source/artifact paths before this handoff file was created.
- Remote baseline remains `origin/main` at `083dc64`; therefore HACS/repository installation would not install this reviewed candidate.

## Generation and reproducibility

Canonical command:

```text
uv run python scripts/build_colleague_bundle.py --output dist/radar_hail_risk-simple-rc.zip
```

S6 generated the canonical archive and two separate temporary rebuilds. All three were byte-identical and had SHA-256 `b434ecc708274992b325bf8517a4ea6a71218d7f6a89d4f0784b93f535214c69`.

## S6 verification results

- Python 3.14 full pytest: 157 passed
- Python 3.14 Ruff: all checks passed
- Python 3.10 full pytest: 144 passed, 3 skipped
- Python 3.10 compileall over `custom_components` and `tests`: passed
- `git diff --check`: passed
- Deterministic double rebuild and byte comparison: passed
- Archive sorted allowlist/member/source/exclusion scan: passed
- Clean-room extraction/install/manifest/HACS/YAML/JavaScript/Python verification: passed
- Prohibited runtime-scope scan: no Open-Meteo, recorder/observation/research dataset, public-tunnel, or deployment implementation found

## Install — only current valid route

The checksum-verified manual ZIP is the only valid current install/test route for this unpushed RC. HACS is not currently authorized and would resolve a different remote revision.

1. Verify the complete SHA-256 above.
2. Extract the ZIP outside the Home Assistant configuration directory.
3. Copy only `custom_components/radar_hail_risk/` to `<HA config>/custom_components/radar_hail_risk/`.
4. Restart Home Assistant.
5. Add Radar Hail Risk from Settings → Devices & services. Use `zone.home` or leave location blank for HA core coordinates. Leave both lightning fields blank for radar-only mode, or configure both compatible distance and counter sensors.
6. Follow `docs/colleague-test-checklist.md` inside the archive for dashboard, notification, and test steps.

Minimum Home Assistant version: 2024.10.0.

## Upgrade

1. Keep the existing config entry, options, automation/card YAML, and previous verified ZIP.
2. Delete the entire existing `<HA config>/custom_components/radar_hail_risk/` directory; do not overlay-copy versions.
3. Copy the complete directory from the newly checksum-verified archive.
4. Restart Home Assistant and reload the existing config entry; do not remove/recreate it.
5. Verify entity IDs, options, stale behavior, and notification wording.

## Rollback

1. Disable Radar Hail Risk notification automations.
2. Keep the existing config entry so saved options and entry-ID-derived entity identities remain intact.
3. Delete the entire integration directory and restore the complete directory from the previous verified ZIP; do not overlay-copy.
4. Restart Home Assistant, reload the existing entry, verify entities, then re-enable notifications if appropriate.

## Uninstall

1. Disable/remove Radar Hail Risk automations and dashboard/card snippets.
2. Remove the Radar Hail Risk config entry.
3. Delete `<HA config>/custom_components/radar_hail_risk/`.
4. Restart Home Assistant and confirm its entities are gone.
5. Remove a HACS custom-repository entry only if a separately authorized future HACS publication was actually used.

## Data sources, privacy, and known limitations

- Radar data: RainViewer. Optional lightning context: Home Assistant entities from Blitzortung-compatible integrations/sensors.
- The integration sends RainViewer requests centered on the configured coordinates.
- It is heuristic, not an official warning source, and does not provide a calibrated hail probability.
- Radar/lightning data can be delayed, stale, unavailable, or wrong. Do not use it for safety-critical automation; official warnings and local safety procedures remain authoritative.
- `confidence_score` is diagnostic quality, not probability.
- Clean-room verification is mechanical compile/parse/layout validation, not a booted Home Assistant end-to-end installation.
- Python 3.10 skips three HA-dependent tests because the current Home Assistant test dependency requires a newer Python; equivalent current-HA coverage runs under Python 3.14.
- No production Home Assistant configuration/state, secrets, credentials, recorder/observation/research data, caches, logs, or local datasets are included.

## Prohibited-scope confirmation

S6 performed no push, merge, tag, GitHub release, HACS publication/listing, deployment, public tunnel, or production Home Assistant access/mutation. The candidate remains local and private.
