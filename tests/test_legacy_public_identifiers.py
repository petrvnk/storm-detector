"""Reject legacy product identifiers from active public repository surfaces."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = (
    "Radar Hail Risk",
    "radar-hail-risk",
    "radar_hail_risk",
    "custom:radar-hail-risk-card",
    "/radar_hail_risk/radar-hail-risk-card.js",
    "blueprints/automation/radar_hail_risk/hail_risk_notification.yaml",
    "hail_risk_notification.yaml",
    "tag: radar_hail_risk",
)

HISTORICAL_ALLOWLIST = {
    Path("docs/plans/2026-07-10-s1-stabilization-note.md"),
    Path("docs/plans/2026-07-10-simple-shareable-rc.md"),
    Path("docs/plans/2026-07-14-live-radar-overlay-architecture.md"),
    Path("docs/plans/2026-07-09-production-hardening.md"),
    Path("docs/plans/AUTOPILOT_CONTROLLER_TICK.md"),
    Path("docs/plans/SIMPLE_RC_AUTOPILOT_CONTROLLER_TICK.md"),
    Path("docs/plans/live-radar-overlay/UI_ARCHITECTURE.md"),
    Path("docs/plans/live-radar-overlay/UX_SPEC.md"),
}


def _tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def test_active_tracked_files_have_no_legacy_public_identifiers() -> None:
    violations: list[str] = []
    for relative in _tracked_files():
        if relative == Path(__file__).relative_to(ROOT) or relative in HISTORICAL_ALLOWLIST:
            continue
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for forbidden in FORBIDDEN:
            if forbidden in text:
                violations.append(f"{relative}: {forbidden}")

    assert not violations, "Legacy public identifiers remain:\n" + "\n".join(violations)