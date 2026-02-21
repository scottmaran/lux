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
  - persists PATH block in existing zsh/bash startup files
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

Rendered block prepends `shims.bin_dir` with duplicate guard:

```sh
# >>> lux-shim-path >>>
case ":$PATH:" in
  *":<shims_bin_dir>:"*) ;;
  *) export PATH="<shims_bin_dir>:$PATH" ;;
esac
# <<< lux-shim-path <<<
```

Candidate file sets (existing files only):
- zsh:
  - `~/.zprofile`
  - `~/.zshrc`
- bash:
  - login file: first existing of `~/.bash_profile`, `~/.bash_login`, `~/.profile`
  - interactive file: `~/.bashrc` (if exists)

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
- instructions are shell-specific and show:
  - apply (`export PATH=...`)
  - or refresh startup files (`source ...`) if user prefers.

### 5) `status` summary model
`status` computes summary over targeted providers:
- `enabled`: all targeted providers installed and `path_precedence_ok=true`
- `disabled`: none targeted providers installed
- `degraded`: any mixed/partial condition (including precedence mismatch)

`status` also reports PATH persistence state:
- `configured`: Lux PATH block present in all existing candidate files
- `partial`: Lux PATH block present in some existing candidate files
- `absent`: Lux PATH block present in none of the existing candidate files

### 6) Docs/help/setup alignment
Update all user-facing references to old commands:
- `lux setup` next steps
- `README.md`
- `docs/contracts/cli.md`
- `docs/contracts/install.md`
- any related tests/docs that mention old subcommands

## Data / Schema Changes
No evidence/log schema changes.

CLI JSON response shape changes for shim commands:
- `enable` response replaces old `installed` naming with `enabled` payload.
- `disable` response replaces old `removed` naming with `disabled` payload.
- `status` response adds:
  - top-level `state`
  - top-level `path_persistence`
  - per-file PATH block status details

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
  - command reports file-specific warning/error and continues for other files.
- No startup files exist:
  - command succeeds with explicit manual PATH guidance; no files created.
- PATH precedence not first after enable:
  - status reports `degraded`; command emits remediation guidance.

## Acceptance Criteria
- `lux shim enable|disable|status` are the only non-exec shim subcommands.
- Old subcommands (`install|uninstall|list`) are absent from command surface and
  docs.
- `enable` and `disable` preserve existing shim safety semantics (Lux-managed
  writes/removals only, provider validation, trust policy checks).
- PATH marker block is inserted/removed idempotently in existing zsh/bash
  startup files.
- Missing startup files are never created by Lux.
- `status` includes top-level summary state and per-provider rows.
- `status` includes PATH persistence coverage over managed shell files.
- Setup/help/install docs and next-step output reference only new shim verbs.
- Canonical repository test lanes pass:
  - `uv run python scripts/all_tests.py --lane fast`
  - `uv run python scripts/all_tests.py --lane pr`
  - `uv run python scripts/all_tests.py --lane full`

## Test Plan
- Unit tests (`lux/src/main.rs`):
  - shell startup file selection logic (existing-only behavior)
  - marker block render/insert/replace/remove idempotence
  - summary state computation (`enabled|disabled|degraded`)
  - PATH persistence state computation (`configured|partial|absent`)
- CLI tests (`lux/tests/cli.rs`):
  - `enable -> status -> disable` roundtrip
  - no-provider defaults use configured providers
  - missing shell files are not created
  - existing files are updated and cleaned correctly
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
