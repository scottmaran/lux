# Agent Harness

Containerized harness + agent + collector stack for auditing agent activity inside a VM.

## Documentation Map
```
README.md (you are here)
├─ Orientation
│  ├─ overview.md — system summary and goals
│  ├─ platform.md — platform assumptions and constraints
│  └─ kernel_auditing_info.md — kernel audit/eBPF notes
├─ VM boundary & layout
│  ├─ docker_desktop_vm.md — Docker Desktop VM behavior
│  └─ agent_harness_vm_layout.md — VM/container layout
├─ Components
│  ├─ agent/README.md — agent container setup
│  ├─ harness/README.md — harness behavior and config
│  └─ collector/README.md — collector setup and pipeline
│     ├─ collector/auditd_data.md — audit log schema
│     ├─ collector/eBPF_data.md — eBPF log schema
│     ├─ collector/timeline_data.md — merged timeline schema
│     └─ collector/config/filtering_rules.md — filtering rules
├─ UI
│  ├─ UI_DESIGN.md — UI behavior and layout
│  ├─ UI_API.md — UI API contract
│  ├─ ui/README.md — UI build/run notes
│  └─ ui/src/Attributions.md — asset attributions
├─ Testing & examples
│  ├─ TESTING.md — filter test cases and expected outcomes
│  └─ EXAMPLE_FLOW.md — end-to-end example walkthroughs
├─ Past work & rationale
│  ├─ HISTORY.md — narrative history and decisions
│  └─ dev_log.md — implementation log
└─ Scratch
   └─ scratch_notes.md — working notes
```

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
