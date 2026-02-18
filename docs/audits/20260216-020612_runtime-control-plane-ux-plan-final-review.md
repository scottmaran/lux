# Audit: Runtime Control Plane + UX Plan Final Implementability Review

ID: 20260216-020612
Date: 2026-02-16
Owner: codex
Scope: `PLAN.md` and `docs/specs/runtime-control-plane-and-frictionless-ux.md` implementation readiness

## Summary
The plan/spec are close to implementation-ready, but there are 5 blocking gaps
to resolve before coding starts. The largest risks are control-plane security,
UI-to-control-plane integration mechanics, runtime bootstrapping/scheduler
ownership, and rotation cutover completeness guarantees.

## Method
- Reviewed:
- `PLAN.md`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md`
- `INVARIANTS.md`
- `docs/contracts/config.md`
- `lasso/config/default.yaml`
- `lasso/src/main.rs` (CLI surface)
- `ui/server.py` and UI components (`Timeline.tsx`, `SummaryMetrics.tsx`)
- Checked for:
- contract completeness
- contradiction with current architecture
- testability and rollout feasibility
- invariant alignment risks

## Findings

### Finding: Control-plane auth model is unspecified for privileged lifecycle operations
Severity: high
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:82`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:107`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:218`

Impact:
- Localhost binding alone does not define caller authorization for operations
  like start/stop/rotate.
- Another local process could potentially interfere with runtime lifecycle and
  evidence continuity.

Recommendation:
- Add explicit control-plane auth contract before implementation:
- Option A (preferred): local Unix socket with filesystem permissions.
- Option B: localhost HTTP with required bearer token (config/env sourced),
  matching harness API style.
- Define auth failure semantics in `docs/contracts/runtime_control_plane.md`.

### Finding: UI-to-control-plane connectivity path is unaccounted for
Severity: high
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:93`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:79`
- `ui/src/components/Timeline.tsx:88`
- `ui/src/components/SummaryMetrics.tsx:50`
- `ui/server.py:325`

Impact:
- UI currently fetches same-origin `/api/*` via `ui/server.py`.
- Spec moves runtime API to separate port `8082`, but does not define CORS or
  reverse-proxy behavior.
- Without this, UI integration in PR6 is not directly implementable.

Recommendation:
- Pick one integration strategy in spec/contract now:
- Preferred: keep browser same-origin by adding `ui/server.py` proxy routes to
  runtime control-plane.
- Alternative: enable strict CORS on control-plane and update UI fetch base URL.
- Add explicit integration tests for this path.

### Finding: Runtime control-plane lifecycle/bootstrapping ownership is undefined
Severity: high
Evidence:
- `PLAN.md:70`
- `PLAN.md:189`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:76`

Impact:
- CLI commands are planned as API clients, but no authoritative rule exists for
  when/how control-plane is started, discovered, supervised, or restarted.
- Timer-driven features (idle timeout, rotation cadence) also require a
  continuously running scheduler owner.

Recommendation:
- Define process model explicitly:
- always-on daemon started via `lasso runtime up` and auto-started by CLI clients, or
- embedded supervisor in each lifecycle command (not recommended for timers).
- Add state/health endpoint that distinguishes:
- process unavailable
- process running but degraded

### Finding: Rotation cutover lacks explicit no-loss/drain behavior
Severity: high
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:174`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:177`
- `PLAN.md:138`

Impact:
- Cutover currently lists restart and pointer swap, but does not define
  collector/harness drain/flush semantics.
- This risks silent evidence gaps around restart windows, conflicting with
  completeness expectations.

Recommendation:
- Add cutover contract steps:
- graceful stop with bounded wait for in-flight writes,
- explicit degraded event if forced cutover occurs before flush,
- post-cutover health confirmation before declaring success.
- Add regression test specifically at cutover boundary for continuity.

### Finding: Shim passthrough semantics are under-specified for cwd/path/env behavior
Severity: medium
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:145`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:150`
- `PLAN.md:114`

Impact:
- “Full argv passthrough” is stated, but not how host paths/cwd/env map into
  container `/work`.
- Ambiguity can produce broken commands or inconsistent UX between direct and
  shimmed provider usage.

Recommendation:
- Define shim translation contract:
- host cwd mapping rule to container path,
- behavior for absolute host paths in args,
- env passthrough allowlist/denylist,
- deterministic error message when passthrough is impossible.
- Add integration tests with path-heavy argument patterns.

## Suggested Work Items
- Add a “control-plane security + auth” section to spec and contract.
- Add a “UI integration architecture” section defining proxy/CORS strategy.
- Add a “control-plane process lifecycle” section with startup/discovery model.
- Expand rotation section with drain/flush + degraded fallback semantics.
- Add shim translation rules for cwd/path/env and test cases.

## Verification Notes
- Review only; no runtime tests executed.
- Commands used:
- `nl -ba PLAN.md | sed -n '1,320p'`
- `nl -ba docs/specs/runtime-control-plane-and-frictionless-ux.md | sed -n '1,360p'`
- `nl -ba ui/src/components/Timeline.tsx | sed -n '70,130p'`
- `nl -ba ui/src/components/SummaryMetrics.tsx | sed -n '35,85p'`
- `nl -ba ui/server.py | sed -n '320,390p'`
- `nl -ba lasso/src/main.rs | sed -n '40,110p'`
- `nl -ba lasso/config/default.yaml | sed -n '1,120p'`
- `nl -ba docs/contracts/config.md | sed -n '1,220p'`
