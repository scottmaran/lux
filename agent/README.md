# Agent

## Purpose
Provider runtime container (Codex/Claude) plus an SSH endpoint used by the
trusted harness control plane.

## Runtime Contract (Mounts, User, Network)
Mounts:
- `/work`: rw workspace mount
- `/logs`: ro logs mount (evidence only; agent must not be able to mutate logs)

SSH:
- SSH user: `agent` (uid 1001)
- Key-only auth (no passwords)
- No host SSH port mapping required; harness connects on the compose network

Security:
- No Docker socket access

## SSH Hardening
The shipped `agent/sshd_config` disables risky SSH features:
- Root login disabled
- Password auth disabled
- TCP forwarding disabled
- Agent forwarding disabled
- Tunnel/X11 forwarding disabled

## Key Handling (Authorized Keys)
The agent expects `authorized_keys` to be provided via a mount and keeps it in
sync for the lifetime of the container:
- Primary: `/config/authorized_keys` (the shared harness key volume)
- Legacy fallback: `/run/authorized_keys`

On startup, `agent/entrypoint.sh` waits up to `AGENT_AUTH_WAIT_SEC` seconds for
`authorized_keys` to appear, copies it to `/home/agent/.ssh/authorized_keys`,
and then re-syncs it every 2 seconds.

## Provider Bootstrap (Auth + Host State)
`lux` injects provider settings via compose runtime overrides. The agent
entrypoint reads these and bootstraps provider auth before starting `sshd`.

Env vars (agent container):
- `LUX_PROVIDER`
- `LUX_AUTH_MODE` (`api_key` or `host_state`)
- `LUX_PROVIDER_SECRETS_FILE`
- `LUX_PROVIDER_ENV_KEY`
- `LUX_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE`
- `LUX_PROVIDER_HOST_STATE_COUNT`
- `LUX_PROVIDER_HOST_STATE_SRC_<n>`
- `LUX_PROVIDER_HOST_STATE_DST_<n>`

Behavior summary:
- `host_state`: copy mounted host-state items into the configured destination
  paths (usually under `/home/agent/...`) and fix ownership/permissions.
- `api_key`: source the secrets file, export the key for SSH sessions, and
  optionally also run host-state copy when
  `LUX_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE=true`.

For the exact copy/export behavior and code references, see:
- `agent/provider_auth.md`

## Supported CLIs
Installed (pinned in `agent/Dockerfile`):
- `codex` (`@openai/codex`)
- `claude` (`@anthropic-ai/claude-code`)

## Legacy Compatibility
Legacy Codex mounts are imported if present:
- `/run/codex_auth.json` -> `/home/agent/.codex/auth.json`
- `/run/codex_skills` -> `/home/agent/.codex/skills`

## Stage Map (Code + Tests)
| Concern | Code | Primary tests |
|---|---|---|
| Image contents + CLI versions | `agent/Dockerfile` | exercised by Codex lanes under `tests/integration/` |
| Bootstrap + auth/host-state copy | `agent/entrypoint.sh` | `tests/integration/test_agent_codex_exec.py`, `tests/integration/test_agent_codex_tui.py` |
| SSH posture | `agent/sshd_config` | exercised indirectly by harness SSH lanes |
| Env injection source of truth | `lux/src/main.rs` | CLI/integration coverage under `tests/integration/test_cli_*.py` |

## Troubleshooting
- SSH auth fails:
  - Confirm `/config/authorized_keys` exists and is readable in the agent.
  - Check `AGENT_AUTH_WAIT_SEC` and the key sync loop in `agent/entrypoint.sh`.
- Host-state auth missing:
  - Confirm `LUX_PROVIDER_HOST_STATE_COUNT > 0` and mounts exist under
    `/run/lux/provider_host_state/<n>`.
  - Confirm the `LUX_PROVIDER_HOST_STATE_DST_<n>` destinations are correct.
- API-key auth fails:
  - Confirm `LUX_PROVIDER_SECRETS_FILE` exists and contains the key named by
    `LUX_PROVIDER_ENV_KEY`.
  - See `agent/provider_auth.md` for exact behavior.
- CLI missing:
  - Check pinned versions and install steps in `agent/Dockerfile`.

## Change Checklist (For PRs)
- If you change provider bootstrap env vars: update `agent/provider_auth.md` and
  the `lux` runtime override wiring (`lux/src/main.rs`).
- If you bump provider CLI versions: update `agent/Dockerfile` and ensure Codex
  integration lanes still pass locally.
- If you change SSH posture: update `agent/sshd_config` and validate harness SSH
  behavior (TUI + server jobs).
