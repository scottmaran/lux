---
name: system-boundary-review
description: Boundary-aware design and change review for the Lux repo. Use when a task might create/change a boundary (CLI commands/flags, on-disk artifacts or schema formats, cross-component APIs, "public" internal interfaces, dependency direction changes, versioning/backcompat decisions) or when you're unsure what the boundary is. Output a concise Boundary Review plus candidate repo boundary rules to discuss.
---

# System Boundary Review

## Overview

Identify boundaries early, design their contracts deliberately, and avoid locking in leaky or tightly-coupled interfaces.

## Workflow

### 1) Decide: Is This a Boundary?

Treat it as a boundary if any are true:
- External user or "can't break it easily" constraint exists (real or simulated).
- It is a versioned or durable surface: CLI UX, file formats, schemas, API routes, library interfaces, wire protocols.
- Many internal call sites depend on it (even if you control them).
- It crosses an ownership/team/component boundary, or is intended for reuse.

If it is not a boundary, proceed with normal refactoring discipline; still prefer small interfaces, but optimization pressure is lower.

### 2) Name the Contract

Write down (in the PR/spec notes):
- Producer and consumers.
- What makes it hard to change (upgrade constraints, external users, data already written, etc.).
- What is explicitly NOT promised.
- Stability target: experimental vs stable vs "public".

### 3) Shape the Boundary (Avoid Leaks)

Design inputs/outputs around the minimal information needed for the consumer use cases.
- Prefer passing the specific fields you need over passing whole "domain objects" (avoid information leaks).
- Avoid "debug" fields/flags/params that expose producer internals; they get depended upon.
- Avoid boolean-flag APIs at boundaries; name operations and concepts instead.
- Prefer fewer dependencies: the most important thing is what the boundary does NOT depend on.

### 4) Check Dependency Direction and Ownership

For the proposed contract:
- Verify dependency direction matches the intended layering.
- Ensure the consumer does not need to know producer implementation details.
- If a refactor redraws boundaries, call out migration cost and expected unforeseen consequences.

### 5) Versioning / Backwards Compatibility

If the boundary is durable (CLI/schema/artifact formats/APIs):
- Decide whether to version (and how).
- Decide how to deprecate: timeline, migration plan, compatibility shims.
- Prefer adding new surface area over breaking existing callers unless the break is justified and planned.

### 6) Produce the "Boundary Review" Output

Add a short section to the work product (spec/PR description) using this template:

```
## Boundary Review
- Boundary surface(s):
- Producer / consumers:
- Why it's a boundary (what makes it hard to change):
- Contract proposed (inputs/outputs, promises, non-promises):
- Potential information leaks / coupling risks:
- Dependency direction / layering notes:
- Versioning / migration plan (if applicable):
- Alternatives considered:
```

If the user is trying to define repo boundary rules, also output:

```
## Candidate Repo Boundary Rules (Draft)
1. ...
```

## Deep References (Load Only If Needed)

Use these repo notes when you need more detail or examples:
- `docs/research/system_boundaries/boundary-drawing.md` (boundaries are invented; reconsider deliberately; redrawing is costly)
- `docs/research/system_boundaries/system_boundariees_the_focus_of_design.md` (what makes a boundary; why rules differ at boundaries; boundaries are not free)
- `docs/research/system_boundaries/good-software-architectures-are-mostly-about-boundaries.md` (boundaries as contracts; information leaks; examples of "debug" surface area becoming dependency)

## Notes
- This skill is intended for use inside this repo; references assume the repo workspace is available.
- Do not turn draft "boundary rules" into normative repo contracts without explicit user approval; propose, discuss, then encode in docs/spec/tests.
