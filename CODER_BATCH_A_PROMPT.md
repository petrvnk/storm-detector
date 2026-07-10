You are the Coding Mind implementing Batch A in /home/jarvis/projects/radar-hail-risk on branch feat/production-hardening-a.

Read first:
- docs/plans/2026-07-09-production-hardening.md
- custom_components/radar_hail_risk/rainviewer.py
- custom_components/radar_hail_risk/risk.py
- custom_components/radar_hail_risk/coordinator.py
- custom_components/radar_hail_risk/const.py
- custom_components/radar_hail_risk/config_flow.py
- tests/test_rainviewer_stage3.py
- tests/test_stage5_coordinator_entities.py
- tests/test_stage6_resilience.py

Implement ONLY Batch A: radar pipeline correctness.

Required behavior:
1. Follow TDD. Add tests that fail for the current implementation before changing production code.
2. Configured watch/warning/urgent dBZ thresholds must drive actual connected-core detection and risk classification. Non-default thresholds must be covered.
3. Preserve fixed 50/55/60 diagnostic attributes if practical for compatibility, but do not use them as substitutes for configured thresholds. Add explicit generic configured-threshold results/attributes if needed.
4. Build connected components globally across all successfully downloaded tiles in a frame. A core split across x=511/x=0 of adjacent tiles must be one component with correct pixel count/area/core_count.
5. Add bounded option min_core_pixels (or an equivalently clear minimum-area option), centralize default/range in const.py, expose it in config/options flow and translations. Choose a safe default that rejects isolated one-pixel noise. Ensure filtered noise cannot activate risk merely through raw max_dbz fallback; preserve raw maximum only as clearly diagnostic if useful.
6. Valid compact cores must continue to classify correctly. Partial tile failures should remain degraded/partial, not crash.
7. Update README and CHANGELOG.
8. No Batch B/C work, no release/tag/push/deployment, no unrelated refactors.

Verification required:
- Run targeted new tests in RED before implementation and mention the observed failures in your final report.
- Run targeted tests after implementation.
- Run python -m pytest -q
- Run python -m ruff check .
- Run python -m compileall -q .
- Inspect git diff --check and git status.
- Commit all Batch A files locally with a descriptive commit. Do not push.

Be careful about compatibility of existing Lovelace attributes and tests. If you change public attribute names, preserve aliases and document semantics. Final report: tests, files changed, commit SHA, risks or follow-up items.