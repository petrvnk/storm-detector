# Release checklist

Use this checklist before publishing a HACS release tag.

The private Simple RC colleague bundle is not a publication authorization. For that
local handoff, also complete the bundle gate below and
[`colleague-test-checklist.md`](colleague-test-checklist.md); do not tag, push, publish,
deploy, or access a real Home Assistant configuration as part of bundle verification.

## Private colleague bundle gate

- [ ] Run `uv run python scripts/build_colleague_bundle.py --output dist/radar_hail_risk-simple-rc.zip`.
- [ ] Record `sha256sum dist/radar_hail_risk-simple-rc.zip`.
- [ ] Generate a second archive at a separate temporary path and confirm identical SHA-256 and member lists.
- [ ] Confirm every member exactly matches the generator's explicit allowlist.
- [ ] Confirm the exclusion scan rejects Git/GitHub metadata, caches, virtual environments, `dist/` inputs, coverage/build/log output, `.env*`, credentials/tokens/keys, `.storage`, `secrets.yaml`, `configuration.yaml`, local HA state/config, recorder/observation data, and research artifacts.
- [ ] Confirm clean-room extraction and temporary `config/custom_components/radar_hail_risk/` installation verification pass without reading or mutating a real HA configuration.
- [ ] Validate `hacs.json`, integration `manifest.json`, directory naming, blueprint path/content, and all referenced card/example paths.
- [ ] Complete the Python 3.14/3.10 tests, Ruff, compileall, and `git diff --check` gates.

## Local verification

- [ ] `python -m pytest -q`
- [ ] `python -m ruff check .`
- [ ] `python -m compileall -q .`
- [ ] Confirm `manifest.json` version matches the release tag.
- [ ] Confirm `CHANGELOG.md` has an entry for the release.
- [ ] Confirm `README.md` documents install, entities, dashboard snippets, notification blueprint, limitations, and credits.

## Home Assistant runtime verification

- [ ] Install as a HACS custom repository in a test Home Assistant instance.
- [ ] Add the integration through the UI config flow.
- [ ] Verify RainViewer metadata/tile fetching works for the configured location.
- [ ] Verify Blitzortung-compatible distance/counter entities are autodetected, selectable manually, or both fields can be left empty for radar-only mode.
- [ ] Verify `unknown`/`unavailable` lightning distance states do not appear as hard integration errors.
- [ ] Verify entities update and survive Home Assistant restart.
- [ ] Verify the notification blueprint can be imported and triggered manually.

## Migration from another alerting setup

Avoid duplicate notifications when replacing an existing hail-risk setup:

- [ ] Compare the previous risk level vs integration risk level during at least one storm/radar event.
- [ ] Confirm notifications are at least as useful and not noisier.
- [ ] Confirm stale/missing data behavior is safe and explainable.
- [ ] Only then disable the previous alerting setup.

## Release

- [ ] Create a git tag matching the manifest version, e.g. `v0.0.1`.
- [ ] Push tag and confirm GitHub Actions pass, including HACS validation.
- [ ] Attach screenshots if available.
- [ ] Include limitations: heuristic only, not an official warning source.
