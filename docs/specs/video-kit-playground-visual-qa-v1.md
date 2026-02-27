# Spec: Video Kit Playground Visual QA V1

Status: implemented
Owner: codex
Created: 2026-02-27
Last updated: 2026-02-27

## Problem
`video-kit` now contains reusable terminal and Lux UI primitives, but there is
no dedicated project to visually inspect these components in isolation before
using them in campaign videos.

## Goals
- Add a permanent Remotion playground project for visual QA of `video-kit`.
- Provide showcase compositions that instantiate terminal and Lux UI components.
- Keep the playground decoupled from `kalshi_spawns` and campaign content.

## Non-Goals
- Producing a final marketing video.
- Retrofitting existing projects to use `video-kit`.
- Adding snapshot tests for visuals.

## User Experience
- Open Remotion Studio in `projects/video_kit_playground` and inspect:
  - Terminal showcase composition.
  - Lux UI showcase composition.
- Scrub timeline to verify component appearance and animation behavior.

## Design
- Create project: `marketing/remotion/projects/video_kit_playground`.
- Add compositions:
  - `VideoKitTerminalShowcase`
  - `VideoKitLuxUiShowcase`
- Import components from `marketing/remotion/packages/video-kit/src`.
- Add sample local data in the playground project only.

## Data / Schema Changes
- Adds a new project directory under `marketing/remotion/projects/`.
- No product/runtime schema changes.

## Security / Trust Model
- No trust model changes.

## Failure Modes
- Relative imports to `video-kit/src` could break if directory layout changes.
  - Mitigation: keep this project in the same workspace and treat it as a
    maintenance canary for kit API/layout changes.

## Acceptance Criteria
- `video_kit_playground` exists with dedicated terminal and Lux UI compositions.
- Compositions import and render `video-kit` components.
- `npm run lint` in the playground succeeds after dependency install.

## Test Plan
- Manual verification:
  - Install dependencies in `projects/video_kit_playground`.
  - Run `npm run lint`.
  - Run `npm run dev` and confirm both showcase compositions load.

## Rollout
- Land as a development-only visual QA tool.

## Open Questions
- Whether to add a combined “all-components” showcase composition later.
