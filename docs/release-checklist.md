# Release checklist

Use this checklist before publishing a HACS release tag.

## Local verification

- [ ] `python -m pytest -q`
- [ ] `python -m ruff check .`
- [ ] `python -m compileall -q .`
- [ ] Confirm `manifest.json` version matches the release tag.
- [ ] Confirm `CHANGELOG.md` has an entry for the release.
- [ ] Confirm `README.md` documents install, upgrade, uninstall, privacy/data flow, troubleshooting, support, entities, dashboard snippets, notification blueprint, limitations, and credits.
- [ ] Confirm the README screenshots render and are explicitly described as live or representative.
- [ ] Confirm `SECURITY.md`, `SUPPORT.md`, `CONTRIBUTING.md`, the pull-request template, and Dependabot configuration remain accurate.
- [ ] Confirm every directly referenced third-party GitHub Action is pinned to an immutable commit, every directly executed container image is pinned to a digest, and no pinned action hides a mutable container dependency.

## Home Assistant runtime verification

- [ ] Install as a HACS custom repository in a test Home Assistant instance.
- [ ] Add the integration through the UI config flow.
- [ ] Verify RainViewer metadata/tile fetching works for the configured location.
- [ ] Verify Blitzortung-compatible distance/counter entities are autodetected, selectable manually, or both fields can be left empty for radar-only mode.
- [ ] Verify `unknown`/`unavailable` lightning distance states do not appear as hard integration errors.
- [ ] Verify entities update and survive Home Assistant restart.
- [ ] Verify the notification blueprint can be imported and triggered manually.
- [ ] Confirm the blueprint `source_url` and README import link match the release tag.
- [ ] Verify `/storm_detector/storm-detector-card.js` and `custom:storm-detector-card` render in Czech and English.
- [ ] Verify the HACS repository and blueprint My-links open the intended import flow.
- [ ] Verify upgrade, uninstall, restart, and reinstall steps against a clean test instance.

## Migration from another alerting setup

Avoid duplicate notifications when replacing an existing hail-risk setup:

- [ ] Compare the previous risk level vs integration risk level during at least one storm/radar event.
- [ ] Confirm notifications are at least as useful and not noisier.
- [ ] Confirm stale/missing data behavior is safe and explainable.
- [ ] Only then disable the previous alerting setup.

## Release

- [ ] Create a git tag matching the manifest version, e.g. `v0.2.1`.
- [ ] Push tag and confirm GitHub Actions pass, including HACS validation.
- [ ] Attach screenshots if available.
- [ ] Include limitations: heuristic only, not an official warning source.
- [ ] Publish only a full GitHub release after all tag-triggered workflows pass.
