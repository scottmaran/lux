# Lasso UX + Runtime Control Plane Implementation Plan

Status: implemented
Owner: codex
Created: 2026-02-16
Last updated: 2026-02-16

## Purpose
This file is the implementation execution plan. The detailed behavior contract is
specified in `docs/specs/runtime-control-plane-and-frictionless-ux.md`.

## Consistency And Alignment Review
This section records the consistency review against current repo contracts and implementation.

### Verified Alignment
- Invariant alignment:
- Preserves evidence integrity and attribution guarantees in `INVARIANTS.md`.
- Explicitly prevents silent attribution ambiguity at run rotation boundaries.
- Doc-layer alignment:
- Durable behavior moves into contract/spec docs (`docs/contracts/*`, `docs/specs/*`).
- No implementation details are added to `INVARIANTS.md`.
- Test-contract alignment:
- Plan maps new behavior to unit/integration/regression coverage in `tests/README.md`.

### Corrections Applied To Prior Draft
- Rotation correctness gap fixed:
- Current run-id is injected via env at container start.
- Safe rotation therefore requires container cutover (not only `.active_run.json` rewrite).
- UI lifecycle clarity tightened:
- Independent UI lifecycle is implemented with dedicated `lasso ui ...` command family.
- Legacy `--ui` lifecycle flags are removed (no compatibility mode).
- Config naming finalized:
- Rotation field fixed to `collector.rotate_every_min` with default `1440`.
- Control-plane transport/auth finalized:
- Privileged runtime control-plane operations use a local Unix domain socket.
- Socket access is enforced by uid/gid filesystem permissions.
- UI integration finalized (Option A):
- Browser stays same-origin via `ui/server.py` proxy routes to control-plane.
- No direct browser-to-control-plane cross-origin access in v1.
- UI socket transport wiring finalized:
- Runtime socket directory is mounted into UI container at `/run/lasso/runtime`.
- `ui/server.py` uses `UI_RUNTIME_CONTROL_PLANE_SOCKET` to reach control-plane.
- Proxy namespace is explicit: `/api/runtime/*` and `/api/runtime/events` (SSE).
- Runtime ownership finalized:
- Control-plane runs as a long-lived scheduler/orchestrator process.
- CLI auto-starts it when needed, with explicit `lasso runtime up|down|status`.
- Daemon lifecycle semantics finalized:
- single-instance lock + pid state, stale socket recovery, and deterministic restart behavior.
- After `lasso runtime down`, next CLI/shim command auto-starts runtime by default.

## Locked Product Decisions
- UI lifecycle is independent from collector/provider lifecycle.
- Provide explicit UI CLI commands (Option B).
- Provide managed provider shims (Option B) with full argv passthrough.
- Collector auto-start on first agent launch by default.
- `collector.auto_start: true` by default.
- `collector.idle_timeout_min: 10080` by default.
- `collector.rotate_every_min: 1440` by default.
- `runtime_control_plane.socket_path` is top-level config and defaults under
  `LASSO_CONFIG_DIR` (uid/gid permission model).
- `runtime_control_plane.socket_gid` defaults to invoking user primary gid.
- `compose.env` includes:
- `LASSO_RUNTIME_DIR`
- `LASSO_RUNTIME_GID`
- `compose.ui.yml` mounts `${LASSO_RUNTIME_DIR}` and adds `${LASSO_RUNTIME_GID}` for socket access.
- Rotation safety rules:
1. Never rotate while a provider session/job is active.
2. Defer rotation until provider plane is idle/down.
3. Update `<log_root>/.active_run.json` atomically at cutover.
- Introduce one runtime control-plane contract used by both CLI and UI.

## Scope

### In Scope
- New runtime control-plane contract + implementation.
- Independent UI lifecycle command set.
- Provider shims with full passthrough.
- Collector auto-start, idle timeout, and safe periodic rotation.
- Expanded setup/doctor readiness checks.
- Tests and docs updates for all user-visible behavior changes.

### Out Of Scope
- Changes to evidence schemas unless required by implementation.
- Invariant changes in `INVARIANTS.md`.
- Non-local/remote multi-host orchestration.

## Architecture Summary
- Add a local runtime control-plane service (`lasso runtime serve`) with HTTP+SSE
  over Unix socket transport for privileged runtime APIs.
