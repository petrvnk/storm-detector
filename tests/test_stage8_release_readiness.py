"""Stage 8 HACS release-readiness tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_release_readiness_files_exist() -> None:
    expected = [
        ROOT / "LICENSE",
        ROOT / "CHANGELOG.md",
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SUPPORT.md",
        ROOT / "docs" / "release-checklist.md",
        ROOT / "examples" / "lovelace" / "native-card.yaml",
        ROOT / "examples" / "lovelace" / "mushroom-card.yaml",
        ROOT / "examples" / "lovelace" / "weather-tab.yaml",
        ROOT / ".github" / "workflows" / "validate.yml",
        ROOT / ".github" / "workflows" / "hassfest.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
        ROOT / ".github" / "pull_request_template.md",
        ROOT / ".github" / "dependabot.yml",
        ROOT / "docs" / "screenshots" / "storm-detector-live-storm.png",
        ROOT / "docs" / "screenshots" / "storm-detector-clear.png",
        ROOT / "docs" / "screenshots" / "storm-detector-degraded.png",
    ]

    missing = [path for path in expected if not path.exists()]
    assert not missing, f"Missing release-readiness files: {missing}"


def test_manifest_and_hacs_metadata_are_release_ready() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "storm_detector" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    manifest_keys = list(manifest)
    assert manifest_keys[:2] == ["domain", "name"]
    assert manifest_keys[2:] == sorted(manifest_keys[2:])
    assert manifest["domain"] == "storm_detector"
    assert manifest["version"] == "0.2.1"
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert "http" in manifest["dependencies"]
    assert hacs["name"] == "Storm Detector"
    assert hacs["homeassistant"] >= "2024.10.0"
    assert hacs["hide_default_branch"] is True
    assert hacs["render_readme"] is True

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{manifest["version"]}"' in pyproject


def test_readme_contains_public_installation_support_and_privacy_guidance() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Install with HACS" in readme
    assert "Minimum Home Assistant version: **2024.10.0**" in readme
    assert "currently installed as a **HACS custom repository**" in readme
    assert "Use normal HACS search only after" in readme
    assert "https://github.com/petrvnk/storm-detector" in readme
    assert "my.home-assistant.io/redirect/hacs_repository" in readme
    assert "my.home-assistant.io/redirect/blueprint_import" in readme
    assert "## Upgrade" in readme
    assert "## Uninstall" in readme
    assert "## Privacy and data flow" in readme
    assert "## Troubleshooting" in readme
    assert "## Support and security" in readme
    assert "approximate monitored map area" in readme
    assert "Never edit Home Assistant `.storage`" in readme
    assert "Limitations" in readme
    assert "not an official warning source" in readme
    assert "Credits" in readme
    assert "RainViewer" in readme
    assert "Blitzortung-compatible" in readme
    assert "radar-only" in readme
    assert "examples/lovelace/native-card.yaml" in readme
    assert len(readme.splitlines()) < 280
    assert "unpushed RC" not in readme


def test_public_screenshots_are_valid_readable_images() -> None:
    screenshot_dir = ROOT / "docs" / "screenshots"
    for name in (
        "storm-detector-live-storm.png",
        "storm-detector-clear.png",
        "storm-detector-degraded.png",
    ):
        with Image.open(screenshot_dir / name) as image:
            image.verify()
        with Image.open(screenshot_dir / name) as image:
            assert image.width >= 320
            assert image.height >= 120
            assert image.info == {}


def test_public_governance_and_dependabot_are_configured() -> None:
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
    pull_request_template = (ROOT / ".github" / "pull_request_template.md").read_text(
        encoding="utf-8"
    )
    dependabot = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))

    assert "security/advisories/new" in security
    assert "exact home coordinates" in security
    assert "Public contracts" in contributing
    assert "HACS" in contributing and "Hassfest" in contributing
    assert "best-effort" in support
    assert "Safety and privacy" in pull_request_template
    ecosystems = {item["package-ecosystem"] for item in dependabot["updates"]}
    assert ecosystems == {"pip", "github-actions"}


def test_workflows_pin_the_complete_action_and_container_execution_surface() -> None:
    workflow_documents = [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in (ROOT / ".github" / "workflows").glob("*.yml")
    ]
    steps = [
        step
        for workflow in workflow_documents
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    ]
    uses_values = [step["uses"] for step in steps if "uses" in step]
    run_values = [step["run"] for step in steps if "run" in step]
    execution_values = uses_values + run_values

    hacs_step = next(
        step for step in steps if str(step.get("uses", "")).startswith("docker://ghcr.io/hacs/action@")
    )
    assert hacs_step["env"] == {
        "INPUT_CATEGORY": "integration",
        "INPUT_COMMENT": "false",
        "INPUT_REPOSITORY": "${{ github.repository }}",
        "INPUT_GITHUB_TOKEN": "${{ github.token }}",
    }

    for uses_value in uses_values:
        if uses_value.startswith("docker://"):
            assert re.fullmatch(r"docker://[^@\s]+@sha256:[0-9a-f]{64}", uses_value)
        else:
            assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", uses_value)

    container_images = [
        image
        for value in execution_values
        for image in re.findall(r"ghcr\.io/[a-z0-9._/-]+(?:@sha256:[0-9a-f]{64})?", value)
    ]
    assert container_images
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", image) for image in container_images)

    workflows = "\n".join(str(value) for value in execution_values)

    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflows
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflows
    assert "docker://ghcr.io/hacs/action@sha256:41f6310585d9fb72c7a0e183cce0594355715bc24112b62bc4279b83412edccb" in workflows
    assert "ghcr.io/home-assistant/hassfest@sha256:fb33da5538163d271e0f06557d70af8d5dbe90ae60e2826e7f510c1ea90c564c" in workflows
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" not in workflows
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" not in workflows


def test_lovelace_examples_use_clean_entity_ids() -> None:
    examples_dir = ROOT / "examples" / "lovelace"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in examples_dir.glob("*.yaml"))

    assert "sensor.storm_detector_level" in combined
    assert "sensor.storm_detector_summary" in combined
    assert "binary_sensor.storm_detector_data_stale" in combined
    assert "device_tracker.storm_detector_storm_core" in combined


def test_notification_blueprint_includes_minimal_entities_and_cooldown() -> None:
    blueprint = (
        ROOT / "blueprints" / "automation" / "storm_detector" / "storm_notification.yaml"
    ).read_text(encoding="utf-8")

    assert "storm_level_sensor" in blueprint
    assert "storm_summary_sensor" not in blueprint
    assert "cooldown_minutes" in blueprint
    assert "message_text" in blueprint


def test_notification_blueprint_import_is_pinned_to_manifest_release() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "storm_detector" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    tag = f"v{manifest['version']}"
    blueprint = (
        ROOT / "blueprints" / "automation" / "storm_detector" / "storm_notification.yaml"
    ).read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f"/blob/{tag}/blueprints/automation/storm_detector/storm_notification.yaml" in blueprint
    assert f"%2Fblob%2F{tag}%2Fblueprints%2Fautomation%2Fstorm_detector%2Fstorm_notification.yaml" in readme
    assert "/blob/main/blueprints/automation/storm_detector/storm_notification.yaml" not in blueprint


def test_release_checklist_covers_runtime_and_migration_verification() -> None:
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "Home Assistant runtime verification" in checklist
    assert "Migration from another alerting setup" in checklist
    assert "Compare the previous risk level" in checklist
    assert "HACS validation" in checklist
    assert "not an official warning source" in checklist


def test_release_checklist_tag_matches_manifest_version() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "storm_detector" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert f"`v{manifest['version']}`" in checklist
    assert "`v0.0.1`" not in checklist


def test_bug_report_sets_safe_diagnostics_expectations() -> None:
    template = (
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
    ).read_text(encoding="utf-8")

    assert "omit" in template
    assert "identifying config" in template
    assert "location details" in template
    assert "review" in template
    assert "private entity names" in template
    assert "addresses" in template
    assert "log details" in template
