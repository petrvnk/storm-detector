"""Core tests for the Stage 2 skeleton metadata and constants."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_exists_and_has_required_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "custom_components" / "radar_hail_risk" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data["domain"] == "radar_hail_risk"
    assert data["name"] == "Radar Hail Risk"
    assert data.get("config_flow") is True
    assert isinstance(data.get("requirements"), list)
    assert "loggers" in data
