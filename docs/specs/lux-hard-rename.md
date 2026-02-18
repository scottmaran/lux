# Spec: Lux Hard-Break Full Technical Rename

Status: draft
Owner: codex
Created: 2026-02-18
Last updated: 2026-02-18

## Problem
The product and runtime surfaces are currently coupled to the name `lasso` across
CLI command names, environment variables, install/update paths, run identifiers,
Docker image names, release artifact names, test expectations, and contract docs.

A partial rename would produce mixed identity, broken install/update flows, and
drift between contracts and implementation. We need one atomic technical rename
to `lux` with explicit hard-break behavior.

## Goals
- Rename all technical surfaces from `lasso`/`LASSO_*` to `lux`/`LUX_*`.
- Enforce a hard break: no compatibility aliases, no dual support, no fallback.
- Keep product invariants intact (evidence completeness, integrity, attribution,
  and non-cooperative observation).
- Keep behavior unchanged except for naming and path/identifier migrations
  required by the rename.
- Leave repo in a releasable state for manual publication of new `lux` releases.

## Non-Goals
- Backward compatibility with old `lasso` command, env vars, dirs, or run IDs.
- Automatic migration of `~/.lasso`, `~/.config/lasso`, or legacy run directories.
- Legacy release publication automation for `lasso` artifacts after this change.
- Any change to evidence schemas beyond renamed path/run-id examples.
- Any change to trust boundaries or attribution algorithms.

## User Experience
- Primary command becomes `lux` (not `lasso`).
- Installer script becomes `install_lux.sh`.
- Default install/config dirs become:
  - `~/.lux`
  - `~/.config/lux`
- Default host log roots become:
  - macOS: `/Users/Shared/Lux/logs`
  - Linux: `/var/lib/lux/logs`
- Run IDs become `lux__YYYY_MM_DD_HH_MM_SS`.
- Compose/runtime env variables become `LUX_*`.
- Host runtime socket default remains `<config_dir>/runtime/control_plane.sock`
  (there is no host default under `/run`).
- UI container runtime mount paths move to `/run/lux/...`.
- Docker image names become `ghcr.io/<owner>/lux-agent|lux-harness|lux-collector|lux-ui`.
- New `lux` installs do not install/link `lasso`.
- Legacy `lasso` installations are unsupported after cutover.
- Existing `lasso__*` runs are not auto-discovered by default UX after rename.

## Design

### Canonical Hard-Break Rename Map

| Surface | Old | New |
|---|---|---|
| CLI command/binary | `lasso` | `lux` |
| Rust crate/package | `lasso` | `lux` |
| Installer script | `install_lasso.sh` | `install_lux.sh` |
| Env prefix | `LASSO_*` | `LUX_*` |
| Install dir | `~/.lasso` | `~/.lux` |
| Config dir | `~/.config/lasso` | `~/.config/lux` |
| Runtime paths | `/run/lasso/...` | `/run/lux/...` |
| Runtime fallback socket tokens | `/tmp/lasso*` | `/tmp/lux*` |
| Harness root marker paths | `/tmp/lasso_root_pid_<id>.txt`, `/tmp/lasso_root_sid_<id>.txt` | `/tmp/lux_root_pid_<id>.txt`, `/tmp/lux_root_sid_<id>.txt` |
| Provider profile export script | `/etc/profile.d/lasso-provider-auth.sh` | `/etc/profile.d/lux-provider-auth.sh` |
| Setup writable probe sentinel | `.lasso_write_test` | `.lux_write_test` |
| Update temp download dir prefix | `lasso-update-*` | `lux-update-*` |
| Run prefix | `lasso__` | `lux__` |
| Image names | `lasso-*` | `lux-*` |
| Bundle names | `lasso_<ver>_...` | `lux_<ver>_...` |
| Docker project default | `docker.project_name: lasso` | `docker.project_name: lux` |
| Product text | `Lasso` | `Lux` |

### Canonical Environment Variable Rename Inventory

All active `LASSO_*` environment variables are renamed to `LUX_*` with no aliasing.

