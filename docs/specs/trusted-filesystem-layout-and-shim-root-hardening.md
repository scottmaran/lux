# Spec: Trusted Filesystem Layout And Shim Root Hardening

Status: draft
Owner: codex
Created: 2026-02-19
Last updated: 2026-02-19

## Problem
Lux currently mixes concerns across host paths:
- User-editable config lives in `~/.config/lux` (expected), but trusted operational
  artifacts are split across multiple locations.
- Managed shims are installed to `~/.local/bin`, which can overlap the default
  workspace when `paths.workspace_root=$HOME`.
- This weakens trust guarantees for shim-mediated launch and creates an
  inconsistent mental model for users trying to understand Lux footprint.

The product goal is a clean, predictable, and trust-aligned filesystem contract:
- user intent/config in one place
- trusted Lux runtime assets in one place (outside workspace scope)
- agent workspace in one place

## Goals
- Define a clean filesystem layout based on explicit trust zones.
- Keep default workspace at `$HOME`.
- Move managed shim installation outside workspace scope by default.
- Keep `codex ...` / `claude ...` workflow frictionless after one-time setup.
- Preserve existing invariants in `INVARIANTS.md`, especially evidence integrity
  and attribution confidence.
- Make shim install behavior deterministic and atomic (no partial mutation on
  command failure).

## Non-Goals
- Changing `paths.workspace_root` default away from `$HOME`.
- Supporting Windows in this phase.
- Redesigning evidence schemas.
- Relocating versioned CLI binary install (`~/.lux`) in this phase.
  - Current install/update/rollback contract is already anchored on
    `~/.lux/versions` + `~/.lux/current` + `~/.local/bin/lux`; this spec
    focuses on trusted runtime/shim layout without changing release lifecycle.

## User Experience
### Filesystem model
Users reason about three zones:
1. User config zone (editable): `~/.config/lux`
2. Trusted Lux zone (outside workspace): OS-specific shared root
3. Agent workspace zone (rw by agent): `paths.workspace_root` (default `$HOME`)

### Defaults
- macOS trusted root: `/Users/Shared/Lux`
- Linux trusted root: `/var/lib/lux`

Default subpaths under trusted root:
- shims: `<trusted_root>/bin`
- logs: `<trusted_root>/logs`
- runtime socket dir: `<trusted_root>/runtime`
- Lux state files: `<trusted_root>/state`
- provider API-key secrets: `<trusted_root>/secrets`

### Commands
- `lux shim install` (no provider args): installs for all providers defined in
  `config.providers` (not hard-coded names).
- `lux shim install` fails before writing anything when preflight fails.
- `lux shim install` warns when shim bin dir is not first in PATH resolution.
- `lux doctor` includes shim readiness checks (path safety + PATH precedence).

### One-time setup UX
`lux setup` prints explicit next steps for PATH when needed, for example:
- add `<trusted_root>/bin` to PATH
- re-run `lux doctor` to confirm `codex`/`claude` resolve to Lux shims first

## Design
### 1) Config contract extensions (version remains `2`)
Extend `config.yaml` with optional/defaulted blocks:

```yaml
paths:
  workspace_root: /home/alice
  trusted_root: /var/lib/lux
  log_root: /var/lib/lux/logs

shims:
  bin_dir: /var/lib/lux/bin
```

Rules:
- `paths.workspace_root` must be under `$HOME` (unchanged).
- `paths.trusted_root` must be outside `$HOME`.
- `paths.log_root` must be inside `paths.trusted_root`.
- `shims.bin_dir` must be inside `paths.trusted_root`.
- `shims.bin_dir` must not overlap `paths.workspace_root`.
- Runtime/state/secrets defaults derive from `paths.trusted_root` unless
  explicitly overridden by existing advanced flags.

Decision: keep `version: 2` and add optional/defaulted fields rather than
forcing a schema-version bump. This minimizes migration friction while allowing
an explicit trust-root model.

### 2) Trusted-root derived runtime paths
Default paths become:
- runtime socket: `<trusted_root>/runtime/control_plane.sock`
- runtime pid/events: `<trusted_root>/runtime/*`
- active run/provider state files: `<trusted_root>/state/*`
- compose env file default: `<trusted_root>/state/compose.env`
- provider secrets default templates in setup/docs:
  - `<trusted_root>/secrets/codex.env`
  - `<trusted_root>/secrets/claude.env`

Rationale:
- keeps trusted operational files out of workspace scope when workspace is `$HOME`
- keeps all Lux runtime assets grouped under one root

### 3) Shim install/uninstall/list semantics
`lux shim install [provider...]`:
- Provider set resolution:
  - explicit args: those providers
  - no args: sorted `config.providers.keys()`
- Preflight phase (no writes):
  - provider exists in config
  - target path is allowed by path policy
  - bin dir exists or can be created
  - existing file is absent or Lux-managed shim
- Apply phase:
  - write all shims atomically
  - if any write fails, rollback newly created shims from this invocation

`lux shim uninstall [provider...]`:
- default provider set is config-driven (same resolution rule)
- removes only Lux-managed shims in configured bin dir

`lux shim list`:
- includes provider, path, installed status
- adds diagnostics:
  - `path_safe` (outside workspace scope)
  - `path_precedence_ok` (first resolver on PATH)
  - `resolved_candidates` (from `which -a`/equivalent)

