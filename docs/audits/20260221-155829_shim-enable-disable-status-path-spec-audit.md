# Audit: Shim Enable/Disable/Status PATH Spec Review

ID: 20260221-155829
Date: 2026-02-21
Owner: codex
Scope: `docs/specs/shim-enable-disable-status-path-management.md` consistency, correctness, and alignment with existing Lux CLI contracts/implementation.

## Summary
The spec direction is strong and aligned with requested UX (intent-first shim commands, hard break, no shell-file creation), but it still has several implementation-critical ambiguities. The highest-risk gaps are shell target selection and command failure semantics for shell-file mutation errors. These should be resolved in the spec before implementation to avoid divergent behavior and flaky acceptance outcomes.

## Method
- Reviewed the draft spec:
  - `docs/specs/shim-enable-disable-status-path-management.md`
- Cross-checked current command surface and shim behavior:
  - `lux/src/main.rs`
  - `lux/tests/cli.rs`
- Cross-checked user-facing contracts that will be impacted:
  - `docs/contracts/cli.md`
  - `docs/contracts/install.md`
  - `README.md`
- Cross-checked repository test-lane reliability notes from prior implemented spec:
  - `docs/specs/trusted-filesystem-layout-and-shim-root-hardening.md`

## Findings
### Finding: Shell target selection policy is undefined
Severity: high
Evidence:
- Spec requires zsh and bash support: `docs/specs/shim-enable-disable-status-path-management.md:30`
- Candidate file sets are listed for both shells: `docs/specs/shim-enable-disable-status-path-management.md:108`
- Persistence says update “all existing candidate files” without defining shell selection rules: `docs/specs/shim-enable-disable-status-path-management.md:116`
- No open questions remain despite this unresolved behavior: `docs/specs/shim-enable-disable-status-path-management.md:225`

Impact:
- Different implementations could choose “current shell only”, “both families always”, or “heuristic by `$SHELL`”.
- Risk of surprising host config edits and inconsistent `status` reporting across environments.

Recommendation:
- Add an explicit shell-selection contract (for example):
  - default behavior (auto or all)
  - exact selection algorithm
  - behavior when shell detection is unavailable
- Add acceptance criteria and tests for that selection behavior.

### Finding: Exit semantics for shell-file write/remove failures are ambiguous
Severity: high
Evidence:
- Failure mode says “warning/error and continues” but does not define final exit status: `docs/specs/shim-enable-disable-status-path-management.md:176`
- Existing shim IO behavior is fail-fast for write/remove failures in current implementation:
  - write/create errors fail command: `lux/src/main.rs:6118`
  - remove errors fail command: `lux/src/main.rs:6188`

Impact:
- Automation cannot rely on deterministic success/failure for `enable`/`disable`.
- Users may believe shim/PATH state is fully applied when only partially updated.

Recommendation:
- Define deterministic command outcome policy:
  - either fail non-zero on any shell-file mutation error, or
  - succeed with explicit partial status and machine-readable `warnings/errors`.
- Define required JSON fields for per-file results and final command status.

### Finding: `path_persistence` state is logically ambiguous when zero startup files exist
Severity: medium
Evidence:
- Spec states no file creation and success when no startup files exist: `docs/specs/shim-enable-disable-status-path-management.md:59`
- `configured` is defined as block present in “all existing candidate files”: `docs/specs/shim-enable-disable-status-path-management.md:140`

Impact:
- With zero existing files, “all existing files” can evaluate true (vacuous truth), causing incorrect `configured` status while nothing is persisted.

Recommendation:
- Add an explicit zero-file state (for example `no_startup_files`), and require `status` to report that distinctly from `configured`.
- Add dedicated unit/CLI tests for zero-file state.

### Finding: JSON contract for new shim commands is under-specified
Severity: medium
Evidence:
- Spec only describes payload renaming at a high level: `docs/specs/shim-enable-disable-status-path-management.md:155`
- No required fields/types for top-level `state`, `path_persistence`, per-provider rows, or per-file rows.

Impact:
- Contract/docs/tests can drift; integration consumers may break across implementations.

Recommendation:
- Define exact response schema fragments in the spec (required fields, types, enum values).
- Mirror these in `docs/contracts/cli.md` during implementation.

### Finding: “All lanes must pass” acceptance is valid but operationally brittle without scoped fallback guidance
Severity: medium
Evidence:
- Draft requires all canonical lanes pass: `docs/specs/shim-enable-disable-status-path-management.md:195`
- Prior implemented spec documents known unrelated/intermittent failures in these lanes:
  - `docs/specs/trusted-filesystem-layout-and-shim-root-hardening.md:285`

Impact:
- Implementation sign-off may be blocked by unrelated environmental failures, reducing signal for this feature.

Recommendation:
- Keep canonical lane requirement if desired, but add explicit verification policy for unrelated failures:
  - targeted shim tests must pass
  - full lanes required unless failure is demonstrably unrelated and documented with evidence.

## Suggested Work Items
- Amend spec to define shell selection algorithm and zero-file status.
- Amend spec to define deterministic exit/error semantics for partial shell-file mutation outcomes.
- Add concrete JSON response schemas for `enable`, `disable`, and `status`.
- Add verification policy text for handling unrelated lane failures while preserving strict quality bar.

## Verification Notes
- Reviewed files/lines via:
  - `nl -ba docs/specs/shim-enable-disable-status-path-management.md | sed -n '1,320p'`
  - `nl -ba lux/src/main.rs | sed -n '6079,6218p'`
  - `nl -ba lux/src/main.rs | sed -n '228,246p'`
  - `nl -ba docs/contracts/cli.md | sed -n '96,170p'`
  - `nl -ba docs/contracts/install.md | sed -n '138,147p'`
  - `nl -ba README.md | sed -n '30,50p'`
  - `nl -ba lux/tests/cli.rs | sed -n '1004,1072p'`
  - `nl -ba docs/specs/trusted-filesystem-layout-and-shim-root-hardening.md | sed -n '280,292p'`
