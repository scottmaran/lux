# Glossary
Layer: Contract

This glossary defines shared vocabulary across invariants, contracts, specs, and
implementation docs.

Canonical definitions for the trust-model terms live in `INVARIANTS.md`. This
file is an index and a place for repo-wide operational vocabulary.

## Trust-Model Terms (Canonical)
See `INVARIANTS.md`:
- Agent
- User
- Observation boundary
- Evidence
- Evidence sink
- Trusted logging plane
- Attribution

## Operational Terms
- **Contract**: externally visible behavior that other components and users can
  rely on. Canonical docs live under `docs/contracts/`.
- **Implementation**: how the current system achieves the contracts today.
  Canonical docs live under `docs/architecture/`.
- **Run**: one `lux up` lifecycle; evidence is grouped under a run-scoped root
  directory in the sink.
- **Session**: one interactive TUI session started by the harness.
- **Job**: one non-interactive server-mode invocation started by the harness.
- **Schema**: a versioned contract for an on-disk artifact shape (see
  `docs/contracts/schemas/`).
- **Agent-owned**: an event attributed to the agent's execution context for a
  given session/job, excluding background VM/container noise (see
  `docs/contracts/attribution.md`).
