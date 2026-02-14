# Lasso

Agent Harness is an OS‑level observation system for third‑party agents: it runs the agent in a container, uses auditd + eBPF inside the Docker Desktop VM to capture exec/fs/network/IPC metadata, and correlates that into a session‑tagged timeline. The stack includes a harness (PTY + API), a collector pipeline (filter → summary → merge), a dedicated container to run the agent, and a UI for log review.

## Lasso CLI (beta)
The recommended way to run the stack is via the `lasso` CLI, which pulls the
versioned Docker images from GHCR and manages config + compose wiring.

Temporary support note (February 2026): Linux host runtime support is
temporarily not guaranteed while bind-mount permission compatibility work is in
progress. The currently recommended host is macOS with Docker Desktop.

### Install (beta)
Run the versioned installer:
```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lasso/${VERSION}/install_lasso.sh" | bash -s -- --version "${VERSION}"
```
Private repo note: if the repo or release assets are private, unauthenticated
`curl` downloads may return 404. In that case, download the release bundle with
`gh release download` and run `install_lasso.sh` with `--bundle/--checksum`.
If `lasso` is "command not found" after install, ensure `~/.local/bin` is in your `PATH`.
This installs the CLI bundle but does **not** create log/workspace directories. Run `lasso config init` to create the default configurations, then edit `~/.config/lasso/config.yaml` to modify configs. You can customize `paths.log_root` and `paths.workspace_root`.
You must run `lasso config apply` to validate config values, write `~/.config/lasso/compose.env`, and create the configured log/workspace directories.

Quick start (after install):
```bash
lasso config init
lasso config apply
lasso up --collector-only --wait
lasso up --provider codex --wait
lasso tui --provider codex
```

Provider selection is explicit for agent-facing actions (`--provider codex|claude`).
Collector lifecycle is separate (`--collector-only`).

To view more info about user configs, see `docs/guide/config.md`.

## Run-scoped logs
Each `lasso up` creates a new run directory under `paths.log_root`, for example:

```text
~/lasso-logs/
  lasso__2026_02_12_12_23_54/
    collector/raw/
    collector/filtered/
    harness/sessions/
    harness/jobs/
    harness/labels/
```

`lasso logs tail` and `lasso jobs ...` default to the active run. If no run is
active, use `--run-id <id>` or `--latest`.

## Docs
Start with the user guide in `docs/guide/`.
Developers/contributors: see `docs/README.md` for the full documentation map.

## License
Licensed under the GNU Affero General Public License v3.0 only (`AGPL-3.0-only`).
See `LICENSE`.

## Contributing
See `CONTRIBUTING.md`.
