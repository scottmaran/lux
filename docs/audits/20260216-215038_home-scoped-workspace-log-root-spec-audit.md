# Audit: Home-Scoped Workspace / External Log Root Spec Readiness

ID: 20260216-215038
Date: 2026-02-16
Owner: codex
Scope: `docs/specs/home-scoped-workspace-log-root.md` correctness, contract consistency, and implementation readiness against current repo behavior.

## Summary
The spec is directionally strong but **not implementation-ready yet**. It contains several ambiguities and a few contract mismatches that can cause incorrect implementation choices, broken auth/runtime behavior, and large avoidable test churn.

Highest-risk gaps are:
- mount model statements that conflict with required runtime mounts,
- undefined semantics for new `--workspace` / `--start-dir` flags,
- no explicit rule to keep collector/provider workspace consistent across a run.

## Method
- Reviewed the spec: `docs/specs/home-scoped-workspace-log-root.md`.
- Cross-checked CLI/runtime implementation in `lasso/src/main.rs`, compose wiring in `compose.yml`, harness behavior in `harness/harness.py`, and installer behavior in `install_lasso.sh`.
- Cross-checked current contracts and tests:
  - `docs/contracts/cli.md`, `docs/contracts/config.md`, `docs/contracts/harness_api.md`, `docs/contracts/install.md`, `docs/contracts/platform.md`
  - `tests/README.md`, `tests/unit/test_compose_contract_parity.py`, `tests/integration/test_cli_*`, `lasso/tests/cli.rs`

## Findings
### Finding: Agent mount model in spec conflicts with required runtime/auth mounts
Severity: high
Evidence:
- Spec says agent sees only workspace + `/logs` (`docs/specs/home-scoped-workspace-log-root.md:31`, `docs/specs/home-scoped-workspace-log-root.md:79`).
- Base compose also requires `/config` mount for SSH key exchange (`compose.yml:36`, `compose.yml:48`).
- Provider runtime overrides add extra read-only mounts for auth/state (`lasso/src/main.rs:2800`, `lasso/src/main.rs:2838`).
- Unit contract parity enforces `/config` mount on agent (`tests/unit/test_compose_contract_parity.py:107`).

Impact:
- A literal implementation of this spec can remove required mounts and break provider-plane startup/auth.
- Acceptance criteria become impossible to satisfy without violating existing contracts.

Recommendation:
- Update spec wording to distinguish:
  - required baseline mounts (`/work`, `/logs:ro`, `/config:ro`), and
  - provider-specific read-only auth/state mounts.
- Keep invariant-oriented restriction as: agent must not get write access to evidence sink.

### Finding: New CLI override contract is under-specified and conflicts with existing `run --cwd` behavior
Severity: high
Evidence:
- Spec introduces `--workspace` and `--start-dir` but does not define command scope (`docs/specs/home-scoped-workspace-log-root.md:32`).
- Current CLI has no such flags; existing `run` already exposes `--cwd` (`lasso/src/main.rs:94`, `docs/contracts/cli.md:80`).
- Spec claims CLI precedence over config for `start-dir` though config has no `start_dir` field (`docs/specs/home-scoped-workspace-log-root.md:58`, `docs/contracts/config.md:24`).

Impact:
- Implementers must guess whether flags are global, `up`-only, `run`/`tui`-only, or replacements for `--cwd`.
- Risk of contradictory UX and docs drift.

Recommendation:
- Explicitly define:
  - which commands accept `--workspace` and `--start-dir`,
  - whether `--cwd` is kept, aliased, or deprecated,
  - whether `start_dir` is persisted in config (if yes, update config contract/schema docs).

### Finding: Workspace override can desynchronize collector vs provider observation boundary
Severity: high
Evidence:
- Collector and provider are started in separate phases (`lasso/src/main.rs:3151`, `lasso/src/main.rs:3186`).
- Runtime compose env overrides currently only carry `LASSO_RUN_ID` (`lasso/src/main.rs:2934`).
- Active run state stores only run id/time, not effective workspace/start-dir (`lasso/src/main.rs:499`).
- Compose base args reuse existing env file unless missing (`lasso/src/main.rs:2631`).

Impact:
- If `--workspace` differs across `up --collector-only` and `up --provider`, collector may observe a different mounted path than where agent executes.
- This can violate evidence completeness expectations.

Recommendation:
- Add explicit run-consistency rules:
  - freeze effective workspace/start-dir at collector-start time,
  - persist them in active run state,
  - reject later provider-up overrides that differ.
