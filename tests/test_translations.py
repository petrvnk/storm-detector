"""Tests that validate Stage 2 translations payload shape."""

from __future__ import annotations

import json
from pathlib import Path


def test_translations_reference_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "custom_components" / "storm_detector" / "translations" / "en.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert "config" in data
    assert "step" in data["config"]
    assert "user" in data["config"]["step"]
    assert "options" in data
    assert "entity" in data
    assert "services" not in data
