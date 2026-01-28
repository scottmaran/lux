# Agent Harness

Containerized harness + agent + collector stack for auditing agent activity inside a VM.

## Compose files
- `compose.yml`: base stack (agent-agnostic).
- `compose.codex.yml`: adds host Codex auth + skills mounts for the agent container.

## Integration tests
### Stub (no Codex required)
```bash
export HARNESS_API_TOKEN=dev-token
export HARNESS_RUN_CMD_TEMPLATE='echo stub-ok'
./scripts/run_integration_stub.sh
```

### Codex
Requires `~/.codex/auth.json` and `~/.codex/skills` on the host.
```bash
export HARNESS_API_TOKEN=dev-token
./scripts/run_integration_codex.sh
```

See `TESTING.md` for filter test cases and expected outcomes.

## How to run
### Interactive mode (Codex)
Requires `~/.codex/auth.json` and `~/.codex/skills` on the host.
```bash
docker compose -f compose.yml -f compose.codex.yml run --rm --service-ports \
  -e HARNESS_MODE=tui \
  harness
```
The default TUI command uses `/work` and disables Codex sandboxing (`codex -C /work -s danger-full-access`); override via `HARNESS_TUI_CMD`.

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
The harness runs in server mode when stdin is not a TTY; use `HARNESS_MODE=server` to force it.

### Interactive mode (no Codex; plain shell)
```bash
docker compose -f compose.yml run --rm --service-ports \
  -e HARNESS_MODE=tui \
  -e "HARNESS_TUI_CMD=bash -l" \
  harness
```
