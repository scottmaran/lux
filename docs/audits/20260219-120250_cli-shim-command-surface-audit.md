# Audit: CLI shim command surface (codex/claude workflow)

ID: 20260219-120250
Date: 2026-02-19
Owner: codex
Scope: `lux shim install|uninstall|list|exec` implementation, related runtime wiring, and test/contracts coverage for frictionless `codex ...` / `claude ...` usage.

## Summary
The current shim implementation is close to the intended UX but has several high-impact gaps for correctness and trust. The biggest issues are: non-atomic default install behavior (can fail while mutating state), shim execution not preserving current working directory, and a trust-boundary weakness where default workspace/home layout allows agent-side shim tampering. There are also observability and coverage gaps around runtime events and PATH conflict handling.

Recommended priority order:
1. Make shim install deterministic and atomic (no partial side effects on failure).
2. Preserve caller working directory in shim execution to match normal agent CLI workflow.
3. Harden shim trust boundary and add PATH precedence checks/warnings.
4. Expand shim contract test coverage (unit + integration).

## Method
- Reviewed contracts/specs:
  - `AGENTS.md`
  - `docs/contracts/cli.md`
  - `docs/contracts/config.md`
  - `docs/specs/runtime-control-plane-and-frictionless-ux.md`
  - `INVARIANTS.md`
- Reviewed implementation:
  - `lux/src/main.rs`
  - `compose.yml`
  - `harness/harness.py`
- Reviewed tests:
  - `lux/tests/cli.rs`
  - repository-wide shim-related grep across `tests/*`
- Ran verification commands:
  - `uv run python scripts/all_tests.py --lane fast`
  - `cd lux && cargo test --test cli shim -- --nocapture`

## Findings
### Finding: `shim install` defaults are hard-coded and can fail after partial mutation
Severity: high
Evidence:
- Hard-coded default providers: `lux/src/main.rs:5531`
- Install loop writes per provider without preflight for all providers: `lux/src/main.rs:5630`, `lux/src/main.rs:5639`
- Repro (local): with config containing only `codex`, `lux shim install` exited non-zero with `provider 'claude' is not defined`, while `~/.local/bin/codex` was still created.

Impact:
- Violates predictable command semantics: command reports failure but mutates system state.
- Breaks provider-agnostic behavior when configs do not include both `codex` and `claude`.
- Increases operator confusion in setup automation.

Recommendation:
- Resolve default provider set from `config.providers.keys()` when no args are passed.
- Add a preflight phase that validates all requested providers and all overwrite conflicts before writing any shim.
- Apply writes atomically (or transactional rollback on failure).

### Finding: Shim execution does not preserve caller working directory
Severity: high
Evidence:
- `shim exec` validates host cwd is in workspace but never maps cwd into container workdir: `lux/src/main.rs:5685`, `lux/src/main.rs:5710`
- `lux tui` path does map and pass `HARNESS_AGENT_WORKDIR`: `lux/src/main.rs:6166`, `lux/src/main.rs:6179`
- Harness always executes TUI from `DEFAULT_CWD` (`HARNESS_AGENT_WORKDIR`, default `/work`): `harness/harness.py:633`

Impact:
- Diverges from expected “normal codex/claude workflow” when invoked from a subdirectory.
- Increases risk of commands running in the wrong directory/project root.

Recommendation:
- In `shim exec`, resolve host cwd relative to active workspace and pass mapped `HARNESS_AGENT_WORKDIR` exactly like `tui --start-dir` flow.
- Add tests for cwd preservation from nested workspace paths.

### Finding: Default workspace + shim location allows agent-side shim tampering
Severity: high
Evidence:
- Default workspace is `$HOME`: `lux/src/main.rs:998`, `lux/src/main.rs:1004`; contract mirror `docs/contracts/config.md:31`
- Agent/harness get workspace mount as read-write: `compose.yml:33`, `compose.yml:46`
- Shim location is under home (`~/.local/bin/<provider>`): `lux/src/main.rs:3041`, `lux/src/main.rs:5538`

