# Radar Hail Risk — Simple RC autonomous controller tick

Act as controller for Kanban board `radar-hail-risk` and repository `/home/jarvis/projects/radar-hail-risk`.

Petr authorized autonomous continuation only through the bounded **Simple RC** chain:

- completed S0 planning history preserved in the archived corrupt board and worker logs
- S0R3 final repaired-plan review `t_583ecdf9`
- S1 stabilization `t_7704adef`
- S2 warning semantics `t_1c38e29f`
- S3 setup/entity UX simplification `t_63f719a9`
- S4 colleague test bundle `t_a9ada5e8`
- S5 independent RC review `t_30ac3b29`
- S6 controller verification/handoff `t_41a5ffde`
- narrowly linked repair/re-review cards created within this scope

This is one event-driven controller tick, not a polling loop. Inspect the live board, relevant task show/runs/log, Git status/diff and active workers. Take every immediately safe transition needed, then stop when a worker is active or a real blocker requires Petr.

## Product boundary

The target is a simple, stable Home Assistant integration for one location using RainViewer radar and optional Blitzortung, shareable locally with one colleague for testing. Preserve stale/unavailable safety, timeout/concurrency hardening, tracking/hysteresis and compatibility where practical.

Do not implement a global dataset, observation recorder, research platform, Open-Meteo integration, production deployment, push, public release, HACS publication or scope expansion.

## Required workflow

- Never run two writers in the shared checkout.
- S0 planning and its narrow repairs are already complete. S1 may proceed only after explicit S0R3 approval of the repaired plan.
- For S1-S4 implementation completion or `review-required`, independently inspect exact Git status/diff and verify before routing read-only review.
- Code verification requires, unless a narrower docs-only repair is explicitly justified:
  - `uv run --isolated --python 3.14 --extra dev pytest -q`
  - `uv run --isolated --python 3.14 --extra dev ruff check .`
  - `uv run --isolated --python 3.10 --extra dev pytest -q`
  - `uv run --isolated --python 3.10 --extra dev python -m compileall -q custom_components tests`
  - `git diff --check`
- Record exact verification evidence on the card. Checks alone are not reportable actions.
- Route independent review to `jarvis-reviewer`; reviewer is read-only.
- `APPROVE` advances. `APPROVE_WITH_COMMENTS` advances only when findings are explicitly non-blocking.
- On `REQUEST_CHANGES`, create a narrow linked repair card assigned to `jarvis-coder`, keep downstream work dependency-blocked, verify the repair and re-review.
- Inspect crashes/timeouts before retrying. With `max_retries=1`, failed workers should remain blocked for deliberate recovery rather than retry loops.
- S5 must independently approve the complete RC. S6 then performs final controller verification and writes the exact artifact path, SHA-256, installation/rollback steps and limitations into its result/handoff artifact.
- Never push, merge, tag, publish, deploy, mutate production Home Assistant, or expose a public tunnel.
- Subscribe newly created/activated Simple RC cards to the authorized Telegram topic if not already subscribed.

## Reporting contract

Write `/tmp/radar-hail-risk-simple-rc-autopilot-report.md` using `write_file`.

Write a concise Czech report **only if this tick actually performs a user-relevant action** such as creating/routing/assigning/blocking/unblocking/completing a card, dispatching a worker, creating a repair, or changing workflow state.

Use this Telegram-friendly structure (omit a row only when genuinely irrelevant):

```markdown
## <emoji> Simple RC · <short stage/outcome>

**Provedeno:** <the concrete action performed, outcome first>
**Důvod:** <why it was needed; include the reviewer finding/blocker in plain Czech>
**Aktuálně:** <active stage, owner and task ID; say explicitly what is waiting>
**Ověření:** <exact tests/verdict only when relevant to the action>
**Další krok:** <one precise transition that should happen next>
```

Choose one meaningful heading icon: `🚀` dispatched/started, `🔧` repair created, `✅` approved/completed, `⚠️` finding/recoverable blocker, `⛔` human blocker, `📦` handoff artifact ready. Keep the stage/outcome human-readable; task IDs belong in the detail rows, not as the headline. Prefer one compact sentence per row, bold labels and at most two short bullets when one sentence cannot carry the information. Never emit raw log prose, a chronological diary, repeated background context, generic phrases such as „pokračuji“, or more than 8 non-empty lines.

Information priority is: action and result → why it matters → current owner/waiting gate → exact next step. Verification data are supporting evidence, not the headline.

Reads, status polling, Git inspection, test/lint/compile runs, verification comments, discovering a verdict, unchanged blockers, startup, heartbeat and observing a running worker are checks, not actions. For those write an empty file. Verification results may appear only as context for a real action in the same tick.

Do not rely on your final chat response for delivery; the watcher action-gates and delivers the report.