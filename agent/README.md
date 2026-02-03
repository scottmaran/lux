# Agent container

Purpose: run the third-party agent (Codex CLI) inside an isolated container while exposing a PTY via SSH for the harness.

## Contract
- `/work` is the writable workspace (bind-mount from host).
- `/logs` is a read-only view of the host log sink.
- SSH is key-only (no passwords), user `agent` (uid 1001).
- The agent container does not need access to the container runtime socket.
- HTTP(S) egress is expected to flow through the proxy service via environment variables injected by the harness.

## SSH configuration
The container expects authorized keys via one of:
- `/config/authorized_keys` (bind-mount, preferred), or
- `/run/authorized_keys` (bind-mount).

Keys should be provided by the harness container so the solution is self-contained.
On startup, the agent waits briefly for the authorized keys to appear so the harness can populate the shared volume.

## Codex CLI
Installed via npm in the image (`@openai/codex`). The entrypoint logs a warning if the `codex` binary is missing.

## Codex auth and skills
The agent can import host credentials and skills on startup:
- `/run/codex_auth.json` -> copied to `/home/agent/.codex/auth.json`
- `/run/codex_skills` -> copied to `/home/agent/.codex/skills`

These mounts are read-only; the entrypoint copies them into the agent home and fixes ownership.

## Usage patterns
Interactive TUI (harness-driven):
- `ssh -tt agent@agent codex`

Non-interactive:
- `ssh agent@agent codex exec "<prompt>"`

## Security posture
- Root login disabled.
- Password auth disabled.
- Port forwarding disabled.
- `/logs` should be mounted read-only from the host sink.
- SSH is internal-only (no host port mapping required).
- The agent runs on an internal network; direct internet egress is blocked unless routed through the proxy.
