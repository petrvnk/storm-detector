"""Deterministic colleague bundle and clean-room verification tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_colleague_bundle.py"


def _load_bundle_module():
    spec = importlib.util.spec_from_file_location("build_colleague_bundle", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _archive_with_replacement(
    module, tmp_path: Path, member_to_replace: str, replacement: bytes
) -> Path:
    archive_path = tmp_path / "mutated.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for member in module.ALLOWLIST:
            content = replacement if member == member_to_replace else (ROOT / member).read_bytes()
            archive.writestr(module._zip_info(member), content)
    return archive_path


def test_bundle_generation_is_deterministic_and_allowlisted(tmp_path: Path) -> None:
    module = _load_bundle_module()
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    module.build_bundle(ROOT, first)
    module.build_bundle(ROOT, second)

    assert _sha256(first) == _sha256(second)
    with zipfile.ZipFile(first) as archive:
        members = archive.infolist()
        assert [item.filename for item in members] == list(module.ALLOWLIST)
        assert len({item.filename for item in members}) == len(members)
        assert all(item.date_time == module.ZIP_TIMESTAMP for item in members)
        assert all((item.external_attr >> 16) == (stat.S_IFREG | 0o644) for item in members)
        assert all(archive.read(item) == (ROOT / item.filename).read_bytes() for item in members)


def test_bundle_rejects_symlinked_allowlisted_source(tmp_path: Path) -> None:
    module = _load_bundle_module()
    source = tmp_path / "source.txt"
    source.write_text("safe", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(source)

    with pytest.raises(ValueError, match="symlink"):
        module.validate_source_file(tmp_path, Path("link.txt"))


def test_bundle_rejects_allowlisted_source_below_symlinked_directory(tmp_path: Path) -> None:
    module = _load_bundle_module()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "source.txt").write_text("safe", encoding="utf-8")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        module.validate_source_file(tmp_path, Path("linked/source.txt"))


def test_bundle_allowlist_has_no_forbidden_local_or_secret_paths() -> None:
    module = _load_bundle_module()

    assert not [path for path in module.ALLOWLIST if module.is_forbidden_path(Path(path))]
    assert "custom_components/radar_hail_risk/manifest.json" in module.ALLOWLIST
    assert "blueprints/automation/radar_hail_risk/hail_risk_notification.yaml" in module.ALLOWLIST
    assert "examples/lovelace/native-card.yaml" in module.ALLOWLIST
    assert "docs/colleague-test-checklist.md" in module.ALLOWLIST
    assert "LICENSE" in module.ALLOWLIST


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        ".github/workflows/validate.yml",
        ".env",
        ".env.production",
        ".storage/core.config_entries",
        "configuration.yaml",
        "secrets.yaml",
        "dist/old.zip",
        "custom_components/radar_hail_risk/__pycache__/const.pyc",
        "observations/events.json",
        "research/dataset.csv",
        "private-token.txt",
        "credentials/api.json",
        "private-key/id_rsa.txt",
        "private_key/id_rsa.txt",
        "privatekey/id_rsa.txt",
        "home-assistant_v2.db",
        "home-assistant_v2.db-journal",
        "home-assistant_v2.db-wal",
        "home-assistant_v2.db-shm",
        "home-assistant.log.1",
        "server.key",
    ],
)
def test_forbidden_path_scan_covers_local_secret_and_generated_inputs(path: str) -> None:
    module = _load_bundle_module()

    assert module.is_forbidden_path(Path(path))


def test_archive_verifier_rejects_path_traversal(tmp_path: Path) -> None:
    module = _load_bundle_module()
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../configuration.yaml", b"unsafe")

    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(ValueError, match="unsafe member"):
            module._safe_members(archive)


def test_archive_verifier_rejects_duplicate_members(tmp_path: Path) -> None:
    module = _load_bundle_module()
    archive_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("README.md", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("README.md", b"second")

    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(ValueError, match="duplicate members"):
            module._safe_members(archive)


def test_archive_verifier_rejects_unexpected_members(tmp_path: Path) -> None:
    module = _load_bundle_module()
    archive_path = tmp_path / "unexpected.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("README.md", b"incomplete")

    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(ValueError, match="allowlist"):
            module._safe_members(archive)


def test_clean_room_verification_checks_layout_and_parses_assets(tmp_path: Path) -> None:
    module = _load_bundle_module()
    output = tmp_path / "bundle.zip"
    module.build_bundle(ROOT, output)

    report = module.verify_bundle(output)

    assert report["members"] == len(module.ALLOWLIST)
    assert report["integration_modules_compiled"] >= 10
    assert report["javascript_syntax_checked"] is True
    assert report["yaml_assets_parsed"] == 5
    assert report["clean_room_layout"] == "config/custom_components/radar_hail_risk"
    assert report["manifest_domain"] == "radar_hail_risk"
    assert report["hacs_minimum_home_assistant"] == "2024.10.0"


def test_clean_room_rejects_invalid_blueprint_yaml_with_required_markers(tmp_path: Path) -> None:
    module = _load_bundle_module()
    archive_path = _archive_with_replacement(
        module,
        tmp_path,
        "blueprints/automation/radar_hail_risk/hail_risk_notification.yaml",
        b"blueprint:\n  domain: automation\n  input: !input risk_sensor\nbroken: [\n",
    )

    with pytest.raises(ValueError, match="invalid YAML syntax"):
        module.verify_bundle(archive_path)


def test_clean_room_rejects_invalid_example_yaml_with_required_marker(tmp_path: Path) -> None:
    module = _load_bundle_module()
    archive_path = _archive_with_replacement(
        module,
        tmp_path,
        "examples/lovelace/native-card.yaml",
        b"type: entities\nentities: [\n",
    )

    with pytest.raises(ValueError, match="invalid YAML syntax"):
        module.verify_bundle(archive_path)


def test_clean_room_rejects_invalid_javascript_with_registration_marker(tmp_path: Path) -> None:
    module = _load_bundle_module()
    archive_path = _archive_with_replacement(
        module,
        tmp_path,
        "custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js",
        b"customElements.define('radar-hail-risk-card', RadarHailRiskCard);\nconst broken = {;\n",
    )

    with pytest.raises(ValueError, match="invalid JavaScript syntax"):
        module.verify_bundle(archive_path)


def test_cli_prints_archive_path_and_sha256(tmp_path: Path) -> None:
    output = tmp_path / "bundle.zip"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    digest = _sha256(output)
    assert str(output) in result.stdout
    assert f"SHA-256: {digest}" in result.stdout
    assert "Clean-room verification: passed" in result.stdout


def test_colleague_checklist_covers_required_handoff_paths() -> None:
    checklist = (ROOT / "docs" / "colleague-test-checklist.md").read_text(encoding="utf-8")

    required = [
        "2024.10.0",
        "private HACS custom repository",
        "manual archive install",
        "zone.home",
        "radar-only",
        "Blitzortung",
        "sensor.radar_hail_risk_level",
        "hail_risk_notification.yaml",
        "lightning-only",
        "stale",
        "restart",
        "upgrade",
        "rollback",
        "uninstall",
        "RainViewer",
        "not an official warning source",
        "safety-critical",
    ]
    missing = [text for text in required if text.lower() not in checklist.lower()]
    assert not missing, f"Missing colleague checklist topics: {missing}"

    manifest = json.loads(
        (ROOT / "custom_components" / "radar_hail_risk" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == "2024.10.0"
    assert manifest["domain"] == "radar_hail_risk"


def test_current_simple_rc_docs_make_manual_archive_the_only_install_route() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "colleague-test-checklist.md").read_text(encoding="utf-8")

    for document in (readme, checklist):
        normalized = document.lower()
        assert "only valid current install/test route for this unpushed rc" in normalized
        assert "checksum-verified manual archive" in normalized
        assert "separately authorized publication" in normalized
        assert "exact reviewed source and sha-256" in normalized

    assert "Quick start with a HACS custom repository" not in readme
    assert "Choose one path." not in checklist
    assert "Conditional future HACS route (not currently authorized)" in readme
    assert "Conditional HACS route (not currently authorized)" in checklist


def test_upgrade_and_rollback_preserve_config_entry_and_replace_complete_directory() -> None:
    checklist = (ROOT / "docs" / "colleague-test-checklist.md").read_text(encoding="utf-8")
    upgrade = checklist.split("## Upgrade", 1)[1].split("## Rollback", 1)[0]
    rollback = checklist.split("## Rollback", 1)[1].split("## Uninstall", 1)[0]
    uninstall = checklist.split("## Uninstall", 1)[1].split(
        "## Privacy, sources, and limitations", 1
    )[0]

    for section in (upgrade, rollback):
        assert "existing config entry" in section
        assert "entry ID" in section or "entry-ID-derived" in section
        assert "entire `<HA config>/custom_components/radar_hail_risk/` directory" in section
        assert "overlay-copy" in section
    assert "do not remove and recreate it" in upgrade
    assert "Removing it loses saved options" in rollback
    assert "Remove the Radar Hail Risk config entry" not in rollback
    assert "Remove the Radar Hail Risk config entry" in uninstall
    assert "Config-entry removal is for uninstall only" in uninstall
