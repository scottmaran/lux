# Spec: Runtime Control Plane And Frictionless Agent UX

Status: implemented
Owner: codex
Created: 2026-02-16
Last updated: 2026-02-16

## Problem
Lasso currently requires multiple explicit steps to run a provider, UI lifecycle
is not first-class in CLI UX, and lifecycle/health/evidence-state data are
spread across ad hoc command flows. This creates friction, increases operator
mistakes, and prevents consistent real-time state for CLI and UI.

## Goals
- Provide independent UI lifecycle controls from the `lasso` CLI.
- Provide zero-friction recurring provider usage via managed shims:
- User can type normal `codex`/`claude` commands.
- Full argv passthrough must be preserved.
- Auto-start collector on first provider launch by default.
- Keep collector running by default with idle timeout.
- Rotate runs every 24h by default with safe attribution-preserving cutover.
- Define one runtime control-plane contract consumed by both CLI and UI for:
- lifecycle operations
- health checks
- evidence-state queries
- real-time event stream
- Expand `lasso setup` / `lasso doctor` readiness checks for trust/correctness.

## Non-Goals
- No invariant changes in `INVARIANTS.md`.
- No weakening of evidence integrity or attribution guarantees.
- No dependency on agent cooperation for observability guarantees.
- No legacy compatibility layer for `up/down/status --ui`.

## User Experience

### UI Lifecycle
New command family:
- `lasso ui up [--wait --timeout-sec N]`
- `lasso ui down`
- `lasso ui status`
- `lasso ui url`

Removal:
- Existing `--ui` lifecycle flag is removed from `up/down/status`.
- CLI returns actionable guidance to use `lasso ui ...` commands.

### Frictionless Provider Launch
User setup:
- `lasso setup`
- `lasso shim install codex claude`

Then normal usage:
- `codex ...` and `claude ...` launch through Lasso with full passthrough args.
- Collector auto-starts if needed (policy-driven).

### Collector Policy Defaults
Config defaults:
- `collector.auto_start: true`
- `collector.idle_timeout_min: 10080`
- `collector.rotate_every_min: 1440`

### Rotation Behavior
Run rotation rules:
1. Never rotate while provider session/job is active.
2. Defer rotation until provider plane is idle/down.
3. Update `.active_run.json` atomically at cutover.

Implementation note:
- Since run-id is injected via container env, rotation requires coordinated
  run-bound service cutover (not only state-file rewrite).

## Design

### 1) Runtime Control-Plane Service
Introduce a local runtime control-plane service using Unix-socket transport
with explicit config defaults and config location:
- `runtime_control_plane.socket_path: <config_dir>/runtime/control_plane.sock`
- `runtime_control_plane.socket_gid: <invoking_user_primary_gid>`
- Config location: top-level `runtime_control_plane` block in `config.yaml`.
- `<config_dir>` resolves from `LASSO_CONFIG_DIR` or default `~/.config/lasso`.
- Socket permissions are `0660`; parent runtime dir is `0770`.
- Owner is invoking user uid; group is `socket_gid`.

Responsibilities:
- Source of truth for runtime lifecycle state.
- Lifecycle operations for collector/provider/ui.
- Readiness/health reporting.
- Evidence-state summaries (run/session/job/pipeline pointers).
- SSE event publication.

CLI model:
- Lifecycle and status commands call the control-plane API.
- Runtime lifecycle command surface:
- `lasso runtime up`
- `lasso runtime down`
- `lasso runtime status`
- CLI auto-starts runtime control-plane if not already running.
- `runtime up` is idempotent and enforces single-instance lock/pid semantics.
- `runtime up` handles stale socket/pid artifact cleanup safely.
- After `runtime down`, next normal CLI/shim command auto-starts runtime by default.

UI model:
- Browser remains same-origin.
- `ui/server.py` proxies runtime-control-plane routes to the Unix-socket API.
- Proxy route namespace is explicit:
- `/api/runtime/*` for read-only runtime status/health/evidence-state.
- `/api/runtime/events` for SSE pass-through.
- Browser UI does not call control-plane cross-origin directly in v1.
- Mutating lifecycle routes are not proxied for browser clients in v1.

Deployment wiring:
- `compose.env` exports:
- `LASSO_RUNTIME_DIR=<config_dir>/runtime`
- `LASSO_RUNTIME_GID=<socket_gid>`
- `compose.ui.yml` mounts `${LASSO_RUNTIME_DIR}` at `/run/lasso/runtime`.
- UI service receives `UI_RUNTIME_CONTROL_PLANE_SOCKET=/run/lasso/runtime/control_plane.sock`.
- UI service includes `${LASSO_RUNTIME_GID}` group mapping so proxy can open the socket.

### 2) API Surface (Contract-Level)
Create `docs/contracts/runtime_control_plane.md` with explicit request/response
schema and failure semantics.

Required endpoint groups:
- Stack status
- Run status
- Session/job status
- Collector pipeline status
- Recent warnings/errors
- Lifecycle operations (start/stop/status/rotate where applicable)