Impact:
- In common default setup, in-boundary agent activity can rewrite host shim binaries.
- A tampered shim can silently bypass Lux on future launches, reducing confidence in observation completeness.

Recommendation:
- Do not place managed shims inside any configured `workspace_root`.
- Add validation/doctor checks that fail or warn when shim path is inside workspace mount scope.
- Consider immutable/signature verification of managed shim content on `shim exec` and/or `doctor`.

### Finding: PATH conflict handling is incomplete for frictionless usage
Severity: medium
Evidence:
- Spec expects PATH-conflict warning + remediation: `docs/specs/runtime-control-plane-and-frictionless-ux.md:277`
- Implementation only checks conflict at one target path (`~/.local/bin/<provider>`), no PATH-order diagnostics: `lux/src/main.rs:5632`
- Doctor checks currently do not include shim/PATH readiness: `lux/src/main.rs:6262`

Impact:
- User may run a non-Lux `codex`/`claude` binary due PATH precedence and assume Lux is observing.
- Directly harms “install once, keep using normal command” UX.

Recommendation:
- During `shim install` and `doctor`, inspect command resolution (`which -a codex`, `which -a claude`) and report whether Lux shim is first.
- Provide explicit remediation guidance for PATH ordering.

### Finding: Runtime event stream misses shim-driven lifecycle actions
Severity: medium
Evidence:
- Runtime proxy routing excludes `Commands::Shim`: `lux/src/main.rs:1188`
- Runtime lifecycle events are emitted from delegated `/v1/execute` path: `lux/src/main.rs:4511`, `lux/src/main.rs:4549`, `lux/src/main.rs:5230`
- `shim exec` runs lifecycle logic directly (`ensure_runtime_running` + `handle_up`) without runtime execute recording: `lux/src/main.rs:5694`, `lux/src/main.rs:5593`

Impact:
- Runtime event consumers (CLI/UI) can miss shim-driven `session.started/session.ended` style transitions.
- Weakens observability consistency across entry points.

Recommendation:
- Route shim lifecycle actions through runtime execute API, or emit equivalent runtime events directly in shim path.
- Add integration checks that shim launches are reflected in runtime event stream.

### Finding: Shim contract coverage is minimal relative to risk
Severity: medium
Evidence:
- Only two shim-focused tests exist: `lux/tests/cli.rs:1002`, `lux/tests/cli.rs:1061`
- No additional shim tests found in integration/regression/unit trees (repo-wide grep returned only those two test cases).

Impact:
- High-risk behavior (install atomicity, cwd semantics, PATH conflict detection, runtime event parity) can regress silently.

Recommendation:
- Add coverage for:
  - default-provider resolution from config
  - no-partial-write guarantees on install failure
  - cwd preservation for shim launches
  - provider mismatch and workspace-boundary failures
  - runtime event emission parity for shim-triggered lifecycle
  - PATH precedence readiness/doctor checks

## Suggested Work Items
- Implement atomic `shim install` with config-derived provider defaults and full preflight validation.
- Add cwd mapping in `shim exec` (host cwd -> `/work` relative) and pass `HARNESS_AGENT_WORKDIR`.
- Add shim trust-boundary guardrails (no shim path inside workspace root; integrity verification check).
- Add PATH precedence diagnostics to `shim install` + `lux doctor`.
- Unify runtime event reporting so shim-driven flows appear in `/v1/events`.
- Expand shim tests in both `lux/tests/cli.rs` and integration lanes.

## Verification Notes
- `uv run python scripts/all_tests.py --lane fast`
  - Result: PASS (`57` unit/fixture tests + `6` regression tests in this run)
- `cd lux && cargo test --test cli shim -- --nocapture`
  - Result: PASS (`2` shim tests)
