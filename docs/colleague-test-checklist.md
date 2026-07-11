# Colleague test checklist — Simple RC

This is a private, local test handoff. It is not a public release or HACS listing. Use a non-production Home Assistant test instance where possible. Minimum supported Home Assistant version: **2024.10.0**.

## Before installation

- [ ] Record the ZIP SHA-256 supplied by Petr and verify it locally before extracting.
- [ ] Confirm Home Assistant has a correct core location or an entity with coordinates such as `zone.home`.
- [ ] Decide between radar-only mode and optional Blitzortung-compatible lightning sensors.
- [ ] Do not use this heuristic integration for safety-critical automation.

## Install

The **checksum-verified manual archive** is the only valid current install/test route for this unpushed RC. Do not substitute a repository checkout, an unverified ZIP, or a HACS download.

### Manual archive install — current route

1. Run `sha256sum radar_hail_risk-simple-rc.zip` and compare the complete digest with the checksum supplied by Petr.
2. Extract `radar_hail_risk-simple-rc.zip` outside the Home Assistant configuration directory.
3. Copy only the extracted `custom_components/radar_hail_risk/` directory to `<HA config>/custom_components/radar_hail_risk/`.
4. Restart Home Assistant.
5. Keep the original verified ZIP for rollback. Do not copy the whole archive into the HA config directory.

### Conditional HACS route (not currently authorized)

The private HACS custom repository instructions are retained only for a possible later handoff. They apply only after separately authorized publication of this exact reviewed source and SHA-256 checksum. HACS is not an equivalent current path; until that authorization is given, do not use HACS to install or test this RC.

If separately authorized, add the authorized private repository URL in HACS as category **Integration**, install **Radar Hail Risk**, restart Home Assistant, and do not publish or submit the repository to the public HACS catalog.

## Simple setup

1. Settings → Devices & services → Add integration → **Radar Hail Risk**.
2. Select `zone.home` as the location source, or leave location blank to use Home Assistant's core coordinates.
3. For radar-only operation, leave both lightning fields blank.
4. Optionally select a matching Blitzortung-compatible lightning distance sensor and counter sensor. Configure both or neither.
5. Leave the advanced options at their defaults for the first test.

Expected default entities:

- `sensor.radar_hail_risk_level`
- `sensor.radar_hail_risk_summary`
- `binary_sensor.radar_hail_risk_active`
- `binary_sensor.radar_hail_risk_data_stale`

## Minimal dashboard and notifications

- [ ] Copy `examples/lovelace/native-card.yaml` into a manual dashboard card and adjust entity IDs if Home Assistant generated different names.
- [ ] Import or copy `blueprints/automation/radar_hail_risk/hail_risk_notification.yaml`.
- [ ] Create an automation from the blueprint using the level sensor, optional summary sensor, notify service, language, minimum level, and cooldown.
- [ ] Confirm the blueprint is opt-in and did not change any dashboard or automation automatically.

## Test procedure

Record the time, level, summary, `evidence_kind`, stale state, and whether the wording was useful for each applicable step. Never manufacture unsafe weather conditions; wait for real data or inspect states without acting on them.

- [ ] **First update:** after setup, wait for the first refresh. Confirm the level is understandable and Data Stale is not silently clear when radar/location data is unavailable.
- [ ] **Normal refresh:** observe at least two normal update cycles. Confirm entities continue updating and the summary contains no internal diagnostics.
- [ ] **Radar-supported strong event:** when real radar evidence is available, confirm `warning` says possible hail and `urgent` appears only with current urgent radar-core evidence.
- [ ] **Lightning-only wording:** when current lightning exists without radar hail evidence, confirm the warning says thunderstorm/lightning and that hail is not confirmed; it must not become `urgent`.
- [ ] **Stale/outage:** during a real source outage or safe network-isolated test instance, confirm stale/unusable radar without current lightning becomes `unavailable`, not a false-clear `none`.
- [ ] **Restart/reload:** restart Home Assistant, then reload the config entry. Confirm entity IDs and options persist and updates resume.
- [ ] **Optional Blitzortung:** add both distance and counter sensors, reload, and confirm unavailable/unknown lightning states do not become hard integration errors.
- [ ] Report noisy warnings, unclear wording, stale behavior, and approximate event time/location to Petr; do not send credentials, `.storage`, `secrets.yaml`, or a full HA config.

## Upgrade

1. Save the current integration version, options, automation, card YAML, and verified previous ZIP. Keep the existing config entry: its entry ID is part of the entity unique IDs and preserves the options and entity identities.
2. For the current RC manual install, first remove the entire `<HA config>/custom_components/radar_hail_risk/` directory, then copy the new complete directory from the checksum-verified archive into its place; do not overlay-copy files. A HACS redownload/update applies only to a later HACS publication separately authorized for the exact reviewed source and checksum.
3. Restart Home Assistant and reload the existing config entry; do not remove and recreate it.
4. Confirm the existing entity IDs, options, dashboard, and automation still work; repeat first-update, normal-refresh, stale, and notification wording checks.

## Rollback

1. Disable the Radar Hail Risk notification automation.
2. Keep the existing Radar Hail Risk config entry. Removing it loses saved options and can change entry-ID-derived entity identities.
3. For the current RC manual install, delete the entire `<HA config>/custom_components/radar_hail_risk/` directory and copy the complete previous checksum-verified directory into its place; never overlay-copy versions. A HACS redownload applies only if that exact HACS publication was separately authorized and its reviewed version is available.
4. Restart Home Assistant, reload the existing config entry, and verify its existing entities before re-enabling notifications.

## Uninstall

1. Disable and remove Radar Hail Risk automations created from the blueprint.
2. Remove copied Radar Hail Risk dashboard/card snippets and the custom card resource if one was added.
3. Remove the Radar Hail Risk config entry. Config-entry removal is for uninstall only, not upgrade or rollback.
4. Manually delete `<HA config>/custom_components/radar_hail_risk/`. Remove the integration in HACS and delete its private custom repository entry only if a separately authorized HACS publication was actually used.
5. Restart Home Assistant and confirm no Radar Hail Risk entities remain.

## Privacy, sources, and limitations

- Radar data comes from [RainViewer](https://www.rainviewer.com/api.html); optional lightning context comes from Home Assistant entities provided by Blitzortung-compatible integrations/sensors.
- Home Assistant and HACS provide the runtime/install platform. See `README.md` and `LICENSE` for credits and license terms.
- Radar Hail Risk is heuristic only and **not an official warning source**. It does not provide a calibrated hail probability.
- Radar/lightning feeds can be delayed, stale, unavailable, or wrong. Do not use the integration for safety-critical automation; keep official weather warnings and local safety procedures as the authority.
- The integration sends RainViewer requests centered on the configured coordinates. Do not share Home Assistant configuration, secrets, tokens, recorder data, or precise location diagnostics beyond what the tester intentionally reports.
