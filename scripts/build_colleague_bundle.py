#!/usr/bin/env python3
"""Build and verify the deterministic private colleague-test archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import yaml
from yaml.nodes import ScalarNode

ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
ZIP_MODE = stat.S_IFREG | 0o644

# Deliberately explicit: every new member requires a reviewed source change here.
ALLOWLIST = tuple(
    sorted(
        (
            "CHANGELOG.md",
            "LICENSE",
            "README.md",
            "blueprints/automation/radar_hail_risk/hail_risk_notification.yaml",
            "custom_components/radar_hail_risk/__init__.py",
            "custom_components/radar_hail_risk/async_utils.py",
            "custom_components/radar_hail_risk/binary_sensor.py",
            "custom_components/radar_hail_risk/brand/icon.png",
            "custom_components/radar_hail_risk/config_flow.py",
            "custom_components/radar_hail_risk/const.py",
            "custom_components/radar_hail_risk/coordinator.py",
            "custom_components/radar_hail_risk/device_tracker.py",
            "custom_components/radar_hail_risk/diagnostics.py",
            "custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js",
            "custom_components/radar_hail_risk/ha_fallback.py",
            "custom_components/radar_hail_risk/lightning.py",
            "custom_components/radar_hail_risk/manifest.json",
            "custom_components/radar_hail_risk/rainviewer.py",
            "custom_components/radar_hail_risk/risk.py",
            "custom_components/radar_hail_risk/sensor.py",
            "custom_components/radar_hail_risk/translations/en.json",
            "docs/colleague-test-checklist.md",
            "docs/release-checklist.md",
            "examples/lovelace/mushroom-card.yaml",
            "examples/lovelace/native-card.yaml",
            "examples/lovelace/weather-tab.yaml",
            "examples/radar-hail-risk-card.yaml",
            "hacs.json",
        )
    )
)

_FORBIDDEN_PARTS = {
    ".git",
    ".github",
    ".storage",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "observations",
    "recorder",
    "research",
    "venv",
}
_FORBIDDEN_NAMES = {
    ".ha_version",
    "automations.yaml",
    "configuration.yaml",
    "home-assistant.log",
    "home-assistant_v2.db",
    "scenes.yaml",
    "scripts.yaml",
    "secrets.yaml",
}
_SECRET_WORDS = ("credential", "privatekey", "secret", "token")
_SECRET_SUFFIXES = (".key", ".log", ".pem", ".pyc")
_HOME_ASSISTANT_DB_NAMES = {
    "home-assistant_v2.db",
    "home-assistant_v2.db-journal",
    "home-assistant_v2.db-shm",
    "home-assistant_v2.db-wal",
}


class _HomeAssistantSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that recognizes Home Assistant blueprint inputs."""


def _construct_input(loader: yaml.SafeLoader, node: ScalarNode) -> str:
    """Construct a scalar Home Assistant !input reference without resolving it."""
    return loader.construct_scalar(node)


_HomeAssistantSafeLoader.add_constructor("!input", _construct_input)


def is_forbidden_path(path: Path) -> bool:
    """Return whether a candidate is local/generated/secret-like and never bundle-safe."""
    parts = tuple(part.lower() for part in path.parts)
    normalized_parts = tuple(part.replace("-", "").replace("_", "") for part in parts)
    name = path.name.lower()
    return (
        any(part in _FORBIDDEN_PARTS for part in parts)
        or name in _FORBIDDEN_NAMES
        or name in _HOME_ASSISTANT_DB_NAMES
        or name.startswith("home-assistant.log.")
        or name == ".env"
        or name.startswith(".env.")
        or name.endswith(_SECRET_SUFFIXES)
        or any(word in part for part in normalized_parts for word in _SECRET_WORDS)
    )


def validate_source_file(root: Path, relative: Path) -> Path:
    """Validate one allowlisted regular file without following symlinks."""
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe allowlist path: {relative}")
    if is_forbidden_path(relative):
        raise ValueError(f"forbidden allowlist path: {relative}")
    source = root
    for part in relative.parts:
        source /= part
        if source.is_symlink():
            raise ValueError(f"allowlisted source uses a symlink: {relative}")
    if not source.exists():
        raise FileNotFoundError(f"missing allowlisted source: {relative}")
    if not source.is_file():
        raise ValueError(f"allowlisted source is not a regular file: {relative}")
    return source


