# Spec: Remotion Shared Skills Canonicalization V1

Status: implemented
Owner: codex
Created: 2026-02-27
Last updated: 2026-02-27

## Problem
The `remotion-best-practices` skill currently lives inside a single legacy
project path (`projects/kalshi_spawns/.agents/skills/`). As additional video
projects are created, this causes discoverability and maintenance problems
because the shared skill source is not in a workspace-level location.

## Goals
- Create a workspace-level canonical skills directory under `marketing/remotion`.
- Make `remotion-best-practices` available from the canonical location.
- Keep existing project-local legacy copies available for reference.
- Update Remotion docs to point to the canonical skill path.

## Non-Goals
- Rewriting skill content.
- Removing legacy project-local skill directories.
- Adding skill execution automation.

## User Experience
- Users and agents can find shared Remotion skills in one place:
  - `marketing/remotion/skills/`
- Legacy project-local skills still exist but are documented as non-canonical.

## Design
- Add `marketing/remotion/skills/` with:
  - `README.md`
  - `remotion-best-practices/` (copied from legacy project path)
- Update docs:
  - `marketing/remotion/README.md`
  - `marketing/remotion/docs/architecture.md`
  - `marketing/remotion/docs/conventions.md`
  - `marketing/remotion/docs/scaffold-workflow.md`
  - `marketing/remotion/projects/README.md`
- Add a note file in the legacy skills directory clarifying canonical location.

## Data / Schema Changes
- Directory layout adds `marketing/remotion/skills/`.
- No schema/API/runtime behavior changes.

## Security / Trust Model
- No trust-boundary changes.

## Failure Modes
- Divergence risk if legacy and canonical copies are edited independently.
  - Mitigation: docs define canonical update path.

## Acceptance Criteria
- `marketing/remotion/skills/remotion-best-practices/SKILL.md` exists.
- Remotion docs reference `marketing/remotion/skills/` as canonical.
- Legacy project-local skills remain available.

## Test Plan
- Manual verification:
  - Confirm canonical files exist under `marketing/remotion/skills/`.
  - Confirm docs mention `skills/` as canonical path.
  - Confirm legacy skill files still exist in `projects/kalshi_spawns/`.

## Rollout
- Land as a branch-only workspace-structure update.

## Open Questions
- Whether to eventually remove legacy skill copies once all workflows use
  canonical paths.
