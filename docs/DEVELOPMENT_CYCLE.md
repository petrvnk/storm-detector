# Development Cycle

## Kanban board

Project work is tracked on the Hermes Kanban board `storm-detector`.

```bash
hermes kanban --board storm-detector list
hermes kanban --board storm-detector stats
hermes kanban --board storm-detector assignees
```

## Agent routing

| Work type | Owner | Model |
|---|---|---|
| Orchestration, prioritization, final controller gate | `default` | `gpt-5.6-sol` |
| Small explicit low-risk coding tasks | `jarvis-coder-junior` | `gpt-5.3-codex-spark` |
| Complex implementation and difficult repairs | `jarvis-coder` | `gpt-5.6-sol` |
| Task-compliance and code-quality review | `jarvis-reviewer` | `gpt-5.6-sol` |

Use the junior for focused tests, lint/type fixes, documentation, translations, mechanical refactors, and isolated deterministic bug fixes. Escalate after one failed implementation-and-test cycle or immediately when architecture, security, migrations, concurrency redesign, production operations, or broad cross-subsystem changes are involved.

## Required state machine

```text
implementation card (blocked or dependency-waiting)
  -> explicit controller authorization / dependency resolution
  -> coder candidate result
  -> controller reruns tests/lint/build and inspects diff
  -> card enters `review` while queued for jarvis-reviewer
  -> dispatcher claims it and changes status `review` -> `running`
  -> reviewer APPROVE or REQUEST_CHANGES
  -> controller closes the card or creates a bounded repair card
  -> next dependent implementation may be promoted
```

Future implementation cards wait in `todo` behind parent dependencies, so they are not dispatchable. Manual blocks are used for human/capability gates. The built-in `jarvis-review-router` reuses the coder card for review; do not create duplicate review cards for normal coder work. The dashboard's `review` column therefore contains reviews waiting to be claimed. Once a reviewer actively claims a review, the task appears under `running`/In Progress until the verdict. This preserves the complete coder/reviewer history on one card while preventing premature downstream dispatch.

## Mandatory verification gate

A coding agent's report is not proof of completion. Before closing an implementation card, the controller must independently verify:

1. task acceptance criteria against the actual diff;
2. targeted regression tests;
3. full project test suite;
4. lint/static checks configured by the project;
5. syntax/compile checks where applicable;
6. `git diff --check` and working-tree scope;
7. no push, release, deployment, or production mutation unless explicitly approved.

Behavioral changes then require an independent `jarvis-reviewer` verdict. `REQUEST_CHANGES` returns the same batch to the appropriate coder; it does not unblock dependent work.

## Parallel work

Never run multiple writing agents in the same mutable checkout. Parallel tasks require isolated git worktrees and explicit non-overlapping scopes. Read-only reviewers may inspect the implementation checkout but must not modify it.

## Active hardening chain

| Stage | Card | Owner | Current state |
|---|---|---|---|
| Batch A original implementation/audit history | `t_2840684b` | `jarvis-coder` / reviewer history | blocked, superseded after `REQUEST_CHANGES` |
| Batch A bounded reviewer fixes | `t_fa13251f` | `jarvis-coder` → automatic reviewer routing | running |
| Batch B implementation | `t_75a8b848` | `jarvis-coder` | dependency-waiting `todo` |
| Batch C implementation | `t_82a566c3` | `jarvis-coder` | dependency-waiting `todo` |
| Observation/ground-truth pilot | `t_9d223d60` | `default` | dependency-waiting `todo` |
| Pilot plan review | `t_58885a72` | `jarvis-reviewer` | blocked |

## Junior utilization quality checks

Track whether Spark-backed junior tasks actually save senior time:

- first-pass green rate;
- reviewer findings per task;
- patches accepted without senior rewrite;
- controller/reviewer effort;
- escalation and regression rates.

Do not create low-value churn merely to consume budget. Narrow the junior scope if review cost approaches the cost of direct senior implementation.
