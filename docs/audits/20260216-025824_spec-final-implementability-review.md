# Audit: Spec Final Implementability Review

ID: 20260216-025824
Date: 2026-02-16
Owner: codex
Scope: `docs/specs/runtime-control-plane-and-frictionless-ux.md`

## Summary
The spec is close to implementation-ready, but there are still unresolved gaps
around UI proxy transport, socket permission model, daemon lifecycle semantics,
and explicit proxy route contracts.

## Method
- Reviewed spec with line-level checks.
- Cross-checked current UI runtime wiring:
- `compose.ui.yml`
- `ui/server.py`

## Findings

### Finding: UI proxy-to-socket path is not wired in deployment contract
Severity: high
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:99`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:100`
- `compose.ui.yml:4`

Impact:
- Spec requires `ui/server.py` to proxy to runtime control-plane over Unix socket.
- Current UI service contract only mounts log roots, not runtime socket paths.
- Without a socket mount (or alternate host bridge), proxy integration cannot work.

Recommendation:
- Add explicit deployment contract for UI proxy transport:
- mount socket directory into UI container at a fixed path, or
- define alternative host bridge path with equivalent security controls.

### Finding: Owner-only socket auth conflicts with UI container proxy access
Severity: high
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:81`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:234`
- `compose.ui.yml:1`

Impact:
- Owner-only permissions are good for auth, but UI proxy in container needs read/write socket access.
- Spec does not define matching uid/gid strategy between host runtime process and UI container.

Recommendation:
- Define one explicit model:
- shared uid/gid between runtime process and UI container, or
- dedicated socket group with `0660` permissions + fixed container group mapping.

### Finding: Runtime daemon lifecycle semantics are under-specified
Severity: medium
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:93`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:96`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:258`

Impact:
- Spec says CLI auto-starts runtime and also exposes `runtime up/down/status`.
- Missing single-instance, stale socket cleanup, and race behavior contract.

Recommendation:
- Add explicit lifecycle semantics:
- lock file and ownership rules,
- stale socket detection/recovery,
- behavior after `runtime down` when normal CLI commands run next.

### Finding: Proxy route namespace and stream behavior are not explicit
Severity: medium
Evidence:
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:100`
- `docs/specs/runtime-control-plane-and-frictionless-ux.md:101`
- `ui/server.py:325`

Impact:
- Without explicit route namespace (`/api/runtime/*` etc.), integration can drift.
- SSE proxy semantics (headers/streaming/reconnect pass-through) are not yet contracted.

Recommendation:
- Define proxy route names and SSE forwarding contract in spec/contract docs.

## Suggested Work Items
- Add “UI socket transport wiring” subsection to spec + `docs/contracts/ui_api.md`.
- Add “socket permission/group model” subsection to `docs/contracts/runtime_control_plane.md`.
- Add “runtime process lifecycle and locking” subsection to spec/contract.
- Add “proxy route + SSE forwarding” subsection and associated integration tests.

## Verification Notes
- Review only; no tests executed.
