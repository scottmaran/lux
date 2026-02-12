# Lasso Developer Guide

This guide is for contributors and advanced users who need to run the stack
manually or work on individual components. For normal usage, prefer the `lasso`
CLI and the user guide in `docs/guide/`.

## Manual compose (advanced)
### Prerequisites
- Docker Desktop (or Docker Engine) running.
- `~/.config/lasso/compose.env` present (generated via `lasso config apply`).
- For Codex modes: `~/.codex/auth.json` and `~/.codex/skills` on the host.

### Local image + run setup (required for consistent run-scoped logs)
Run once per terminal session:

```bash
set -a
source ~/.config/lasso/compose.env
set +a

export LASSO_VERSION=local
export LASSO_RUN_ID="lasso__$(date +%Y_%m_%d_%H_%M_%S)"

mkdir -p "$LASSO_LOG_ROOT/$LASSO_RUN_ID"
printf '{\n  "run_id": "%s",\n  "started_at": "%s"\n}\n' \
  "$LASSO_RUN_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$LASSO_LOG_ROOT/.active_run.json"
```

Build local images tagged as `:local`:

```bash
docker build -t ghcr.io/scottmaran/lasso-collector:local ./collector
docker build -t ghcr.io/scottmaran/lasso-agent:local ./agent
docker build -t ghcr.io/scottmaran/lasso-harness:local ./harness
docker build -t ghcr.io/scottmaran/lasso-ui:local ./ui
```

Important:
- Keep `LASSO_RUN_ID` constant across all compose commands for the same run.
- If `LASSO_RUN_ID` is unset, compose defaults to `lasso__adhoc`, which can split collector and harness outputs into different directories.

### Start collector + agent + UI

```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml -f compose.ui.yml \
  down --remove-orphans

docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml -f compose.ui.yml \
  up -d --pull never collector agent ui
```

The UI binds to `http://127.0.0.1:8090`.

### Interactive mode (Codex TUI)
Launch one session:

```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml \
  run --rm -e HARNESS_MODE=tui -e HARNESS_TUI_NAME=manual_session_1 harness
```

Launch concurrent sessions:
- Open a second terminal.
- Repeat env setup (`source ~/.config/lasso/compose.env`, `export LASSO_VERSION=local`, same `LASSO_RUN_ID`).
- Run a second `docker compose ... run --rm ... harness` command with a different `HARNESS_TUI_NAME`.

The harness connects to the `agent` service over SSH. `docker compose run` does not start dependencies.
The default TUI command is `codex -C /work -s danger-full-access`; override via `HARNESS_TUI_CMD`.

### Non-interactive mode (Codex server jobs)
Start harness server and submit a job:

```bash
export HARNESS_API_TOKEN=dev-token

docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml \
  up -d --pull never harness

curl -s -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"say hello"}' \
  http://127.0.0.1:8081/run
```

### Interactive mode (no Codex; plain shell)

```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml \
  up -d --pull never agent collector

docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml \
  run --rm -e HARNESS_MODE=tui -e "HARNESS_TUI_CMD=bash -l" harness
```

### Teardown

```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml -f compose.ui.yml \
  down --remove-orphans
```

### Troubleshooting manual compose
- Symptom: UI shows no runs or timeline rows.
  Check that `http://127.0.0.1:8090/api/runs` reports a valid `active_run_id`, or pass `run_id` explicitly in API queries.
- Symptom: collector files are under one run directory but harness sessions are under another (often `lasso__adhoc`).
  Cause: `LASSO_RUN_ID` was not exported consistently across terminals/commands.
- Quick verification:
  `find "$LASSO_LOG_ROOT/$LASSO_RUN_ID" -maxdepth 5 -print | sort`

## Compose files
- `compose.yml`: base stack (agent-agnostic).
- `compose.codex.yml`: adds host Codex auth + skills mounts for the agent container.
- `compose.ui.yml`: UI-only service that mounts `${LASSO_LOG_ROOT}` for read-only log reads and label writes.

## Testing and examples
- `tests/README.md`: canonical test architecture, required gates, and commands.
- `tests/test_principles.md`: concise statement of testing invariants.
- `tests/SYNTHETIC_LOGS.md`: synthetic data scope, fidelity status, and constraints.
- `docs/dev/EXAMPLE_FLOW.md`: illustrative walkthrough (not a normative test contract).

Canonical local/CI test gating is:

```bash
uv run python scripts/all_tests.py --lane <fast|pr|full|codex|local-full>
```
