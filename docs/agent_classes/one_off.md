# Agent Class: One Off

## Mission
Handle a small, bounded task quickly (bug fix, tiny refactor, doc tweak, narrow
question) with minimal process overhead and strong verification.

## When To Use
- The task is clearly scoped and can be completed in one sitting.
- There is no need for a full spec.

## Required Artifacts
- If the task introduces a new behavior or changes a contract: write/update a spec instead of treating it as One Off.

## Output Requirements
- Keep changes minimal and localized.
- Add or update tests if behavior changes.
- Record commands and verification.

## Definition Of Done
- The requested change is complete and verified.
- Any follow-ups are explicitly listed.

## Prohibited
- Allowing scope to grow without reclassifying to Create Spec or Implement Spec.