Runtime/config/install/update:
- `LASSO_CONFIG` -> `LUX_CONFIG`
- `LASSO_CONFIG_DIR` -> `LUX_CONFIG_DIR`
- `LASSO_ENV_FILE` -> `LUX_ENV_FILE`
- `LASSO_BUNDLE_DIR` -> `LUX_BUNDLE_DIR`
- `LASSO_RELEASE_BASE_URL` -> `LUX_RELEASE_BASE_URL`
- `LASSO_RUNTIME_BYPASS` -> `LUX_RUNTIME_BYPASS`

Compose/runtime generated env:
- `LASSO_VERSION` -> `LUX_VERSION`
- `LASSO_LOG_ROOT` -> `LUX_LOG_ROOT`
- `LASSO_WORKSPACE_ROOT` -> `LUX_WORKSPACE_ROOT`
- `LASSO_RUNTIME_DIR` -> `LUX_RUNTIME_DIR`
- `LASSO_RUNTIME_GID` -> `LUX_RUNTIME_GID`
- `LASSO_RUN_ID` -> `LUX_RUN_ID`

Provider runtime wiring:
- `LASSO_PROVIDER` -> `LUX_PROVIDER`
- `LASSO_AUTH_MODE` -> `LUX_AUTH_MODE`
- `LASSO_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE` -> `LUX_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE`
- `LASSO_PROVIDER_ENV_KEY` -> `LUX_PROVIDER_ENV_KEY`
- `LASSO_PROVIDER_HOST_STATE_COUNT` -> `LUX_PROVIDER_HOST_STATE_COUNT`
- `LASSO_PROVIDER_HOST_STATE_SRC_<n>` -> `LUX_PROVIDER_HOST_STATE_SRC_<n>`
- `LASSO_PROVIDER_HOST_STATE_DST_<n>` -> `LUX_PROVIDER_HOST_STATE_DST_<n>`
- `LASSO_PROVIDER_SECRETS_FILE` -> `LUX_PROVIDER_SECRETS_FILE`

Test/CI knobs:
- `LASSO_STRESS_TRIALS` -> `LUX_STRESS_TRIALS`
- `LASSO_RUN_EXTERNAL_INSTALL` -> `LUX_RUN_EXTERNAL_INSTALL`
- `LASSO_EXTERNAL_INSTALL_VERSION` -> `LUX_EXTERNAL_INSTALL_VERSION`
- `LASSO_EXTERNAL_INSTALL_REPO` -> `LUX_EXTERNAL_INSTALL_REPO`

### Implementation Boundaries To Update

1. CLI and runtime implementation:
- Rename crate directory `lasso/` to `lux/`.
- Rename package metadata and binary targets to `lux`.
- Rename clap command name and all user-facing examples/errors.
- Rename runtime host header token and shim marker text to `lux`.

2. Installer/update/uninstall system:
- Rename install script and all internal file-name assumptions.
- Rename release bundle/checksum naming patterns to `lux_*`.
- Rename install/current/bin symlink targets to `lux`.
- Rename release base URL env var to `LUX_RELEASE_BASE_URL`.
- Rename default release source constants to:
  - downloads: `https://github.com/scottmaran/lux/releases/download`
  - latest-release API: `https://api.github.com/repos/scottmaran/lux/releases/latest`
  - HTTP user-agent token: `lux-cli`.

3. Config/env/path resolution:
- Rename all `LASSO_*` env variables listed in this spec to `LUX_*`.
- Rename default config/install directories and default log roots to `lux`.
- Rename default docker project identity from `lasso` to `lux`.

4. Compose and provider wiring:
- Update `compose.yml` and `compose.ui.yml` to use only `LUX_*`.
- Update `LASSO_*` provider env injection surfaces to `LUX_*` in:
  - runtime override generation,
  - agent entrypoint consumption,
  - provider auth docs/tests.
- Rename provider runtime mount paths:
  - `/run/lasso/provider_host_state/...` -> `/run/lux/provider_host_state/...`
  - `/run/lasso/provider_secrets.env` -> `/run/lux/provider_secrets.env`.
