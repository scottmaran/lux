# Spec: Video Kit Codex Session Source Translation V1

Status: implemented
Owner: codex
Created: 2026-02-27
Last updated: 2026-02-27

## Problem
`marketing/remotion/packages/video-kit/src/codex_session_source.mp4` captures a
high-value visual style for Codex terminal sessions, but it is currently only a
raw video reference and cannot be reused parametrically in future projects.

## Goals
- Add a reusable `codex-session` module to `video-kit`.
- Translate the source look/flow into a Remotion component and preset.
- Keep the source behavior reproducible without modifying legacy projects.
- Add playground compositions to visually compare source vs replica.

## Non-Goals
- Pixel-perfect forensic parity with every source frame.
- Replacing `codex_session_source.mp4` as an archival reference asset.
- Retrofitting `kalshi_spawns`.

## User Experience
- Consumers can import `CodexSession` and the source replica preset from
  `@lux/video-kit`.
- Developers can open the playground and inspect:
  - 1:1 replica composition (`928x598`)
  - side-by-side source vs replica composition (`1920x1080`)

## Design
- Add `packages/video-kit/src/codex-session/`:
  - `types.ts`
  - `theme.ts`
  - `CodexSession.tsx`
  - `presets/sourceReplica.ts`
  - `index.ts`
- Export module via `packages/video-kit/src/index.ts`.
- Add playground compositions:
  - `CodexSessionReplica.tsx`
  - `CodexSessionComparison.tsx`
- Copy source mp4 into playground public assets for side-by-side preview.

## Data / Schema Changes
- Adds a new reusable UI module and preset contract in `video-kit`.
- No runtime schema changes outside Remotion assets/components.

## Security / Trust Model
- No trust-boundary changes.

## Failure Modes
- Visual drift from source over future edits.
  - Mitigation: retain source mp4 and side-by-side comparison composition.
- Relative import breakage in playground if directory layout changes.
  - Mitigation: keep imports explicit and validated by lint/typecheck.

## Acceptance Criteria
- `codex-session` module exists and is exported from `video-kit`.
- Source replica preset is available in `video-kit`.
- Playground includes replica and comparison compositions.
- `npm run lint` passes in `video_kit_playground`.

## Test Plan
- Manual/static verification:
  - Run `npm run lint` in `projects/video_kit_playground`.
  - Run `npm run dev` and load:
    - `VideoKitCodexSessionReplica`
    - `VideoKitCodexSessionComparison`
  - Confirm source and replica both render for full preset duration.

## Rollout
- Land as a reusable building block in the current branch.

## Open Questions
- Whether to add additional presets (for different providers/shell themes).