### 4) Shim execution hardening
`lux shim exec <provider> -- <argv...>` adds:
- safety checks that configured shim path remains outside workspace scope
- current host cwd mapping to container workdir (`HARNESS_AGENT_WORKDIR`), so
  shimmed launch preserves normal subdirectory workflow semantics
- unchanged v1 path behavior for argv:
  - no path rewriting
  - absolute host-path args fail fast

### 5) Doctor checks
Add/extend checks:
- `shim_bin_path_policy`:
  - fails if `shims.bin_dir` overlaps workspace or escapes trusted root
- `shim_path_precedence`:
  - warns (strict-fail) if `codex`/`claude` do not resolve first to Lux-managed
    shims in `shims.bin_dir`
- `trusted_root_permissions`:
  - verifies trusted root and key subdirs can be created/accessed by Lux process

### 6) Setup behavior
`lux setup`:
- computes trusted-root defaults by OS
- proposes/create subdirs under trusted root
- offers to write provider secrets into `<trusted_root>/secrets`
- prints PATH remediation when `<trusted_root>/bin` is not first for providers
- PATH remediation remains text-only in setup/doctor for this phase (no new
  helper command such as `lux shim path`).

### 7) Alternatives considered
Alternative A: keep shims in `~/.local/bin` and rely on marker checks.
- Rejected: overlaps default workspace scope when workspace is `$HOME`, allowing
  agent-side tampering risk.

Alternative B: require workspace default change away from `$HOME`.
- Rejected by product requirement for this phase.

Alternative C: install shims in `/usr/local/bin`.
- Rejected for now: requires elevated privileges and creates cross-user coupling.

## Data / Schema Changes
- `config.yaml` contract additions:
  - `paths.trusted_root` (optional/defaulted)
  - `shims.bin_dir` (optional/defaulted)
- Runtime/control artifact default locations move from config-dir-derived paths
  to trusted-root-derived paths.
- Active state file locations move from `log_root` top-level dotfiles to
  `<trusted_root>/state`.

No changes to raw/filtered/timeline evidence schemas.

## Security / Trust Model
- Reinforces Invariant 2 by ensuring managed launch control (`codex`/`claude`
  shims) lives outside workspace scope when workspace is `$HOME`.
- Keeps evidence sink outside workspace (existing policy), and aligns shim,
  runtime socket, state pointers, and secrets with the same trusted root.
- Reduces silent bypass risk by adding PATH precedence diagnostics and strict
  checks.

Boundary note:
- User config remains in `~/.config/lux` by design for editability. This phase
  hardens execution surfaces and trusted runtime artifacts, not full protection
  against intentional host-user-level config edits.

## Failure Modes
- Trusted root not writable:
  - `setup`, `config apply`, `doctor`, and `shim install` fail with actionable
    permission remediation.
- `shims.bin_dir` overlaps workspace:
  - config validation error; shim commands refuse execution.
- PATH precedence wrong:
  - `shim install` prints warning; `doctor --strict` fails.
- Partial shim writes:
  - prevented by preflight + atomic apply/rollback.
- Provider missing from config during default install:
  - no mutation; actionable error.

## Acceptance Criteria
- Defaults create a trust-root layout:
  - macOS: `/Users/Shared/Lux/{bin,logs,runtime,state,secrets}`
  - Linux: `/var/lib/lux/{bin,logs,runtime,state,secrets}`
- With `workspace_root=$HOME`, default shim path is outside workspace scope.
- `lux shim install` with no args uses providers from config, not hard-coded
  provider names.
- `lux shim install` is atomic: failure causes no partial installed set.
- `lux shim exec` preserves caller cwd semantics via container workdir mapping.
- `lux doctor` reports shim path safety and PATH precedence readiness.
- Existing invariant-level guarantees remain true and tests pass.
- All canonical repository tests pass after implementation:
  - `uv run python scripts/all_tests.py --lane fast`
  - `uv run python scripts/all_tests.py --lane pr`
  - `uv run python scripts/all_tests.py --lane full`

## Test Plan
- Unit tests (`lux/src/main.rs`):
  - trusted-root default computation and path-policy validation
  - shim provider resolution (no-arg config-driven)
  - shim install preflight + rollback semantics
  - shim cwd mapping logic
  - doctor shim/path readiness checks
- CLI tests (`lux/tests/cli.rs`):
  - default trusted-root path rendering under mocked OS/HOME contexts
  - shim install no-arg behavior with custom provider sets
  - no-partial-write behavior on multi-provider failure
  - shim exec cwd preservation in nested workspace paths
  - doctor strict failure for PATH precedence mismatch
- Integration coverage:
  - end-to-end setup + shim install + provider launch from nested cwd
  - runtime socket/state artifact placement under trusted root
  - secrets path mounting from trusted-root secrets location
- Regression tests:
  - prevent reintroduction of workspace-overlapping shim paths
  - prevent hard-coded `codex`/`claude` defaults in no-arg install path

## Rollout
- Stealth mode allows intentional behavior changes without backcompat promise.
- Rollout sequence:
1. Implement config/path validation and trusted-root defaults.
2. Move runtime/state/env default locations.
3. Implement shim install atomicity + config-driven defaults.
4. Add cwd-preserving shim execution behavior.
5. Add doctor/setup PATH and policy checks.
6. Update contracts/docs/tests together.

Intentional breakages:
- Existing setups relying on `~/.local/bin` Lux shims must re-run `lux shim install`
  after updating config/setup.
- Existing runtime socket/env/state paths under config dir are migrated to
  trusted-root defaults unless explicitly overridden.

## Open Questions
- None for this draft.
