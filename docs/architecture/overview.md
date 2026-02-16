# Architecture Overview (How It Works Today)
Layer: Implementation

This document is a short description of the current Lasso architecture. It is
allowed to change as the implementation evolves. For externally visible
behavior, see `docs/contracts/`.

## Components
- `lasso` (CLI): config + lifecycle wrapper for the local stack.
- `agent` (container): the untrusted third-party agent runtime.
- `harness` (container): trusted control plane for starting sessions/jobs and
  capturing stdio/PTY evidence.
- `collector` (container): OS-level observation (auditd + eBPF) and pipelines
  raw events into contract schemas.
- `ui` (optional): reads evidence from the sink for review.
- Evidence sink (host dir): durable storage for run artifacts (outside agent control).

## Data / Evidence Flow (Typical Local Run)
1. `lasso up` boots the stack.
2. `harness` starts an agent session/job (via internal SSH) and captures stdout/stderr
   (and stdin for interactive sessions).
3. `collector` observes OS-level events in the VM boundary and writes raw logs.
4. `collector` filters/normalizes/summarizes and merges into a unified timeline.
5. `harness` may materialize per-session/per-job timeline copies (derived snapshots).
6. `ui` (or the user) reads the sink to inspect evidence.

## Canonical Contracts
- Log layout: `docs/contracts/log_layout.md`
- Schemas: `docs/contracts/schemas/README.md`
- Attribution: `docs/contracts/attribution.md`
- Collector config semantics: `docs/contracts/collector_config/README.md`
