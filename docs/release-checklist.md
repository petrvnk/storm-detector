# Release checklist

Use this checklist before publishing a HACS release tag.

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
- [ ] Verify Blitzortung-compatible distance/counter entities are selected or configured.
- [ ] Verify stale/degraded source diagnostics are visible.
- [ ] Verify entities update and survive Home Assistant restart.
- [ ] Verify the notification blueprint can be imported and triggered manually.

## Migration from local watcher

Do not remove or disable an existing local watcher until parity is confirmed:

- [ ] Compare local watcher risk level vs integration risk level during at least one storm/radar event.
- [ ] Confirm notifications are at least as useful and not noisier.
- [ ] Confirm stale/missing data behavior is safe and explainable.
- [ ] Only then disable the local watcher service/script.

## Release

- [ ] Create a git tag matching the manifest version, e.g. `v0.0.1`.
- [ ] Push tag and confirm GitHub Actions pass, including HACS validation.
- [ ] Attach screenshots if available.
- [ ] Include limitations: heuristic only, not an official warning source.
