# Audit: Setup Wizard Shims + Safer Auto-Start Spec Review

ID: 20260221-225854
Date: 2026-02-21
Owner: codex
Scope: `docs/specs/setup-wizard-shims-and-safer-autostart.md`

## Summary
The spec is directionally strong and matches the requested feature set, but there are a few implementation-critical ambiguities that should be resolved before coding. The highest-risk issue is startup behavior when collector/provider state already exists.

## Method
- Reviewed the spec line-by-line with line numbers.
- Cross-checked against current CLI contract behavior in `docs/contracts/cli.md`.
- Checked for contradictions between UX, design, failure modes, and acceptance criteria.

## Findings

### Finding: Auto-start flow does not define behavior when stack already has active services
Severity: high
Evidence: `docs/specs/setup-wizard-shims-and-safer-autostart.md:55`, `docs/specs/setup-wizard-shims-and-safer-autostart.md:100`, `docs/contracts/cli.md:84`, `docs/contracts/cli.md:90`

Impact:
- Spec currently states setup should run `lux up --collector-only` during auto-start.
- Existing CLI contract can fail `up --collector-only` when collector or provider plane is already running.
- This can produce frequent non-zero setup exits in non-fresh environments, even when startup is effectively already satisfied.

Recommendation:
- Add explicit preflight semantics in spec:
  - If collector is already running, treat collector startup as satisfied (skip, do not fail).
  - If provider plane is already running, do not force a new collector run; keep provider plane untouched and proceed with UI step.
  - Record skipped/satisfied status in setup output.

### Finding: Startup option wording is internally inconsistent ("opt-in" vs default-yes)
Severity: medium
Evidence: `docs/specs/setup-wizard-shims-and-safer-autostart.md:51`, `docs/specs/setup-wizard-shims-and-safer-autostart.md:161`

Impact:
- UX section says auto-start is default-selected (`default` at prompt).
- Acceptance criteria says "opt-in safer auto-start," which implies default-no.
- This can lead to incorrect implementation and test expectations.

Recommendation:
- Replace "opt-in" wording with "optional" (or change interactive default to no).
- Keep one unambiguous contract for implementation and tests.

### Finding: Shim failure semantics are only partially specified and conflict in phrasing
Severity: medium
Evidence: `docs/specs/setup-wizard-shims-and-safer-autostart.md:105`, `docs/specs/setup-wizard-shims-and-safer-autostart.md:141`

Impact:
- Design says stop-on-error for "startup operations" (collector/UI), but shim execution occurs before startup and failure behavior is only implied later.
- Implementers may disagree on whether shim failure should block collector/UI startup or be downgraded to warning.

Recommendation:
- Add explicit rule in Design section:
  - whether shim failure is fatal for setup exit code
  - whether collector/UI actions should continue or be skipped after shim failure
- Keep this aligned with Failure Modes and Acceptance Criteria.

### Finding: No-provider edge case for default shim action is unspecified
Severity: medium
Evidence: `docs/specs/setup-wizard-shims-and-safer-autostart.md:43`, `docs/specs/setup-wizard-shims-and-safer-autostart.md:87`

Impact:
- Default behavior is "enable all providers," but config may legally have zero providers.
- Without explicit handling, setup may fail unexpectedly when trying to enable shims for an empty provider set.

Recommendation:
- Define zero-provider behavior explicitly:
  - auto-convert shim action to skip with warning, or
  - treat as no-op success.

### Finding: Spec metadata date likely stale for this review iteration
Severity: low
Evidence: `docs/specs/setup-wizard-shims-and-safer-autostart.md:6`

Impact:
- Minor traceability mismatch between edit/review time and recorded metadata.

Recommendation:
- Update `Last updated` on next spec revision commit.

## Suggested Work Items
- Add a "Service State Preflight" subsection to Design defining idempotent auto-start semantics when collector/provider/UI are already running.
- Resolve startup prompt default wording mismatch (`optional` vs `opt-in`).
- Add one explicit rule sentence for shim failure policy in execution order.
- Add zero-provider shim behavior to UX + acceptance criteria.
- Update spec metadata date on revision.

## Verification Notes
- Reviewed:
  - `docs/specs/setup-wizard-shims-and-safer-autostart.md`
  - `docs/contracts/cli.md`
- No code/tests executed (spec audit only).
