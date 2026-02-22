# Spec: Setup Wizard Shims Step And Optional Safer Auto-Start

Status: draft
Owner: codex
Created: 2026-02-21
Last updated: 2026-02-22

## Problem
`lux setup` currently leaves critical workflow steps as manual follow-ups, especially:
- enabling shims for normal provider CLI usage
- starting runtime services needed for immediate workflow use

This creates avoidable friction and ambiguity. Users finish setup but still need to infer what to run next.

At the same time, auto-starting the full stack is not a safe default because Lux supports only one active provider plane at a time.

## Goals
- Add an explicit interactive setup step for shim enablement.
- Add an explicit interactive setup option to auto-start services.
- Use safer auto-start mode: start collector + UI, not provider plane.
- Keep `lux setup --defaults` non-interactive behavior deterministic with auto-start disabled by default.
- Make setup exit non-zero when post-setup startup fails, while preserving already-written config/secrets changes.
- Refactor setup flow into maintainable, testable phases (structured refactor).
- Align CLI help and docs so setup explains how Lux works and what was started.

## Non-Goals
- Auto-starting provider plane containers (`agent` + `harness`).
- Supporting multiple active provider planes.
- Changing evidence schemas or attribution invariants.
- Adding Windows-only shim or startup behavior in this change.

## User Experience
Interactive `lux setup` wizard moves from 4 steps to 6 steps:
1. Paths
2. Provider Auth
3. Secrets
4. Shims
5. Startup
6. Review

### New Shims Step
Prompt offers:
- Enable shims for all configured providers (default)
- Select specific providers
- Skip shim enable for now

Review step includes the chosen shim action before final confirmation.

### New Startup Step
Prompt offers:
- Auto-start now (safer mode) (default)
- Do not auto-start

When selected, safer mode refreshes startup services so they reflect updated config:
- collector refresh:
  - stop existing collector if running
  - `lux up --collector-only --wait --pull missing`
- UI ensure-up:
  - `lux ui up --wait --pull missing`

Provider plane is not started.

### `--defaults` behavior
- No interactive prompts.
- Auto-start is disabled by default.
- Existing defaults-mode setup behavior remains otherwise unchanged.

### Final setup messaging
- If auto-start selected and successful, setup states collector/UI are running and tells user to launch their provider CLI (`codex`, `claude`, etc.).
- If auto-start not selected, setup prints explicit next steps.

## Design

### 1) Structured setup refactor
Refactor `handle_setup` into explicit phases with clear boundaries:
- collect/setup decision phase
- review/confirm phase
- apply config/secrets phase
- post-setup action phase
- final guidance phase

Introduce setup-scoped structs/enums for decisions and post-setup actions so behavior is testable without terminal I/O.

### 2) Shim decision model
Represent shim decision as an explicit setup action intent:
- enable all configured providers
- enable selected providers
- skip

If shim enable is requested, execute the equivalent of `lux shim enable [providers...]` during post-setup actions.

Zero-provider behavior matches existing shim contract:
- if no providers are configured and shim enable is selected, setup surfaces the same shim error (`no providers configured for shim enable`) and exits non-zero.

### 3) Startup decision model
Represent startup decision as explicit setup intent:
- safer auto-start (collector + UI)
- no auto-start

Startup actions run only when all are true:
- interactive mode
- `apply=true` (`--no-apply` and `--dry-run` disable startup actions)
- user selected auto-start

### 4) Post-setup action execution order
After config/secrets write and config apply succeed, run actions in this order:
1. optional shim enable
2. optional startup preflight for safer auto-start
3. optional collector refresh startup
4. optional UI startup

Execution is deterministic and stop-on-error:
- if shim enable fails, setup exits non-zero and startup actions are not attempted
- if provider plane is active, safer auto-start fails with actionable guidance (do not mutate provider plane from setup)
- if collector stop/start fails, UI startup is not attempted
- if UI startup fails, setup exits with failure

Startup preflight behavior:
- setup checks provider-plane activity before collector refresh
- setup does not auto-stop provider plane to make collector refresh succeed
- user must stop provider plane explicitly when setup reports this conflict

