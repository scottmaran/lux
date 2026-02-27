# Spec: `kalshi_demo` Strict-Parity Rebuild Using `video-kit`

## Metadata
- Date: 2026-02-27
- Status: Draft
- Agent Class: Create Spec
- Legacy Reference: `projects/kalshi_spawns/`
- New Project Target: `projects/kalshi_demo/`

## Goal
Create a new Remotion project named `kalshi_demo` that reproduces the rendered output of `kalshi_spawns` with strict parity, while replacing reusable legacy UI/terminal primitives with imports from `packages/video-kit`.

## User Decisions (Locked)
1. Visual/runtime parity must be strict (not approximate).
2. Project must be scaffolded via `npm run new-video -- --name kalshi_demo`.
3. Components that are not currently in `video-kit` stay project-local.
4. Code structure and naming may be cleaned up; rendered output is the compatibility contract.
5. Assets can be reused by copying into `kalshi_demo/public`.
6. First pass ends with manual user review of the video; stricter review process can be decided after feedback.

## Scope
### In Scope
- Scaffold `kalshi_demo` from template.
- Port story/scenes/timings/content from `kalshi_spawns`.
- Replace legacy reusable primitives with `video-kit` imports:
  - `TerminalWindow`
  - `ScrollingTerminal`
  - `TypingText`
  - `MouseCursor`
  - `DashboardLayout`
  - `StatsBar`
  - `FilterBar`
  - `Timeline`
  - `TimelineEvent`
  - `RunsPanel`
- Copy required public assets from `kalshi_spawns/public` into `kalshi_demo/public`.
- Preserve all scene durations, sequencing, cue timings, and composition dimensions/fps.

### Out of Scope
- Extracting new primitives into `video-kit` as part of this migration.
- Changing the narrative/copy/tone/content of the video.
- Introducing automated frame diffing in this first pass.

## Non-Negotiable Parity Contract
The rendered behavior of `kalshi_demo` must match `kalshi_spawns` on:
- Video config: `1920x1080`, `60fps`, total frames `1325`.
- Scene frame allocation:
  - chaos: `475`
  - overlay: `110`
  - sceneTransition: `180`
  - dashboard: `360`
  - brand: `200`
- Scene ordering and sequencing in `FullTerminalVideo`.
- Timing of command typing, cursor movement/click pulses, terminal spawns, and dashboard state transitions.
- Audio cue timing and source files used by scene logic.

## Migration Strategy
### 1. Project Creation and Baseline
- Run scaffold command:
  - `npm run new-video -- --name kalshi_demo`
- Install project dependencies inside `projects/kalshi_demo`.
- Set up `kalshi_demo` composition root and IDs as needed for clarity.

### 2. Asset Copy
Copy campaign-specific assets from `projects/kalshi_spawns/public` to `projects/kalshi_demo/public`, including:
- `macos-desktop.svg`
- `typing_sound_effect_trim.m4a`
- `bubble_popping_trim.m4a`
- `mouse_click_trim.m4a`
- `rotate_whoosh_trimmed.m4a`
- Any additional file currently referenced by scene code.

### 3. Code Port with `video-kit` Primitives
- Recreate project-local config and scene files in `kalshi_demo`.
- Replace legacy imports from `kalshi_spawns/src/components/*` with imports from `packages/video-kit/src` for covered primitives.
- Keep project-local components for non-kit behavior:
  - `Callout`
  - audio wrappers such as `MouseClickSfx` and `TerminalPopSfx`
  - any scene-specific helpers not in `video-kit`

### 4. Cleanup and Naming
- Rename/refactor files and composition IDs for clarity where useful.
- Preserve behavior, timing, and rendered output as the governing contract.

### 5. First-Pass Review Output
- Produce a first-pass render artifact for user review.
- No automated diff is required for this pass.

## Component Mapping Contract
- `kalshi_spawns/src/components/TerminalWindow.tsx` -> `video-kit` `TerminalWindow`
- `kalshi_spawns/src/components/ScrollingTerminal.tsx` -> `video-kit` `ScrollingTerminal`
- `kalshi_spawns/src/components/TypingText.tsx` -> `video-kit` `TypingText`
- `kalshi_spawns/src/components/MouseCursor.tsx` -> `video-kit` `MouseCursor`
- `kalshi_spawns/src/components/Dashboard/*` -> `video-kit` `DashboardLayout` and subcomponents
- `Callout`, `MouseClickSfx`, `TerminalPopSfx` remain local to `kalshi_demo`

## Verification Plan (First Pass)
### Required Local Checks
1. `npm install` in `projects/kalshi_demo`
2. `npm run lint` in `projects/kalshi_demo`
3. `npx remotion compositions`
4. Render first-pass video from `kalshi_demo` composition for manual review.

### Manual Review Focus
Validate parity at representative timeline points:
1. initial terminal scene setup and first prompt typing
2. worker terminal spawn sequence and pop SFX sync
3. discovery/warning highlight moments
4. transition command terminal and dashboard launch
5. dashboard run switches and click cues
6. brand outro fade/stripes/whoosh timing

## Risks and Mitigations
- Risk: minor styling drift from theme defaults.
  - Mitigation: explicitly pass `video-kit` theme overrides only where needed to match legacy values.
- Risk: subtle timing drift from refactors.
  - Mitigation: preserve numeric timing constants from legacy project and avoid "cleanup" changes to timing math.
- Risk: missing copied assets causing silent fallback differences.
  - Mitigation: verify `staticFile()` references resolve in `kalshi_demo/public`.
