# Agent Class: Implement Spec

## Mission
Implement an existing spec, update tests/docs, and produce evidence that the
change is correct.

## When To Use
- There is a spec in `docs/specs/` (or the user explicitly requests implementation).

## Required Artifacts
- Link to the spec being implemented.
- Tests and docs updated as required by the change.

## Output Requirements
- Implement the spec as written, or record deviations with rationale and update the spec accordingly.
- Update or add tests so acceptance criteria are enforced.
- Run appropriate verification gates and record exact commands and results.
- If schema changes occur, update the relevant `collector/*.md` schema docs and any fixture cases.

## Definition Of Done
- All acceptance criteria are satisfied.
- Relevant test gates pass (at minimum `--lane fast`, plus additional lanes as justified by scope).
- Outcome and follow-ups are recorded in the spec (and/or in repo docs/issues as appropriate).

## Prohibited
- Shipping behavior changes without tests and documentation updates.
- Making large design decisions without recording them in the spec and aligning with the user.
