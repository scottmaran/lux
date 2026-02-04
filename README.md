# Lasso

Agent Harness is an OS‑level observation system for third‑party agents: it runs the agent in a container, uses auditd + eBPF inside the Docker Desktop VM to capture exec/fs/network/IPC metadata, and correlates that into a session‑tagged timeline. The stack includes a harness (PTY + API), a collector pipeline (filter → summary → merge), a dedicated container to run the agent, and a UI for log review.

## Lasso CLI (beta)
The recommended way to run the stack is via the `lasso` CLI, which pulls the
versioned Docker images from GHCR and manages config + compose wiring.

### Install (beta)
Download from GitHub Releases and run:
```bash
curl -fsSL https://github.com/scottmaran/lasso/releases/download/v0.4.0/install_lasso.sh -o install_lasso.sh
bash install_lasso.sh --version v0.4.0
```
This installs the CLI bundle but does **not** create log/workspace directories. Run `lasso config init` to create the default configurations, then edit `~/.config/lasso/config.yaml` to modify configs. You can customize `paths.log_root` and `paths.workspace_root`.
You must run `lasso config apply` to validate the configs are valid and propogate them to their respective yaml files in the codebase.

Quick start (after install):
```bash
lasso config init
lasso config apply
lasso up --codex
lasso tui --codex
```

To view more info about user configs, view guide/cli.md


## Documentation Map
```
README.md (you are here)
├─ Guide
│  ├─ install.md — installer + manual install steps
│  └─ cli.md — CLI commands and behavior
│  └─ config.md — Documentation for user's config.yaml describing settings
├─ Orientation
│  ├─ overview.md — system summary and goals
│  ├─ platform.md — platform assumptions and constraints
│  └─ kernel_auditing_info.md — kernel audit/eBPF notes
├─ VM boundary & layout
│  ├─ docker_desktop_vm.md — Docker Desktop VM behavior
│  └─ lasso_vm_layout.md — VM/container layout
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
├─ CLI
│  └─ lasso/ — Rust CLI source (release bundles ship the binary only)
├─ Past work & rationale
│  ├─ HISTORY.md — narrative history and decisions
│  └─ dev_log.md — implementation log
└─ Scratch
   └─ scratch_notes.md — working notes
```

## How to
### Start up commands (legacy/manual compose)
#### Interactive mode (Codex)
Requires `~/.codex/auth.json` and `~/.codex/skills` on the host.
```bash
docker compose -f compose.yml -f compose.codex.yml up -d --build agent collector

docker compose -f compose.yml -f compose.codex.yml run --rm \
  -e HARNESS_MODE=tui harness
```
The harness connects to the `agent` service over SSH; the collector must be running to emit audit/eBPF logs. `docker compose run` does not start dependencies.
The default TUI command uses `/work` and disables Codex sandboxing (`codex -C /work -s danger-full-access`); override via `HARNESS_TUI_CMD`.

#### Non-interactive mode (Codex)
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

#### Interactive mode (no Codex; plain shell)
```bash
docker compose -f compose.yml up -d --build agent collector

docker compose -f compose.yml run --rm \
  -e HARNESS_MODE=tui \
  -e "HARNESS_TUI_CMD=bash -l" \
  harness
```

#### Log viewer UI
```bash
docker compose -f compose.ui.yml up -d --build ui
```
The UI reads from `${LASSO_LOG_ROOT:-./logs}` and binds to `http://127.0.0.1:8090`.

### Compose files
- `compose.yml`: base stack (agent-agnostic).
- `compose.codex.yml`: adds host Codex auth + skills mounts for the agent container.
- `compose.ui.yml`: UI-only service that mounts `./logs` read-only.

See `TESTING.md` for integration tests and filter test cases.