Required event stream:
- run started/stopped
- job submitted/started/completed
- session started/ended
- collector lag/degradation
- attribution uncertainty warnings

Required event envelope:
- monotonically increasing event id
- RFC3339 timestamp
- event type
- severity
- payload object

Reconnect behavior:
- Support replay from last known id (via `Last-Event-ID` or equivalent query
  parameter, as finalized in contract).

Transport/auth requirements:
- Privileged runtime APIs are served over Unix-socket HTTP.
- Caller authorization is enforced by socket filesystem permissions.
- Proxy route contract:
- `ui/server.py` forwards selected read-only runtime routes only.
- SSE forwarding preserves stream semantics and forwards `Last-Event-ID`.

### 3) UI Command Family
Add dedicated subcommand tree in CLI:
- `lasso ui up`: starts UI service only.
- `lasso ui down`: stops UI service only.
- `lasso ui status`: returns UI service status.
- `lasso ui url`: returns resolved local URL (for scripts).

`lasso ui open` is intentionally deferred in v1 to avoid platform-specific
browser-launch behavior in the first cut.

### 4) Shim Architecture
Add shim management commands:
- `lasso shim install <provider...>`
- `lasso shim uninstall <provider...>`
- `lasso shim list`
- `lasso shim exec <provider> -- <argv...>`

Shim requirements:
- Preserve full passthrough argv exactly.
- Ensure Lasso prerequisites before launch:
- config validity
- collector state per policy
- provider plane state
- Route launch through Lasso-managed execution path to preserve attribution.
- Expose clear uninstall/escape hatch.
- V1 path/cwd simplification:
- Supported only when invoked from within configured workspace root.
- No argv path rewriting.
- Absolute host-path arguments are unsupported in v1 and fail fast with clear guidance.
- Runtime dependency:
- Shim commands depend on runtime control-plane; auto-start behavior applies.

### 5) Collector Runtime Policy
Add config section:
```yaml
collector:
  auto_start: true
  idle_timeout_min: 10080
  rotate_every_min: 1440
```

Behavior:
- Auto-start collector on provider/shim launch if collector is down and
  `auto_start=true`.
- Idle timeout countdown applies when no provider activity exists.
- Rotation checks wall clock against active run start time.

Rotation execution:
- If rotation due and provider session/job active: mark pending rotation.
- V1 idle definition: provider plane is down.
- If provider plane is up, keep rotation pending.
- When provider is down: execute cutover.
- Cutover performs:
1. new run id allocation
2. graceful stop of run-bound services + bounded drain/flush wait
3. run-bound service cutover/restart as needed for new run id env
4. atomic update of `<log_root>/.active_run.json`
5. post-cutover health verification
6. stream event emission (or degraded warning event on forced cutover)

### 6) Readiness Expansion (`setup` and `doctor`)
Expand doctor checks to cover:
- log sink permissions and ownership
- compose/runtime prerequisites
- collector sensor readiness
- harness API and token sanity
- path config coherence
- attribution prerequisites
- contract/schema version compatibility

Output model:
- machine-readable check list with severity + remediation text.
- `--strict` option to fail on warnings defined as strict-fail checks.

`setup` integration:
- surface failing readiness checks interactively/non-interactively with next-step guidance.

## Data / Schema Changes

### Config Contract (`docs/contracts/config.md`)
- Extend `version: 2` config contract with optional/defaulted `collector` block.
- Extend `version: 2` config contract with optional/defaulted
  `runtime_control_plane` block:
```yaml
runtime_control_plane:
  socket_path: <config_dir>/runtime/control_plane.sock
  socket_gid: <invoking_user_primary_gid>
```
- No schema version bump required if fields are optional with stable defaults.

### Runtime Contract
- Add `docs/contracts/runtime_control_plane.md` with endpoint and event schemas.

### Existing Evidence Schemas
- No required changes to raw/filtered/timeline schemas in this phase.
- If implementation introduces new evidence artifacts for runtime state, those
  artifacts must be documented in contract docs and covered by tests.

## Security / Trust Model
- Control-plane service is local-only via Unix socket.
- Socket path parent directory and socket file are uid/gid permissioned (`0770` dir, `0660` socket).
- Runtime operations remain outside agent trust boundary.
- No write access to evidence sink is granted to agent.
- Rotation and lifecycle operations must preserve attribution integrity and avoid
  silent ownership ambiguity.

## Failure Modes
- Control-plane unavailable:
- CLI returns actionable error and remediation.
- UI shows degraded runtime-state banner and retries.
- Control-plane socket permission/path errors:
- Runtime start fails fast with actionable remediation (`chmod/chown` + path details).
- UI proxy socket access mismatch:
- UI returns explicit degraded runtime-state error with gid/path remediation.
- Rotation due but provider active:
- Mark pending rotation and emit deferred warning event.
- Rotation cutover failure:
- Keep previous active run state, emit error event, no partial pointer updates.
- Shim install conflicts with PATH:
- Emit warning and explicit resolution guidance.
- Doctor check failures:
- Include per-check remediation; strict mode exits non-zero.