- Rename provider export script path:
  - `/etc/profile.d/lasso-provider-auth.sh` -> `/etc/profile.d/lux-provider-auth.sh`.

5. Run identity and discovery:
- Run generation uses `lux__...`.
- Run discovery filters use `lux__` only.
- UI default run prefix uses `lux__` only.

6. UI and runtime proxy:
- Rename product title text to `Lux`.
- Preserve host runtime socket default contract:
  - `<config_dir>/runtime/control_plane.sock` (with existing long-path fallback behavior).
- Rename UI container runtime mount/socket paths:
  - `/run/lasso/runtime/control_plane.sock` -> `/run/lux/runtime/control_plane.sock`.
- Rename proxy host header token to `lux-runtime`.
- Rename runtime fallback socket path tokens in temp paths from `lasso*` to `lux*`.
- Rename internal setup/update temp and sentinel tokens from `lasso*` to `lux*`.

7. Harness runtime markers:
- Rename root marker paths:
  - `/tmp/lasso_root_pid_<id>.txt` -> `/tmp/lux_root_pid_<id>.txt`
  - `/tmp/lasso_root_sid_<id>.txt` -> `/tmp/lux_root_sid_<id>.txt`.
- Update harness marker docs/tests to assert `lux` marker paths.

8. Test harness and coverage:
- Rename all integration/unit/external test assumptions for:
  - binary name,
  - env names,
  - default paths,
  - run prefix,
  - bundle names,
  - repo/release URLs,
  - compose project/image prefixes.
- Update compose parity tests to assert `LUX_*` contract keys.

9. Docs and contracts:
- Update normative docs first (`AGENTS.md`, `INVARIANTS.md`, `docs/contracts/*`,
  `tests/README.md`, component READMEs, root `README.md`).
- Update implementation/history docs second.
- Historical docs may mention old name only as archival context, not as active
  command/interface guidance.

10. CI/release workflows:
- Update workflow checks, build steps, artifact names, and image tags to `lux`.
- Update release-prep scripts that parse crate/package names and paths.
- Keep workflows valid even if releases are manually published.
- Rename test/CI env knobs from `LASSO_*` to `LUX_*`.

### Hard-Break Enforcement
- No command alias `lasso -> lux`.
- No env aliasing (`LASSO_*` rejected/ignored; only `LUX_*` is supported).
- No auto-read/write fallback to `~/.lasso` or `~/.config/lasso`.
- No dual run-prefix support (`lasso__` not treated as active format).

## Data / Schema Changes
- No schema version changes for raw/filtered/timeline contracts.
- Contract examples and path docs are renamed from `lasso` to `lux`.
- On-disk run directory naming convention changes from `lasso__*` to `lux__*`.
- Runtime support files move from `~/.config/lasso/runtime` to
  `~/.config/lux/runtime`.

## Security / Trust Model
- No invariant changes are allowed.
- Evidence sink protection model remains unchanged:
  - agent still has read-only evidence access where designed,
  - trusted components keep write permissions as before.
- Rename must preserve current attribution and ownership behavior.
- No additional trusted components are introduced.

## Failure Modes
- Missing rename in any boundary causes immediate hard failures by design:
  - install/update cannot resolve expected bundle names,
  - compose services fail due to mismatched env keys,
  - provider bootstrap fails on missing renamed auth env vars,
  - runtime/UI proxy fails on mismatched socket path/host tokens.
- Legacy `lasso` installations may still execute locally but are unsupported and
  may fail due to incompatible artifacts/config after cutover.
- Legacy `lasso__*` historical runs may not appear in default run listings.

## Acceptance Criteria
- `lux` binary exists and `lasso` binary is not produced by build/release.
- `lux --json paths` reports only `lux`-named install/config/runtime surfaces.
- Installer flow works via `install_lux.sh` and installs under `~/.lux` with
  config at `~/.config/lux/config.yaml`.
- Update flow uses `lux` bundle naming and `LUX_RELEASE_BASE_URL`.
- Default update constants are renamed and verified:
  - release download base URL defaults to `https://github.com/scottmaran/lux/releases/download`,
  - latest-release API defaults to `https://api.github.com/repos/scottmaran/lux/releases/latest`,
  - HTTP user-agent token is `lux-cli`.
