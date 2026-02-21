# Spec: Shim Enable/Disable/Status With Shell PATH Management

Status: draft
Owner: codex
Created: 2026-02-21
Last updated: 2026-02-21

## Problem
The current shim CLI surface uses implementation-oriented verbs (`install`,
`uninstall`, `list`) instead of user-intent verbs (`enable`, `disable`,
`status`).

Users also need PATH persistence for shim usage, but PATH setup is currently
manual and easy to misconfigure across shells.

This creates avoidable UX friction for the core workflow:
- turn shim behavior on
- run provider CLIs normally
- turn shim behavior off when needed
- verify current shim state quickly

## Goals
- Replace shim command verbs with user-intent verbs:
  - `lux shim enable [provider...]`
  - `lux shim disable [provider...]`
  - `lux shim status [provider...]`
- Remove old shim verbs entirely (`install`, `uninstall`, `list`).
- Keep provider default resolution behavior (no provider args targets all
  configured providers).
- Add PATH persistence management for zsh and bash startup files.
- Make PATH edits idempotent and reversible via Lux-managed marker blocks.
- Do not create missing shell startup files.
- Provide status output with both:
  - top-level summary state
  - per-provider detail
  - shell PATH persistence detail

## Non-Goals
- Creating new shell startup files when none exist.
- Supporting fish, PowerShell, or Windows shell profile management in this
  phase.
- Changing `lux shim exec` passthrough/cwd/path behavior.
- Keeping command aliases or compatibility shims for old subcommands.

## User Experience
- `lux shim enable`:
  - enables shims for configured providers (or explicit providers)
  - persists PATH block in existing zsh/bash startup files found on host
  - prints guidance for current-session activation
- `lux shim disable`:
  - disables shims for configured providers (or explicit providers)
  - removes Lux-managed PATH block from existing startup files
  - prints guidance for current-session activation
- `lux shim status`:
  - reports summary state: `enabled | disabled | degraded`
  - reports per-provider shim install + PATH precedence readiness
  - reports shell PATH persistence coverage across managed files

Behavioral rule:
- If no relevant shell startup files exist, commands do not create files.
  Command succeeds with explicit guidance on one-shot/manual PATH activation.

## Design
### 1) CLI surface replacement
Replace `ShimCommand` subcommands with:
- `Enable { providers: Vec<String> }`
- `Disable { providers: Vec<String> }`
- `Status { providers: Vec<String> }`
- `Exec { provider, argv }` (unchanged)

Remove old subcommands from parser and handlers:
- `install`
- `uninstall`
- `list`

### 2) Shim provider semantics
Provider resolution remains:
- explicit args: deduped in argument order
- no args: all providers in `config.providers`

`enable` reuses current install semantics:
- provider validation
- trust-policy checks
- preflight conflict checks
- atomic shim write behavior with rollback on write failure
- PATH precedence diagnostics

`disable` reuses current uninstall semantics:
- remove only Lux-managed shims
- do not remove non-Lux binaries

### 3) Shell PATH block management
Add a managed PATH block with stable markers:
- begin marker: `# >>> lux-shim-path >>>`
- end marker: `# <<< lux-shim-path <<<`

Rendered block prepends `shims.bin_dir` with duplicate guard using exact
string equality (not glob pattern matching):

```sh
# >>> lux-shim-path >>>
_lux_shim_dir="<shims_bin_dir>"
_lux_has_dir=false
IFS=:
for _lux_path_entry in $PATH; do
  if [ "$_lux_path_entry" = "$_lux_shim_dir" ]; then
    _lux_has_dir=true
    break
  fi
done
unset IFS
if [ "$_lux_has_dir" != "true" ]; then
  export PATH="$_lux_shim_dir:$PATH"
fi
unset _lux_path_entry _lux_has_dir _lux_shim_dir
# <<< lux-shim-path <<<
```

`shims.bin_dir` source-of-truth:
- resolved from `config.shims.bin_dir` on each command invocation
- default is `<trusted_root>/bin` (for example `/Users/Shared/Lux/bin` on macOS)
- not globally fixed forever; if config changes, `enable` rewrites managed PATH
  blocks to the current configured value

Candidate file sets (existing files only):
- Shell targeting policy:
  - does not depend on the shell currently running `lux`
  - always considers both zsh and bash file sets below
  - acts only on files that already exist
- zsh:
  - `~/.zprofile`
  - `~/.zshrc`
- bash:
  - `~/.bash_profile`
  - `~/.bash_login`
  - `~/.profile`
  - `~/.bashrc`

