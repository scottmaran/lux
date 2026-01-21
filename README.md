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

## TUI manual check
```bash
docker compose run --rm --service-ports -e HARNESS_MODE=tui harness
```
Use `-f compose.yml -f compose.codex.yml` if the agent needs host Codex credentials.
The default TUI command uses `/work` and disables Codex sandboxing (`codex -C /work -s danger-full-access`); override via `HARNESS_TUI_CMD`.
