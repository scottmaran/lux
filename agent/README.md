# Agent container

Purpose: run the third-party agent (Codex CLI) inside an isolated container while exposing a PTY via SSH for the harness.

## Contract
- `/work` is the writable workspace (bind-mount from host).
- `/logs` is a read-only view of the host log sink.
- SSH is key-only (no passwords), user `agent` (uid 1001).
- The agent container does not need access to the container runtime socket.

## SSH configuration
The container expects authorized keys via one of:
- `/config/authorized_keys` (bind-mount, preferred), or
- `/run/authorized_keys` (bind-mount).

Keys should be provided by the harness container so the solution is self-contained.

## Codex CLI
Installed via npm in the image (`@openai/codex`). The entrypoint logs a warning if the `codex` binary is missing.

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
