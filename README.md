# Lux

Lux is an OS‑level observation system for third‑party agents: it runs the agent in a container, uses auditd + eBPF inside the Docker Desktop VM to capture exec/fs/network/IPC metadata, and correlates that into a session‑tagged timeline. The stack includes a harness (PTY + API), a collector pipeline (filter → summary → merge), a dedicated container to run the agent, and a UI for log review.

## Lux CLI (beta)
The recommended way to run the stack is via the `lux` CLI, which pulls the
versioned Docker images from GHCR and manages config + compose wiring.

Temporary support note (February 2026): 
- Linux host runtime support is temporarily not guaranteed while bind-mount permission compatibility work is in progress. The currently recommended host is macOS with Docker Desktop.
- On MacOS for subscription-based Claude Code sessions on MacOS, you need to log in upon starting the TUI
See platform support/caveats: `docs/contracts/platform.md`.

### Install (beta)
Run the versioned installer:
```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lux/${VERSION}/install_lux.sh" | bash -s -- --version "${VERSION}"
```
To run the interactive setup wizard automatically after install:
```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lux/${VERSION}/install_lux.sh" | bash -s -- --version "${VERSION}" --setup
```
Private repo note: if the repo or release assets are private, unauthenticated
`curl` downloads may return 404. In that case, download the release bundle with
`gh release download` and run `install_lux.sh` with `--bundle/--checksum`.
If `lux` is "command not found" after install, ensure `~/.local/bin` is in your `PATH`.
This installs the CLI bundle but does **not** create log/workspace directories. Run `lux setup` to configure `config.yaml` (paths + provider auth) and generate the runtime `compose.env`.

Quick start (after install):
```bash
lux setup
lux runtime up
lux ui up --wait
lux shim install codex claude
codex
```

Provider selection is explicit for agent-facing actions (`--provider codex|claude`).
Collector lifecycle is separate (`--collector-only`).

To view more info about user configs, see `docs/contracts/config.md`.

## Run-scoped logs
Each `lux up` creates a new run directory under `paths.log_root`, for example:

```text
~/lux-logs/
  lux__2026_02_12_12_23_54/
    collector/raw/
    collector/filtered/
    harness/sessions/
    harness/jobs/
    harness/labels/
```

`lux logs tail` and `lux jobs ...` default to the active run. If no run is
active, use `--run-id <id>` or `--latest`.

## Docs
Start with the user guide in `docs/contracts/`.
Developers/contributors: see `docs/README.md` for the full documentation map.

## License
Licensed under the GNU Affero General Public License v3.0 only (`AGPL-3.0-only`).
See `LICENSE`.

## Security and Legal
- Security reporting policy: `SECURITY.md`
- Community conduct policy: `CODE_OF_CONDUCT.md`
- Contributor license agreement: `CLA.md`
- Legal use and monitoring consent: `legal/legal_use.md`
- Log retention/deletion policy: `legal/log_retention.md`
- Open source compliance/source availability: `legal/open_source_compliance.md`

## Contributing
See `CONTRIBUTING.md`.
