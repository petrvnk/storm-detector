"""Core tests for the Stage 2 skeleton metadata and constants."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_exists_and_has_required_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "custom_components" / "storm_detector" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data["domain"] == "storm_detector"
    assert data["name"] == "Storm Detector"
    assert data["version"] == "0.2.0"
    assert data["documentation"] == "https://github.com/petrvnk/storm-detector"
    assert data["issue_tracker"] == "https://github.com/petrvnk/storm-detector/issues"
    assert data.get("config_flow") is True
    assert data.get("iot_class") == "cloud_polling"
    assert isinstance(data.get("requirements"), list)
    assert "loggers" in data
    assert data["loggers"] == ["custom_components.storm_detector"]