Persistence behavior:
- `enable`: insert or replace managed block in all existing candidate files.
- `disable`: remove managed block from all existing candidate files.
- never create missing files.

Edit behavior:
- file updates are idempotent (re-running command does not duplicate block).
- only Lux-managed marked block is touched.

### 4) Current-session activation guidance
Because `lux` cannot mutate the parent shell environment directly:
- command output includes explicit one-shot activation instructions for the
  current shell session.
- instructions show:
  - immediate apply (`export PATH=...`)
  - shell reload guidance where applicable.

### 5) Command outcome and exit semantics
`enable` and `disable` are two-phase operations:
1. shim phase
2. PATH file phase

Deterministic rules:
- If shim phase fails:
  - command exits non-zero
  - PATH file phase is not attempted
- PATH file phase is transactional across targeted existing files:
  - either all targeted files are updated
  - or all files are restored to pre-command contents
- If shim phase succeeds and PATH file phase fails on any targeted existing
  file:
  - command exits non-zero
  - JSON error envelope remains standard (`ok=false`, `result=null`)
  - partial outcome is reported in `error_details.partial_outcome`
  - path block changes are rolled back (`path.rolled_back=true`)
- If no startup files exist:
  - command exits zero
  - output sets `path.state=no_startup_files`
- If both phases succeed:
  - command exits zero

### 6) `status` summary model
`status` computes summary over targeted providers:
- `enabled`: all targeted providers installed and `path_precedence_ok=true`
- `disabled`: none targeted providers installed
- `degraded`: any mixed/partial condition (including precedence mismatch)

`status` also reports PATH persistence state:
- `configured`: Lux PATH block present in all existing candidate files
- `partial`: Lux PATH block present in some existing candidate files
- `absent`: Lux PATH block present in none of the existing candidate files
- `no_startup_files`: no candidate startup files exist on host

### 7) Docs/help/setup alignment
Update all user-facing references to old commands:
- `lux setup` next steps
- `README.md`
- `docs/contracts/cli.md`
- `docs/contracts/install.md`
- any related tests/docs that mention old subcommands

## Data / Schema Changes
No evidence/log schema changes.

CLI JSON response shape changes for shim commands.

`enable` result fragment:

```json
{
  "action": "shim_enable",
  "providers": ["codex", "claude"],
  "shim": {
    "ok": true,
    "rows": [
      { "provider": "codex", "path": "/Users/Shared/Lux/bin/codex", "changed": true },
      { "provider": "claude", "path": "/Users/Shared/Lux/bin/claude", "changed": true }
    ]
  },
  "path": {
    "ok": true,
    "state": "configured",
    "files": [
      { "path": "~/.zprofile", "existed": true, "managed_block_present": true, "changed": true },
      { "path": "~/.zshrc", "existed": true, "managed_block_present": true, "changed": false }
    ]
  },
  "warnings": [],
  "errors": []
}
```

`disable` result fragment:

```json
{
  "action": "shim_disable",
  "providers": ["codex", "claude"],
  "shim": {
    "ok": true,
    "rows": [
      { "provider": "codex", "path": "/Users/Shared/Lux/bin/codex", "changed": true },
      { "provider": "claude", "path": "/Users/Shared/Lux/bin/claude", "changed": true }
    ]
  },
  "path": {
    "ok": true,
    "state": "absent",
    "files": [
      { "path": "~/.zprofile", "existed": true, "managed_block_present": false, "changed": true }
    ]
  },
  "warnings": [],
  "errors": []
}
```

`status` result fragment:

```json
{
  "action": "shim_status",
  "providers": ["codex", "claude"],
  "state": "enabled",
  "shims": [
    {
      "provider": "codex",
      "path": "/Users/Shared/Lux/bin/codex",
      "installed": true,
      "path_safe": true,
      "path_precedence_ok": true,
      "resolved_candidates": ["/Users/Shared/Lux/bin/codex", "/usr/local/bin/codex"]
    }
  ],
  "path_persistence": {
    "state": "configured",
    "files": [
      { "path": "~/.zprofile", "existed": true, "managed_block_present": true }
    ]
  }
}
```

Required enums:
- shim summary state: `enabled | disabled | degraded`
- path persistence state: `configured | partial | absent | no_startup_files`

Failure envelope for PATH-phase failure (non-zero):

```json
{
  "ok": false,
  "result": null,
  "error": "process error: ...",
  "error_details": {
    "error_code": "shim_path_mutation_failed",
    "hint": "Fix shell startup file permissions and retry `lux shim enable`.",
    "partial_outcome": {
      "action": "shim_enable",
      "providers": ["codex"],
      "shim": { "ok": true },
      "path": {
        "ok": false,
        "rolled_back": true,
        "state": "absent",
        "files": [
          { "path": "~/.zprofile", "existed": true, "changed": false, "error": "permission denied" }
        ]
      }
    }
  }
}
```