- CLI lifecycle/status commands become clients of this control plane.
- UI stays same-origin and accesses control-plane via `ui/server.py` proxy routes.
- UI proxy forwards read-only runtime routes in v1; mutating lifecycle routes remain CLI-only.
- Existing evidence ingestion and storage paths remain run-scoped under `<log_root>/<run_id>/...`.

## Workstreams

### Workstream 1: Contracts And Spec
Deliverables:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md` (new).
- `docs/contracts/runtime_control_plane.md` (new).
- Updates to:
- `docs/contracts/cli.md`
- `docs/contracts/config.md`
- `docs/contracts/install.md`
- `docs/contracts/ui_api.md` (same-origin proxy integration guidance with runtime control-plane contract)
- `compose.ui.yml` contract notes (runtime socket mount + group mapping)

Exit Criteria:
- Endpoint/event contracts are unambiguous and testable.
- Config contract includes collector policy defaults and semantics.

### Workstream 2: CLI UI Lifecycle
Deliverables:
- New CLI command tree:
- `lasso ui up [--wait --timeout-sec N]`
- `lasso ui down`
- `lasso ui status`
- `lasso ui url`
- Removal policy:
- `--ui` is removed from `up/down/status`.
- CLI returns actionable error directing users to `lasso ui ...`.

Exit Criteria:
- UI can be started/stopped/queried without collector/provider lifecycle coupling.
- `--help` and docs reflect behavior exactly.

### Workstream 3: Shim System With Full Passthrough
Deliverables:
- Commands:
- `lasso shim install <provider...>`
- `lasso shim uninstall <provider...>`
- `lasso shim list`
- `lasso shim exec <provider> -- <argv...>` (internal/public helper)
- Shim behavior:
- Preserve full argv passthrough for `codex` and `claude`.
- Ensure prerequisites (`setup` complete, collector/provider availability based on policy).
- Execute provider through Lasso-managed session path for attribution.
- V1 path/cwd simplification:
- Supported only when invoked from within configured workspace root.
- No argv path rewriting.
- Absolute host-path arguments are unsupported in v1 and fail fast with actionable messaging.
- Runtime dependency:
- Shim commands require runtime control-plane; auto-start applies when unavailable.

Exit Criteria:
- `codex <args...>` and `claude <args...>` behave with preserved arguments.
- Session/job evidence remains attributable.

### Workstream 4: Collector Runtime Policy
Deliverables:
- Config additions (v2 extended with defaults):
- `collector.auto_start: true`
- `collector.idle_timeout_min: 10080`
- `collector.rotate_every_min: 1440`
- Runtime behaviors:
- auto-start collector on first provider/shim launch.
- auto-stop collector after idle timeout.
- rotate run at cadence using safe cutover.

Rotation Cutover Rules:
- If provider has active session/job: mark rotation pending.
- V1 idle definition: provider plane is down.
- If provider plane is up, rotation stays pending until provider down.
- At cutover:
1. Create new run directory and run id.
2. Gracefully stop run-bound services and wait (bounded) for flush/drain.
3. Restart run-bound services required for new run-id env.
4. Atomically write `.active_run.json`.
5. Verify post-cutover health.
6. Emit rotation event on control-plane stream (or degraded warning on forced cutover).

Exit Criteria:
- No rotation occurs mid active session/job.
- New evidence lands in new run after cutover.

### Workstream 5: Runtime Control Plane
Deliverables:
- Unix-socket HTTP endpoints for:
- stack status
- run status
- session/job status
- collector pipeline status
- recent warnings/errors
- lifecycle operations (collector/provider/ui control, run rotate)
- SSE endpoint for:
- run started/stopped
- job submitted/started/completed
- session started/ended
- collector lag/degradation
- attribution uncertainty warnings
- Runtime lifecycle commands:
- `lasso runtime up`
- `lasso runtime down`
- `lasso runtime status`
- Lifecycle semantics:
- `runtime up` is idempotent and enforces single-instance lock.
- `runtime up` removes stale socket/pid artifacts before restart when safe.
- `runtime down` stops daemon and clears runtime artifacts.
- Next normal CLI/shim command auto-starts runtime (default UX path).
- UI proxy surface:
- `ui/server.py` same-origin proxy routes:
- `/api/runtime/*` (read-only status/health/evidence-state)
- `/api/runtime/events` (SSE pass-through with `Last-Event-ID` forwarding)

Exit Criteria:
- CLI and UI consume consistent state from one API contract.
- SSE events are ordered and reconnect-safe per contract.

### Workstream 6: Setup/Doctor Readiness Expansion
Deliverables:
- `lasso doctor` expanded checks:
- log sink permissions/ownership
- compose/runtime prerequisites
- collector sensor readiness
- harness API/token sanity
- path config coherence
- attribution prerequisites
- contract/schema version compatibility
- `lasso setup` improvements to proactively surface/remediate failing checks.
- Optional strict mode for automation (`lasso doctor --strict`).

Exit Criteria:
- Misconfigurations that threaten trust/correctness are surfaced before runtime.
- Results are machine-readable and actionable.

## Implementation Sequence (PR Slices)
1. PR1: spec + contracts only.
2. PR2: `lasso ui` command family + docs/tests.
3. PR3: shim install/list/uninstall + passthrough execution path + tests.
4. PR4: collector config fields + defaults + parsing/validation + docs/tests.
5. PR5: control-plane service skeleton + runtime up/down/status + CLI client wiring.
6. PR6: Unix-socket auth/permission model + UI same-origin proxy integration.
7. PR7: event stream + rotation scheduler + drain-safe cutover + regression tests.
8. PR8: doctor/setup readiness expansion + strict mode + tests/docs.

## Verification Strategy

### Unit
- Config defaults and validation for new `collector.*` fields.
- Config defaults and validation for `runtime_control_plane.socket_path`.
- Config defaults and validation for `runtime_control_plane.socket_gid`.
- Shim argument passthrough and command construction.
- Shim cwd/path validation and fail-fast behavior.
- Rotation eligibility and deferred scheduling logic.
- Rotation drain/flush and forced-cutover degraded-path behavior.
- Atomic state-file write/replace behaviors.
- Control-plane payload and event serialization.
- Daemon lock/pid/stale-socket lifecycle behavior.

### Integration
- `lasso ui up/down/status/url` end-to-end.
- `lasso runtime up/down/status` lifecycle behavior.
- `runtime down` followed by normal CLI/shim command auto-start behavior.
- Shimmed `codex` and `claude` passthrough with representative arg patterns.
- Collector auto-start and idle timeout behavior.
- Rotation defers during active sessions/jobs and executes after idle/down.
- UI reads runtime state/event stream correctly through same-origin proxy paths.
- UI proxy forwards SSE and `Last-Event-ID` semantics correctly.

### Regression
- Rotation boundary attribution integrity.
- No stale `.active_run.json` pointer after cutover or failure.
- No unexpected collector shutdown while provider active.
- No silent evidence gap across drain-safe rotation cutover.

### Contract Coverage
- Validate endpoint/event responses against `docs/contracts/runtime_control_plane.md`.
- Keep CLI docs and observed command behavior in sync.

## Canonical Gates
- `uv sync`
- `uv run python scripts/all_tests.py --lane fast`
- `uv run python scripts/all_tests.py --lane pr`
- `uv run python scripts/all_tests.py --lane full`

## Risks And Mitigations
- Risk: rotation cutover drops or misattributes events.
- Mitigation: safe eligibility rules + deferred cutover + drain/flush + regression coverage.
- Risk: shim PATH behavior can surprise users.
- Mitigation: explicit install/uninstall/list UX and clear docs.
- Risk: shim path translation brittleness.
- Mitigation: v1 no-path-rewrite contract + workspace-cwd requirement + fail-fast errors.
- Risk: control-plane state drifts from Docker actual state.
- Mitigation: reconcile-on-read checks and degraded-state warnings.
- Risk: local unauthorized control-plane access.
- Mitigation: Unix socket transport + strict uid/gid filesystem permissions.
- Risk: UI container cannot access Unix socket due gid mismatch.
- Mitigation: explicit socket group mapping via `LASSO_RUNTIME_GID` + integration coverage.
- Risk: expanded doctor checks become noisy.
- Mitigation: severity levels (`error`, `warn`, `info`) and strict-mode gating.

## Plan Readiness
- This plan is consistent with repo invariants and doc layering.
- This plan is implementation-ready pending approval of the companion spec.
