"""Test existence of Stage 2 scaffold files."""

from __future__ import annotations

from pathlib import Path


def test_scaffold_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = [
        root / "custom_components" / "storm_detector" / "manifest.json",
        root / "hacs.json",
        root / "pyproject.toml",
        root / "requirements-dev.txt",
        root / "custom_components" / "storm_detector" / "const.py",
        root / "custom_components" / "storm_detector" / "__init__.py",
        root / "custom_components" / "storm_detector" / "config_flow.py",
        root / "custom_components" / "storm_detector" / "coordinator.py",
        root / "custom_components" / "storm_detector" / "sensor.py",
        root / "custom_components" / "storm_detector" / "binary_sensor.py",
        root / "custom_components" / "storm_detector" / "device_tracker.py",
        root / "custom_components" / "storm_detector" / "lightning.py",
        root / "custom_components" / "storm_detector" / "rainviewer.py",
        root / "custom_components" / "storm_detector" / "risk.py",
        root / "custom_components" / "storm_detector" / "translations" / "en.json",
        root / "tests" / "test_manifest.py",
        root / "tests" / "test_translations.py",
        root / "tests" / "test_constants.py",
        root / "tests" / "test_scaffold_files.py",
    ]

    missing = [path for path in expected if not path.exists()]
    assert not missing, f"Missing expected files: {[str(item) for item in missing]}"


def test_scaffold_expected_option_defaults() -> None:
    from custom_components.storm_detector import const

    assert isinstance(const.OPTIONAL_CONF_DEFAULTS, dict)
    assert const.OPTIONAL_CONF_DEFAULTS[const.CONF_MIN_ANALYSIS_INTERVAL_SECONDS] == 60


def test_bundled_frontend_uses_storm_detector_static_url() -> None:
    from custom_components import storm_detector

    assert storm_detector._FRONTEND_URL == "/storm_detector"
    assert (storm_detector._FRONTEND_PATH / "storm-detector-card.js").is_file()
