# Audit: Shim Enable/Disable/Status Spec Second-Pass Review

ID: 20260221-161402
Date: 2026-02-21
Owner: codex
Scope: Line-by-line review of `docs/specs/shim-enable-disable-status-path-management.md` for correctness, consistency, and implementation risk.

## Summary
The spec is materially stronger after the first pass, but a high-impact contract conflict remains around JSON failure semantics. Two additional medium-risk ambiguities could cause implementation drift or brittle behavior.

## Method
- Reviewed spec line-by-line:
  - `docs/specs/shim-enable-disable-status-path-management.md`
- Cross-checked against current CLI JSON envelope behavior:
  - `docs/contracts/cli.md`
  - `lux/src/main.rs`
- Cross-checked shim command implementation pattern:
  - `lux/src/main.rs`

## Findings
### Finding: Partial-outcome-on-failure conflicts with JSON error envelope contract
Severity: high
Evidence:
- Spec requires non-zero with partial payload details: `docs/specs/shim-enable-disable-status-path-management.md:148`
- Spec JSON fragments are success-shaped objects (implied `result`) rather than failure envelope: `docs/specs/shim-enable-disable-status-path-management.md:181`
- CLI contract requires failures to return `ok: false`, `result: null`: `docs/contracts/cli.md:179`
- Current code enforces `result: null` on any error path: `lux/src/main.rs:878`

Impact:
- Implementation cannot satisfy both contracts simultaneously without additional definition.
- High risk of breaking JSON consumers or violating documented CLI contract.

Recommendation:
- Resolve explicitly in spec:
  - Option A: keep non-zero and place partial outcome under `error_details` (update contract with exact field schema), keeping `result: null`.
  - Option B: treat PATH-phase failures as successful command with warnings and `result.path.ok=false`.
- Add acceptance criteria/tests for whichever option is chosen.

### Finding: PATH file mutation rollback policy is still undefined
Severity: medium
Evidence:
- Spec says commands can fail after PATH phase errors with partial outcome: `docs/specs/shim-enable-disable-status-path-management.md:149`
- Spec does not define whether already-modified files are rolled back on later file failure.
- Edit behavior is idempotence-only, not transactional: `docs/specs/shim-enable-disable-status-path-management.md:127`

Impact:
- Different implementations may choose rollback vs non-rollback, producing inconsistent host state and test outcomes.

Recommendation:
- Define one explicit policy:
  - non-atomic best-effort (no rollback) with per-file `changed`/`error`; or
  - transactional rollback across all touched files.
- Reflect policy in failure modes + tests.

### Finding: Duplicate guard snippet is pattern-sensitive for unusual path characters
Severity: medium
Evidence:
- Guard uses shell `case` glob pattern with unescaped path interpolation: `docs/specs/shim-enable-disable-status-path-management.md:101`

Impact:
- If `shims.bin_dir` contains glob pattern characters (`*`, `?`, `[`), duplicate detection can misbehave.
- Can produce duplicate PATH entries or false matches.

Recommendation:
- Specify escaping rules for path interpolation in the guard, or
- Use a non-glob comparison approach in emitted shell snippet.

### Finding: Host-wide file targeting + fail-on-any-file-error can be operationally brittle
Severity: medium
Evidence:
- Spec targets all existing zsh and bash files regardless of active shell: `docs/specs/shim-enable-disable-status-path-management.md:109`
- Any PATH mutation error on existing files forces non-zero exit: `docs/specs/shim-enable-disable-status-path-management.md:148`

Impact:
- A stale/unwritable file in an unused shell family can cause `enable`/`disable` to fail.
- May increase support burden and user confusion despite successful shim phase.

Recommendation:
- Keep policy if desired, but document this behavior explicitly in User Experience and CLI contract.
- Ensure errors name the exact failing file and include remediation text.

## Suggested Work Items
- Patch spec to resolve the JSON failure-envelope conflict.
- Add explicit rollback/non-rollback policy for PATH phase.
- Harden or revise duplicate guard snippet to avoid glob pitfalls.
- Clarify host-wide-file failure behavior in UX and contract docs.

## Verification Notes
- Reviewed with:
  - `nl -ba docs/specs/shim-enable-disable-status-path-management.md | sed -n '1,360p'`
  - `nl -ba docs/contracts/cli.md | sed -n '168,220p'`
  - `nl -ba lux/src/main.rs | sed -n '866,892p'`
  - `nl -ba lux/src/main.rs | sed -n '7750,7774p'`
