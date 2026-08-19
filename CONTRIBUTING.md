# Contributing to Storm Detector

Thank you for helping improve Storm Detector.

## Before opening a change

- Search existing issues and pull requests.
- Use an issue first for broad product changes, public identifier changes, new external services, or behavior that can affect alerts.
- Never commit Home Assistant tokens, exact home coordinates, private entity IDs, downloaded diagnostics, or user data.
- Keep Storm Detector's safety language intact: hail is radar-supported possibility, not confirmed ground truth or an official warning.

## Development setup

Storm Detector supports Python 3.10+ for dependency-light development. Its release CI also runs pinned real-Home-Assistant stacks.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run the local gate:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m compileall -q custom_components tests
```

Home Assistant lifecycle changes must also pass both locked HA lanes in CI. Do not weaken or skip the minimum/current HA jobs to make a change pass.

## Pull requests

1. Create a focused branch from the latest `main`.
2. Add or update tests for behavior changes.
3. Update user-facing documentation and both translations when applicable.
4. Run the local gate and check `git diff --check`.
5. Open a pull request using the repository template.
6. Address review findings and require all HACS, Hassfest, dependency-light, and real-HA checks to pass.

Do not bump the integration version or create release tags in an ordinary feature pull request unless the change is specifically a release preparation.

## Public contracts

Treat these as compatibility-sensitive:

- integration domain and entity IDs;
- config-entry and options keys;
- `evidence_kind`, level values, and documented attributes;
- custom card tag and resource URL;
- blueprint path and inputs.

Discuss breaking changes before implementation and provide an explicit migration path.