Collector refresh behavior:
- if collector is running, setup stops collector first
- setup then starts collector via `lux up --collector-only --wait --pull missing`
- this ensures collector startup reflects newly applied config

### 5) Failure semantics and persistence
If any post-setup startup action fails:
- `lux setup` exits non-zero
- config/secrets changes already written remain in place (no rollback)
- failure output includes actionable retry guidance

This preserves user-confirmed configuration while accurately signaling runtime startup failure.

### 6) Help/docs alignment
Update command docs/help text to reflect:
- setup now includes optional shim setup
- setup now includes optional safer auto-start
- safer auto-start starts collector + UI only

## Data / Schema Changes
No evidence/log schema changes.

CLI setup contract changes:
- Interactive setup flow includes new `Shims` and `Startup` steps.
- Setup runtime behavior may now include optional post-setup actions.

No change to collector/harness artifact layout.

## Security / Trust Model
No change to core trust boundaries:
- Lux remains responsible for lifecycle and observability control-plane operations.
- Agent cooperation is still not required.
- No new agent write permissions are introduced.

Starting collector/UI during setup does not weaken attribution or log integrity invariants.

## Failure Modes
- Shim enable fails during post-setup actions:
  - setup exits non-zero
  - config/secrets remain persisted
  - collector/UI auto-start actions are not attempted
- No providers configured but shim enable selected:
  - setup exits non-zero with existing shim error semantics
  - config/secrets remain persisted
- Provider plane active during safer auto-start:
  - setup exits non-zero with guidance to stop provider plane first
  - collector/UI refresh actions are not attempted
- Collector startup fails:
  - setup exits non-zero
  - UI startup is not attempted
  - config/secrets remain persisted
- UI startup fails:
  - setup exits non-zero
  - collector may already be running
  - config/secrets remain persisted
- `--defaults` mode:
  - no startup actions attempted by default
- `--dry-run` or `--no-apply`:
  - no post-setup startup actions attempted

## Acceptance Criteria
- Interactive setup includes explicit `Shims` and `Startup` steps.
- Shims step supports enable-all, select-subset, and skip behavior.
- Startup step supports optional safer auto-start (collector + UI only).
- Provider plane is never auto-started by setup.
- `lux setup --defaults` does not auto-start collector/UI by default.
- If safer auto-start is selected and collector is already running, setup stops and restarts collector so startup reflects newly applied config.
- If provider plane is active, setup auto-start path exits non-zero with actionable guidance (no implicit provider shutdown).
- If collector or UI startup fails during setup auto-start, setup exits non-zero and prior config/secrets writes remain.
- If shim enable fails (including zero-provider edge case), setup exits non-zero and does not continue to collector/UI startup.
- Setup output clearly states what was started and what remains for user action.
- `lux --help`, `lux setup --help`, and related docs reflect new setup behavior.
- Implementation passes all repository tests.

## Test Plan
- Unit tests:
  - setup decision planning for interactive and defaults modes
  - shim/startup action sequencing
  - startup stop-on-error behavior
  - persistence-on-failure behavior for setup apply + post actions
- Fixture cases:
  - none required (no collector data-shape changes)
- Integration coverage:
  - setup defaults mode confirms no auto-start side effects
  - lifecycle verification for collector/UI refresh started by setup auto-start path
  - preflight conflict case when provider plane is active
  - zero-provider shim-enable failure behavior in setup path
  - failure-path integration asserting non-zero exit with persisted config
- Regression tests:
  - prevent reintroduction of ambiguous setup-complete messaging when services are not started
- Manual verification:
  - interactive setup with auto-start enabled and disabled
  - interactive setup with shim enable all, subset, and skip
  - run full test suite (`uv run python scripts/all_tests.py --lane full`)

## Rollout
- Update docs and help text in the same change as implementation.
- No backward-compatibility guarantees required (stealth phase), but tests/docs must be updated atomically with behavior.
- Existing users may observe setup now optionally starting collector/UI; this is user-selected in interactive mode and off by default in `--defaults`.

## Open Questions
- None.
