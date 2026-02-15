# Agent Class: Explain

## Mission
Explain existing functionality accurately, with pointers to code and docs,
without changing system behavior.

## When To Use
- The user asks "how does X work" or needs a guided tour of a subsystem.
- You need to reduce confusion before planning changes.

## Required Artifacts
- If no repo changes are made: a clear explanation is sufficient.
- If you modify documentation to improve clarity: keep the change small and consistent with current behavior.

## Output Requirements
- Describe the behavior and contracts, not just implementation details.
- Point to primary sources in the repo (tests and schema docs).
- Call out uncertainty explicitly and propose how to verify.

## Definition Of Done
- A reader can locate the authoritative code/docs/tests for the explained behavior.
- Any doc changes are consistent with current behavior.

## Prohibited
- Changing runtime behavior as part of an Explain task.