- Define how overrides are injected (compose env overrides vs config/env-file mutation) so behavior is deterministic.

### Finding: “Setup + config init aligned” scope is incomplete
Severity: medium
Evidence:
- Spec scope names `setup` and `config init` (`docs/specs/home-scoped-workspace-log-root.md:19`, `docs/specs/home-scoped-workspace-log-root.md:41`).
- Other config creation flows still use static default YAML:
  - `config edit` when file missing (`lasso/src/main.rs:1593`)
  - `setup` when config missing (`lasso/src/main.rs:938`)
  - installer copies bundled `default.yaml` (`install_lasso.sh:173`)
  - `Config::default()` still old defaults (`lasso/src/main.rs:333`).

Impact:
- User-visible defaults will diverge by entrypoint (`install`, `config edit`, missing-config paths).

Recommendation:
- Decide and state single source-of-truth for runtime defaults, and enumerate all callsites that must use it.

### Finding: Path validation behavior is not concrete enough for safe implementation
Severity: medium
Evidence:
- Spec asks for “realpath descendant/containment checks” (`docs/specs/home-scoped-workspace-log-root.md:45`).
- Current path handling only expands `~/` and allows non-existent targets (`lasso/src/main.rs:818`, `lasso/src/main.rs:1641`).

Impact:
- Non-existent paths, symlink escapes, relative paths, and missing `HOME` can produce inconsistent behavior across commands.

Recommendation:
- Specify canonicalization algorithm explicitly:
  - expand `~`,
  - require absolute paths,
  - canonicalize nearest existing parent + tail,
  - reject symlink escapes,
  - define error when `HOME` is unset/unresolvable.

### Finding: Hard-error expectation for invalid start directory conflicts with harness API contract
Severity: medium
Evidence:
- Spec requires hard errors for invalid start-dir (`docs/specs/home-scoped-workspace-log-root.md:71`).
- Harness currently sanitizes invalid `cwd` to default rather than failing (`harness/harness.py:106`, `harness/harness.py:469`).
- Contract explicitly documents this fallback (`docs/contracts/harness_api.md:22`).

Impact:
- Without explicit decision, behavior will diverge between CLI and direct harness API flows.

Recommendation:
- Pick one and encode in spec/tests:
  - keep harness fallback, enforce hard errors only in `lasso` CLI, or
  - change harness API to hard-fail invalid cwd and update API contract/tests.

### Finding: Test plan does not match repository test taxonomy and misses required test migration scope
Severity: medium
Evidence:
- Spec proposes “fixture cases” for OS defaults (`docs/specs/home-scoped-workspace-log-root.md:84`), but fixture lane is collector-pipeline golden-data scope (`tests/README.md:43`).
- Many CLI tests currently use workspace paths outside `$HOME` and would fail under new validation unless harnessed differently (`tests/integration/test_cli_config_and_doctor.py:104`, `tests/integration/test_cli_lifecycle.py:120`, `lasso/tests/cli.rs:90`).

Impact:
- Implementation will trigger broad failing tests not accounted for in spec.

Recommendation:
- Replace fixture item with Rust unit tests + CLI integration tests.
- Add explicit test migration task (HOME-controlled temp homes or home-scoped temp workspace paths).

### Finding: Unsupported-OS default behavior is unspecified
Severity: low
Evidence:
- Spec defines macOS/Linux defaults only (`docs/specs/home-scoped-workspace-log-root.md:27`).
- No fallback/error behavior is specified for other OS targets.

Impact:
- Ambiguous behavior if binary is run in unsupported environments.

Recommendation:
- Specify explicit error/fallback for unknown OS in default-path helper.

## Suggested Work Items
1. Patch the spec mount model and acceptance criteria to reflect required `/config` and provider auth mounts.
2. Add a precise CLI contract section for `--workspace`/`--start-dir` scope, precedence, and `--cwd` interaction.
3. Add run-consistency design for workspace/start-dir across collector and provider phases (state persistence + mismatch handling).
4. Expand “defaults alignment” to all config-creation entry points (including installer and missing-config edit/setup flows).
5. Add explicit path canonicalization and `HOME`-unavailable rules.
6. Decide CLI-vs-harness behavior for invalid start-dir/cwd and update contracts accordingly.
7. Rewrite test plan section to map to actual test layers and include test migration for home-scoping constraints.

## Verification Notes
- Commands used for this audit were read-only repo inspection (`rg`, `nl -ba`, `sed`) over spec/contracts/code/tests.
- No code behavior was changed.
