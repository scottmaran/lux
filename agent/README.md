# Agent Container

Purpose: run the provider CLI inside an isolated container while exposing SSH for the harness PTY/API control plane.

## Runtime Contract

- `/work`: writable workspace mount.
- `/logs`: read-only logs mount.
- SSH user: `agent` (uid 1001), key-only auth.
- No Docker socket access.

## Provider Bootstrap Env

`lasso` injects provider settings via compose runtime overrides:

- `LASSO_PROVIDER`
- `LASSO_AUTH_MODE` (`api_key` or `host_state`)
- `LASSO_PROVIDER_SECRETS_FILE`
- `LASSO_PROVIDER_ENV_KEY`
- `LASSO_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE`
- `LASSO_PROVIDER_HOST_STATE_COUNT`
- `LASSO_PROVIDER_HOST_STATE_SRC_<n>`
- `LASSO_PROVIDER_HOST_STATE_DST_<n>`

Behavior:
- `api_key`: entrypoint loads key from secrets file and exports it for shell sessions.
- `host_state`: entrypoint copies mounted host-state files/directories into `/home/agent`.
- `api_key` + `mount_host_state_in_api_mode=true`: host-state copy also runs.

## Supported CLIs

- `codex` (`@openai/codex`)
- `claude` (`@anthropic-ai/claude-code`)

## Legacy Compatibility

Legacy Codex mounts (`/run/codex_auth.json`, `/run/codex_skills`) are still imported if present.

## Security Posture

- Root login disabled.
- Password auth disabled.
- No host SSH port mapping required.
- `/logs` should remain read-only in the agent.
