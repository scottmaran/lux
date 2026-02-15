# Agent Class: Audit
Layer: Contract

## Mission
Evaluate the existing codebase for correctness, risk, maintainability, and
contract clarity, then propose prioritized improvements.

## When To Use
- The user asks for a review/audit.
- The system has unclear contracts, flaky tests, confusing structure, or suspected bugs.
- Before major work to reduce risk.

## Required Artifacts
- Audit report in `docs/audits/<id>_<slug>.md` using `docs/audits/TEMPLATE.md`.

## Output Requirements
- Findings prioritized by severity and impact.
- Evidence for findings: file paths, commands, failing tests, or concrete observations.
- Recommended remediations, including test coverage gaps.
- Audits are read-only: do not change repo state while auditing.
- If the user wants changes, switch classes and follow that class's workflow:
  - One Off: for small, bounded fixes
  - Implement Spec: for larger changes or anything that needs a spec

## Definition Of Done
- Audit report can be used as a backlog for follow-on work.

## Prohibited
- Large refactors without a spec.
- Any repo changes (code, tests, docs, config) while in the Audit class.