def _zip_info(member: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(member, ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ZIP_MODE << 16
    info.flag_bits = 0
    return info


def build_bundle(root: Path, output: Path) -> str:
    """Write a deterministic archive from the reviewed explicit allowlist."""
    root = root.resolve()
    if tuple(sorted(ALLOWLIST)) != ALLOWLIST or len(set(ALLOWLIST)) != len(ALLOWLIST):
        raise ValueError("ALLOWLIST must be unique and sorted by POSIX path")

    sources = [(member, validate_source_file(root, Path(member))) for member in ALLOWLIST]
    output = output if output.is_absolute() else root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError(f"output must not be a symlink: {output}")

    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=False) as archive:
            for member, source in sources:
                archive.writestr(_zip_info(member), source.read_bytes(), compresslevel=9)
        verify_bundle(temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("archive contains duplicate members")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"archive contains unsafe member: {name}")
        if is_forbidden_path(Path(*path.parts)):
            raise ValueError(f"archive contains forbidden member: {name}")
    if names != list(ALLOWLIST):
        raise ValueError("archive members do not exactly match the reviewed allowlist")
    return infos


def _validate_yaml_asset(path: Path, required_markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    if "\t" in text or not text.endswith("\n"):
        raise ValueError(f"invalid YAML formatting: {path}")
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise ValueError(f"missing required YAML fields in {path}: {missing}")
    try:
        yaml.load(text, Loader=_HomeAssistantSafeLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML syntax: {path}") from error


def _validate_javascript_asset(path: Path) -> None:
    """Syntax-check JavaScript using the locally available Node.js parser."""
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js is required to syntax-check bundled JavaScript")
    result = subprocess.run(
        [node, "--check", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"invalid JavaScript syntax: {path}: {detail}")


def verify_bundle(archive_path: Path) -> dict[str, object]:
    """Verify extraction, HACS metadata, assets, and a clean temporary HA layout."""
    with tempfile.TemporaryDirectory(prefix="radar-hail-risk-clean-room-") as temp_name:
        temp = Path(temp_name)
        extracted = temp / "extracted"
        extracted.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            infos = _safe_members(archive)
            for info in infos:
                target = extracted / Path(*PurePosixPath(info.filename).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))

        extracted_files = sorted(
            path.relative_to(extracted).as_posix() for path in extracted.rglob("*") if path.is_file()
        )
        if extracted_files != list(ALLOWLIST):
            raise ValueError("clean-room extracted tree does not match the allowlist")

        manifest = json.loads(
            (extracted / "custom_components/radar_hail_risk/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        hacs = json.loads((extracted / "hacs.json").read_text(encoding="utf-8"))
        if manifest.get("domain") != "radar_hail_risk" or manifest.get("config_flow") is not True:
            raise ValueError("integration manifest domain/config_flow is invalid")
        if manifest.get("iot_class") != "cloud_polling":
            raise ValueError("integration manifest must declare cloud_polling")
        if hacs.get("content_in_root") is not False or not hacs.get("homeassistant"):
            raise ValueError("hacs.json layout/minimum Home Assistant metadata is invalid")

        blueprint = extracted / ALLOWLIST[
            ALLOWLIST.index(
                "blueprints/automation/radar_hail_risk/hail_risk_notification.yaml"
            )
        ]
        _validate_yaml_asset(blueprint, ("blueprint:", "domain: automation", "!input"))
        for relative in (
            "examples/lovelace/mushroom-card.yaml",
            "examples/lovelace/native-card.yaml",
            "examples/lovelace/weather-tab.yaml",
            "examples/radar-hail-risk-card.yaml",
        ):
            _validate_yaml_asset(extracted / relative, ("type:",))

        source_integration = extracted / "custom_components/radar_hail_risk"
        clean_integration = temp / "config/custom_components/radar_hail_risk"
        shutil.copytree(source_integration, clean_integration)
        required_modules = {"__init__.py", "config_flow.py", "coordinator.py", "sensor.py"}
        present_modules = {path.name for path in clean_integration.glob("*.py")}
        if not required_modules <= present_modules:
            raise ValueError("clean-room integration is missing required Python modules")

        compiled = 0
        for source in sorted(clean_integration.glob("*.py")):
            compile(source.read_bytes(), source.as_posix(), "exec")
            compiled += 1
        json.loads((clean_integration / "translations/en.json").read_text(encoding="utf-8"))
        json.loads((clean_integration / "manifest.json").read_text(encoding="utf-8"))
        card_asset = clean_integration / "frontend/radar-hail-risk-card.js"
        if not card_asset.is_file():
            raise ValueError("clean-room integration is missing its bundled card asset")
        _validate_javascript_asset(card_asset)

        return {
            "members": len(infos),
            "integration_modules_compiled": compiled,
            "javascript_syntax_checked": True,
            "yaml_assets_parsed": 5,
            "clean_room_layout": "config/custom_components/radar_hail_risk",
            "manifest_domain": manifest["domain"],
            "hacs_minimum_home_assistant": hacs["homeassistant"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    digest = build_bundle(root, output)
    report = verify_bundle(output)
    print(f"Archive: {output}")
    print(f"SHA-256: {digest}")
    print(
        "Clean-room verification: passed "
        f"({report['members']} members, {report['integration_modules_compiled']} Python modules)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
