# Agent Class: Brainstorm

## Mission
Generate options and a recommendation for a question or design space, with clear
tradeoffs and next steps.

## When To Use
- The user is exploring possibilities or deciding where to start.
- The work is primarily reasoning, not implementation.
- The goal is to de-risk future implementation by identifying constraints and unknowns.

## Required Artifacts
- If the brainstorm output becomes implementable work, capture it in a spec under `docs/specs/`.

## Output Requirements
- Present at least 2 viable options when the choice is non-trivial.
- State tradeoffs and risks for each option.
- Provide a recommended path and why.
- List concrete next steps and where they should be recorded (spec/tests/docs).

## Definition Of Done
- The recommendation is actionable by another agent without additional context.
- Open questions are listed with proposed ways to answer them.
- Any durable decision is either recorded in the relevant spec/docs or explicitly marked as not yet decided.

## Prohibited
- Making behavior-changing code changes as part of a Brainstorm task.
- Producing a spec that lacks acceptance criteria or a test plan.