## Acceptance Criteria
- `lasso ui up/down/status/url` are available, documented, and tested.
- `up/down/status --ui` is removed and replaced by actionable `lasso ui ...` guidance.
- `lasso runtime up/down/status` are available and documented.
- Shimmed `codex` and `claude` preserve full argv passthrough.
- Shim v1 behavior is explicit:
- workspace-root cwd required
- no path rewriting
- absolute host-path args fail fast with actionable messaging
- First shim/provider launch auto-starts collector when policy enabled.
- Collector defaults are:
- `auto_start=true`
- `idle_timeout_min=10080`
- `rotate_every_min=1440`
- Control-plane defaults are:
- `runtime_control_plane.socket_path=<config_dir>/runtime/control_plane.sock`
- `runtime_control_plane.socket_gid=<invoking_user_primary_gid>`
- Config location is top-level `runtime_control_plane` in `config.yaml`.
- Rotation never occurs during active session/job.
- Deferred rotations execute when provider is idle/down.
- `.active_run.json` updates atomically at cutover.
- Rotation cutover performs bounded drain/flush and health verification.
- CLI and UI consume same runtime control-plane contract for lifecycle and
  health/evidence-state operations.
- UI runtime calls use same-origin proxy routes via `ui/server.py`.
- UI proxy route namespace and SSE forwarding behavior are explicitly contracted.
- Event stream emits required lifecycle/degradation/attribution-warning events.
- `lasso doctor` surfaces the expanded readiness checks with machine-readable output.

## Test Plan
- Unit tests:
- config default/parse/validate for `collector.*`.
- config default/parse/validate for `runtime_control_plane.socket_path`.
- config default/parse/validate for `runtime_control_plane.socket_gid`.
- shim argv passthrough and launch construction.
- shim cwd/path validation and fail-fast behavior.
- rotation scheduler and deferred cutover logic.
- rotation drain/flush and forced-cutover degraded path.
- atomic active-run state updates.
- control-plane endpoint/event serialization.
- runtime lock/pid/stale-socket lifecycle behavior.
- Fixture cases:
- Not required unless collector pipeline transformations are changed.
- Integration coverage:
- CLI UI lifecycle commands.
- `lasso runtime up/down/status` lifecycle commands.
- `runtime down` then normal CLI/shim command auto-start behavior.
- shim workflow for codex/claude with passthrough args.
- collector auto-start and idle timeout.
- rotation defer/execute semantics.
- UI runtime-state integration via same-origin proxy to control-plane.
- UI proxy route namespace and `Last-Event-ID` SSE forwarding behavior.
- Regression tests:
- rotation boundary attribution integrity.
- no stale active-run pointers after failed/successful cutover.
- no collector shutdown while provider activity remains.
- no silent evidence gap across rotation cutover drain/restart boundary.
- Manual verification:
- end-to-end setup -> shimmed provider launch -> UI live updates -> deferred rotation -> cutover.

## Rollout
- Stealth mode allows behavior changes without strict backwards compatibility,
  but all user-visible changes require docs + tests.

Rollout sequence:
1. Spec and contract docs.
2. UI command family.
3. Shim management + passthrough execution.
4. Collector policy defaults and runtime behavior.
5. Control-plane service + runtime lifecycle commands + CLI consumers.
6. UI same-origin proxy integration + event stream consumers.
7. Setup/doctor readiness expansion.
8. Remove legacy `--ui` code paths and finalize CLI error messaging.

## Implementation Notes (2026-02-16)
- Implemented command families:
  - `lasso ui up|down|status|url`
  - `lasso runtime up|down|status`
  - `lasso shim install|uninstall|list|exec`
- Removed deprecated `--ui` flags from `up/down/status`.
- Added config defaults:
  - `collector.auto_start=true`
  - `collector.idle_timeout_min=10080`
  - `collector.rotate_every_min=1440`
  - `runtime_control_plane.socket_path` defaulting to `<config_dir>/runtime/control_plane.sock`
  - `runtime_control_plane.socket_gid` defaulting to invoking primary gid.
- Added runtime control-plane contract and implementation over Unix socket with:
  - status/evidence endpoints
  - warnings endpoint
  - SSE event stream with replay by id
  - CLI execution endpoint used by lifecycle commands.
- Added same-origin UI runtime proxy routes in `ui/server.py`:
  - `/api/runtime/stack-status`
  - `/api/runtime/run-status`
  - `/api/runtime/session-job-status`
  - `/api/runtime/collector-pipeline-status`
  - `/api/runtime/warnings`
  - `/api/runtime/events` (SSE passthrough).
- Added compose/UI runtime socket wiring:
  - `LASSO_RUNTIME_DIR`
  - `LASSO_RUNTIME_GID`
  - UI socket mount and group mapping.
- Expanded `lasso doctor` to structured readiness checks with `--strict`.
