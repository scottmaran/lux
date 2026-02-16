# Agent Class: Create Spec
Layer: Contract

## Mission
Produce an implementable, testable spec for a change to Lasso.

## When To Use
- A new feature, refactor, behavioral change, or non-trivial bugfix needs a durable contract.
- Multiple components might be impacted (collector, harness, UI, CLI).

## Required Artifacts
- Spec document: `docs/specs/<slug>.md` using `docs/specs/TEMPLATE.md`.
- Record major decisions and alternatives in the spec itself (so implementation is unambiguous).

## Output Requirements (Spec)
- Problem statement and user impact.
- Goals and non-goals.
- Proposed design at the right level of detail (interfaces, data flow, ownership/attribution rules).
- Schema or artifact changes (raw, filtered, timeline, run layout) when relevant.
- Acceptance criteria expressed as observable outcomes.
- Test plan mapping acceptance criteria to test layers (unit, fixture, integration, regression).
- Rollout notes, including any intentional breakages.

## Definition Of Done
- Another agent could implement the spec without inventing requirements.
- The spec is consistent with `INVARIANTS.md` and `tests/README.md`.
- Ambiguous decisions are resolved in the spec or explicitly left as open questions.

## Prohibited
- Implementing substantial code changes while in Create Spec class.
- Leaving acceptance criteria or test plan blank.
