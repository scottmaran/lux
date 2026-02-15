# Lasso Invariants (Implementation-Agnostic)

This document defines the non-negotiable product invariants of Lasso.
These invariants must remain true even if the implementation changes
(runtime, packaging, sensors, storage layout, UI, etc).

Change policy:
- Clarifications are allowed.
- Meaning changes require explicit user approval and must be reflected in tests and docs.

## Definitions (Abstract)
- **Agent**: the untrusted program being observed (plus anything it executes).
- **User**: the party relying on Lasso evidence to understand what happened.
- **Observation boundary**: the scope within which Lasso claims evidence coverage for an agent run.
  The boundary may be local, remote, or hybrid depending on deployment; the invariant is that it is explicit.
- **Evidence**: durable, structured records produced by Lasso about agent actions and outcomes.
- **Evidence sink**: the storage location for evidence (where evidence is written and later read).
- **Trusted logging plane**: the set of components and assumptions that Lasso relies on to produce and protect evidence.
  The exact trusted components may evolve; the invariant is that the agent is not part of the TCB for evidence integrity.
- **Attribution**: the ability to associate evidence with a specific run and a specific agent execution context
  (for example a session/job/attempt), without silent ambiguity.

## Invariant 1: Evidence Completeness Within the Observation Boundary

Statement:
- For any in-boundary agent action that produces an externally observable effect, Lasso must produce evidence.

Implications:
- The observation boundary must be explicit (what is covered vs not covered).
- Evidence must be sufficient for a user to answer: "What did the agent do?" and "What changed as a result?"
- Evidence should be structured, queryable, and suitable for automated validation (tests can enforce it).

Completeness expectation:
- In supported configurations, missing evidence for an in-boundary, attributable action is a bug.
- If completeness is limited by environment constraints, the limitation must be explicit in the product contract
  (docs/tests) rather than silently dropping coverage.

## Invariant 2: The Agent Cannot Tamper With Evidence

Statement:
- The agent must not be able to modify, delete, or rewrite evidence in a way that changes the user's understanding
  of what happened, within the trusted logging plane.

Implications:
- Evidence must be written to an evidence sink that is outside the agent's control.
- If the agent is allowed to read evidence during execution, that access must not grant the ability to alter evidence.
- Any trusted rewrites (for example "snapshot" materializations) must be defined as part of the contract so that
  rewrites cannot be mistaken for tampering.

Boundary note (abstract):
- This invariant is defined relative to an explicit trust boundary. If the trusted logging plane is compromised,
  evidence integrity may not hold; that is a violation of assumptions, not a silent behavior change.

## Invariant 3: Evidence Is Attributable (No Silent Ambiguity)

Statement:
- Evidence must be attributable to a specific agent execution context (run and per-run subdivision) without silent ambiguity.

Implications:
- Evidence records must carry stable correlation identifiers so they can be grouped and traced end-to-end.
- If attribution is uncertain, that uncertainty must be explicit (for example marked unknown) and handled by rule.
  It must never be silently guessed.
- Referential integrity matters: when evidence references an identifier (run/session/job/etc), corresponding metadata
  must exist so a user can resolve "what is this?".

## Invariant 4: Observation Does Not Depend on Agent Cooperation

Statement:
- Lasso's evidence must not rely on the agent program being cooperative, instrumented, or even aware of Lasso.

Implications:
- Evidence is derived from mechanisms outside the agent process (for example OS/runtime observation and harness-controlled IO),
  not from agent self-reporting.
- Provider-specific integration may affect how the agent is launched or authenticated, but must not be required for
  the core observation and attribution guarantees.