## Security / Trust Model
- No change to evidence integrity invariants.
- Existing shim trust-path policy remains enforced.
- PATH persistence edits are constrained to user-owned shell startup files and
  only within managed marker boundaries.
- No automatic creation of shell files reduces risk of unexpected host config
  mutation.

## Failure Modes
- Provider not configured:
  - command fails with actionable config error.
- Shim path violates trust policy:
  - command fails before mutation.
- Existing startup file is unreadable/unwritable:
  - command reports file-specific error.
  - if reached after shim success, command exits non-zero with partial outcome
    under `error_details.partial_outcome` and transactional rollback.
- No startup files exist:
  - command succeeds with explicit manual PATH guidance and
    `path.state=no_startup_files`; no files created.
- PATH precedence not first after enable:
  - status reports `degraded`; command emits remediation guidance.

## Acceptance Criteria
- `lux shim enable|disable|status` are the only non-exec shim subcommands.
- Old subcommands (`install|uninstall|list`) are absent from command surface and
  docs.
- `enable` and `disable` preserve existing shim safety semantics (Lux-managed
  writes/removals only, provider validation, trust policy checks).
- `enable` and `disable` follow explicit two-phase exit semantics:
  - shim failure => non-zero and no PATH mutation attempt
  - PATH mutation error on existing files => non-zero with `result=null`,
    partial outcome in `error_details.partial_outcome`, and rollback applied
  - no startup files => zero with `no_startup_files` state
- PATH file mutation is all-or-nothing across targeted existing files.
- PATH marker block is inserted/removed idempotently in existing zsh/bash
  startup files.
- Missing startup files are never created by Lux.
- `status` includes top-level summary state and per-provider rows.
- `status` includes PATH persistence coverage over managed shell files.
- `status` reports `no_startup_files` distinctly from `configured`.
- Setup/help/install docs and next-step output reference only new shim verbs.
- JSON output for `enable`, `disable`, and `status` includes required fields and
  enums defined in this spec.
- Failure JSON envelope remains consistent with CLI contract (`ok=false`,
  `result=null`) while carrying partial outcome in `error_details`.
- Canonical repository test lanes pass:
  - `uv run python scripts/all_tests.py --lane fast`
  - `uv run python scripts/all_tests.py --lane pr`
  - `uv run python scripts/all_tests.py --lane full`

## Test Plan
- Unit tests (`lux/src/main.rs`):
  - shell startup file selection logic (host-wide existing-file behavior across
    zsh and bash sets)
  - marker block render/insert/replace/remove idempotence
  - summary state computation (`enabled|disabled|degraded`)
  - PATH persistence state computation (`configured|partial|absent|no_startup_files`)
  - phase outcome computation and exit-status mapping for shim/path errors
  - transactional rollback semantics for PATH phase failure
  - non-zero JSON error envelope with `result=null` + `error_details.partial_outcome`
- CLI tests (`lux/tests/cli.rs`):
  - `enable -> status -> disable` roundtrip
  - no-provider defaults use configured providers
  - missing shell files are not created
  - zero-startup-file case returns `path.state=no_startup_files`
  - existing files are updated and cleaned correctly
  - path mutation failure on existing file returns non-zero with partial outcome
  - old subcommands rejected
- Integration coverage (`tests/integration/`):
  - setup output references `lux shim enable`
  - install quick-start contract and CLI help examples align with new commands
- Regression tests:
  - prevent reintroduction of old shim subcommands
  - prevent shell file auto-creation behavior

## Rollout
1. Update CLI parser and handlers for new shim subcommands.
2. Add shell PATH block management helpers and status reporting.
3. Update setup/help/docs/tests to new command contract.
4. Run canonical verification lanes after targeted tests pass.

Verification policy:
- Canonical lanes (`fast`, `pr`, `full`) are required.
- If a lane fails for a demonstrably unrelated reason, record evidence and keep
  shim-targeted tests green before merge approval.

## Open Questions
- None for draft review.

## Alternatives Considered
- Keep old commands with aliases:
  - rejected; command surface stays intent-first with a hard break.
- Manage only zsh profiles:
  - rejected; bash users need first-class support.
- Edit exactly one startup file:
  - rejected; login vs interactive shell differences cause inconsistent behavior.
- Create missing shell files automatically:
  - rejected by product scope for this change.