- Compose stack boots with only `LUX_*` variables and `lux-*` image names.
- Compose/runtime defaults include `docker.project_name: lux`.
- Provider auth bootstrap works with renamed `LUX_*` provider env vars.
- Provider auth export script path is `/etc/profile.d/lux-provider-auth.sh`.
- Runtime control-plane host default socket remains `<config_dir>/runtime/control_plane.sock`.
- UI proxy communicates via `/run/lux/runtime/control_plane.sock` inside the UI container.
- Runtime long-path fallback socket names use `lux` tokens only.
- Setup/update temporary and sentinel naming tokens use `lux` (`.lux_write_test`, `lux-update-*`).
- Harness root marker paths use `lux` tokens (`/tmp/lux_root_pid_*`, `/tmp/lux_root_sid_*`).
- New runs are created as `lux__*` and UI/CLI run discovery uses that prefix.
- Contract docs are updated to `lux` for active behavior.
- CI/release workflows build/publish `lux` artifacts and `lux-*` images.
- Test/CI env knobs use `LUX_*` names.
- No compatibility layers are introduced for old command/env/path/run formats.
- Verification gates pass:
  - `uv sync`
  - `uv run python scripts/all_tests.py --lane fast`
  - `uv run python scripts/all_tests.py --lane pr`
  - `uv run python scripts/all_tests.py --lane full`
  - `(cd lux && cargo test)`

## Test Plan
- Unit tests:
  - CLI/config/path resolution uses `LUX_*` variables only.
  - Default path generation uses `lux` defaults.
  - Default docker project name is `lux`.
  - Run-id generation/discovery uses `lux__`.
  - Installer/update naming logic expects `lux_*` bundles and `lux` binary.
  - Update defaults use `scottmaran/lux` release endpoints and `lux-cli` user-agent.
  - Runtime fallback socket path generation uses `lux` tokens.
  - Harness marker helpers generate `/tmp/lux_root_pid_*` and `/tmp/lux_root_sid_*`.
  - Provider auth export script path is `/etc/profile.d/lux-provider-auth.sh`.
  - Setup/update internal temp/sentinel tokens use `lux` names.
- Fixture cases:
  - Update any fixture or golden data that embeds command/env/path/run naming.
  - Confirm fixture schema validation still passes.
- Integration coverage:
  - CLI lifecycle tests use `lux` binary and renamed config/env surfaces.
  - Installer/update/uninstall tests validate `~/.lux` and `~/.config/lux`.
  - Runtime control-plane tests validate `lux-runtime` and `/run/lux/...`.
  - UI API tests validate `lux__` run discovery behavior.
  - Compose parity tests enforce `LUX_*` contract keys.
  - Compose lifecycle tests validate default `docker.project_name=lux`.
- Regression tests:
  - Add targeted regressions for common rename misses:
    - provider env mismatch,
    - update bundle name mismatch,
    - run discovery prefix mismatch,
    - installer path mismatch,
    - fallback socket naming mismatch,
    - release endpoint/user-agent mismatch,
    - harness marker path mismatch,
    - provider export script path mismatch,
    - setup/update sentinel token mismatch.
- Manual verification (required before release):
  - clean install with `install_lux.sh`,
  - `lux setup`,
  - `lux runtime up`,
  - `lux ui up --wait`,
  - `lux up --collector-only --wait`,
  - `lux up --provider codex --wait`,
  - `lux tui --provider codex`,
  - verify logs under `lux__*`.

## Rollout
- This is a single hard-break rollout.
- Merge all rename changes atomically (code + tests + contracts + workflows).
- Do not publish mixed-name artifacts.
- Manual publication after merge:
  - publish `lux_*` release bundles/checksums,
  - publish `lux-*` images,
  - publish updated install instructions that use `install_lux.sh`.
- Explicitly communicate that prior `lasso` installs are unsupported after cutover.

## Open Questions
- None.
