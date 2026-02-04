# Lasso Developer Guide

This guide is for contributors and advanced users who need to run the stack
manually or work on individual components. For normal usage, prefer the `lasso`
CLI and the user guide in `docs/guide/`.

## Manual compose (legacy/advanced)
### Interactive mode (Codex)
Requires `~/.codex/auth.json` and `~/.codex/skills` on the host.
```bash
docker compose -f compose.yml -f compose.codex.yml up -d --build agent collector

docker compose -f compose.yml -f compose.codex.yml run --rm \
  -e HARNESS_MODE=tui harness
```
The harness connects to the `agent` service over SSH; the collector must be
running to emit audit/eBPF logs. `docker compose run` does not start
dependencies. The default TUI command uses `/work` and disables Codex
sandboxing (`codex -C /work -s danger-full-access`); override via
`HARNESS_TUI_CMD`.

### Non-interactive mode (Codex)
Requires `~/.codex/auth.json` and `~/.codex/skills` on the host.
```bash
export HARNESS_API_TOKEN=dev-token
docker compose -f compose.yml -f compose.codex.yml up -d --build collector agent harness

curl -s -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"say hello"}' \
  http://127.0.0.1:8081/run
```
The harness runs in server mode when stdin is not a TTY; use
`HARNESS_MODE=server` to force it.

### Interactive mode (no Codex; plain shell)
```bash
docker compose -f compose.yml up -d --build agent collector

docker compose -f compose.yml run --rm \
  -e HARNESS_MODE=tui \
  -e "HARNESS_TUI_CMD=bash -l" \
  harness
```

### Log viewer UI
```bash
docker compose -f compose.ui.yml up -d --build ui
```
The UI reads from `${LASSO_LOG_ROOT:-./logs}` and binds to
`http://127.0.0.1:8090`.

## Compose files
- `compose.yml`: base stack (agent-agnostic).
- `compose.codex.yml`: adds host Codex auth + skills mounts for the agent container.
- `compose.ui.yml`: UI-only service that mounts `./logs` read-only.

## Testing and examples
- `docs/dev/TESTING.md`: integration tests and filter test cases.
- `docs/dev/EXAMPLE_FLOW.md`: end-to-end example walkthroughs.
