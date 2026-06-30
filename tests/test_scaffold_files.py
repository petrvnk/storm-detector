"""Test existence of Stage 2 scaffold files."""

from __future__ import annotations

from pathlib import Path


def test_scaffold_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = [
        root / "custom_components" / "radar_hail_risk" / "manifest.json",
        root / "hacs.json",
        root / "pyproject.toml",
        root / "requirements-dev.txt",
        root / "custom_components" / "radar_hail_risk" / "const.py",
        root / "custom_components" / "radar_hail_risk" / "__init__.py",
        root / "custom_components" / "radar_hail_risk" / "config_flow.py",
        root / "custom_components" / "radar_hail_risk" / "coordinator.py",
        root / "custom_components" / "radar_hail_risk" / "sensor.py",
        root / "custom_components" / "radar_hail_risk" / "binary_sensor.py",
        root / "custom_components" / "radar_hail_risk" / "device_tracker.py",
        root / "custom_components" / "radar_hail_risk" / "lightning.py",
        root / "custom_components" / "radar_hail_risk" / "rainviewer.py",
        root / "custom_components" / "radar_hail_risk" / "risk.py",
        root / "custom_components" / "radar_hail_risk" / "translations" / "en.json",
        root / "tests" / "test_manifest.py",
        root / "tests" / "test_translations.py",
        root / "tests" / "test_constants.py",
        root / "tests" / "test_scaffold_files.py",
    ]

    missing = [path for path in expected if not path.exists()]
    assert not missing, f"Missing expected files: {[str(item) for item in missing]}"


def test_scaffold_expected_option_defaults() -> None:
    from custom_components.radar_hail_risk import const

    assert isinstance(const.OPTIONAL_CONF_DEFAULTS, dict)
    assert const.OPTIONAL_CONF_DEFAULTS[const.CONF_MIN_ANALYSIS_INTERVAL_SECONDS] == 60
