# Testing Guide

This page is a developer quickstart. The canonical testing contract lives in:

- `tests/README.md`
- `tests/test_principles.md`
- `tests/SYNTHETIC_LOGS.md`

If this page and those files disagree, follow `tests/README.md`.

## Canonical Entry Points
Use `uv` for all test commands.

```bash
uv sync --frozen
```

Preferred runner:

```bash
uv run python scripts/all_tests.py --lane fast
uv run python scripts/all_tests.py --lane pr
uv run python scripts/all_tests.py --lane full
uv run python scripts/all_tests.py --lane codex
uv run python scripts/all_tests.py --lane local-full
```

Direct pytest runs:

```bash
uv run pytest tests/unit tests/fixture -q
uv run pytest tests/integration -m "integration and not agent_codex" -q
uv run pytest tests/integration -m agent_codex -q
uv run pytest tests/stress -q
uv run pytest tests/regression -q
```

## Codex Lanes
`agent_codex` tests are local-only because GitHub CI does not have Codex credentials.

Requirements on host:

- `~/.codex/auth.json`
- `~/.codex/skills/`

These lanes validate real agent behavior through:

- non-interactive `exec` path
- interactive TUI path

## Scope Boundaries
- Unit/fixture: deterministic contract checks, including synthetic inputs.
- Integration/regression/stress: live-stack assertions only.
- Offline replay is not acceptance evidence for integration/regression/stress.

## Legacy Scripts
Files under `scripts/run_integration_*.sh` remain useful for manual debugging
and historical reference. They are not the canonical release gate surface.

For CI/local gate policy and required checks, use `tests/README.md`.
