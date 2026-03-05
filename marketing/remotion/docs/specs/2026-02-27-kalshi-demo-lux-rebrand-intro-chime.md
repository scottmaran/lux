# Spec: `kalshi_demo` Lux Rebrand + Intro Hook + Chime Outro

## Metadata
- Date: 2026-02-27
- Status: Draft
- Agent Class: Create Spec
- Builds On: `docs/specs/2026-02-27-kalshi-demo-video-kit-parity.md`
- Project: `projects/kalshi_demo`

## Goal
Update `kalshi_demo` creative direction with:
- complete `Lasso` -> `Lux` branding alignment
- a new 120-frame opening problem statement scene
- a brand outro treatment that removes whip/whoosh audio and uses the provided `chime_trimmed.m4a` with light-themed visuals

## User Decisions (Locked)
1. Opening text must be exactly: `Ever lose visibility into all your agents?`
2. New intro duration is exactly `120` frames.
3. Intro adds runtime (do not compress existing scenes).
4. CLI phrase is `lux logs`.
5. Replace final whoosh/whip feel with the provided `projects/kalshi_demo/public/chime_trimmed.m4a`.

## Scope
### In Scope
- Scene/timing updates for added intro runtime.
- Brand copy normalization to `Lux`.
- Command copy normalization to `lux`.
- Outro audio/visual redesign in `BrandScene` using a light motif.

### Out of Scope
- Rewriting story structure beyond the new intro scene and outro treatment.
- Changing existing terminal/dashboard narrative content unrelated to branding.

## Non-Negotiable Behavior Contract
- Composition remains `1920x1080`, `60fps`.
- Existing scene internals and timing relationships remain unchanged relative to their local scene frames.
- Only global timeline shifts from the inserted 120-frame intro.
- No whoosh/whip audio is used in the final brand scene.

## Timeline Contract
### Scene Frames
- `intro`: `120`
- `chaos`: `475`
- `overlay`: `110`
- `sceneTransition`: `180`
- `dashboard`: `360`
- `brand`: `200`

### Total Frames
- Previous: `1325`
- New: `1445`

### Global Start Frames
- intro: `0`
- chaos: `120`
- overlay: `595`
- sceneTransition: `705`
- dashboard: `885`
- brand: `1245`

## Implementation Plan
### 1. Add Intro Scene
- Create `src/scenes/ProblemIntroScene.tsx`.
- Render centered text: `Ever lose visibility into all your agents?`
- Use smooth in/out animation (opacity + subtle translateY and/or blur) over 120 frames.
- Background should transition cleanly into the subsequent dark terminal scene.

### 2. Update Timing Config
- In `src/config/timing.ts`:
  - add `SCENE_FRAMES.intro = 120`
  - include intro in `TOTAL_FRAMES`

### 3. Re-sequence Root Video
- In `src/FullTerminalVideo.tsx`:
  - insert intro sequence at frame `0`
  - shift existing sequence offsets by `SCENE_FRAMES.intro`
  - keep local scene internals unchanged

### 4. Complete Lux Branding Pass
- Replace remaining `Lasso` references in user-visible labels/IDs where applicable:
  - composition ID in `src/Root.tsx` should be Lux-branded
  - any remaining textual references in scenes/components should be Lux-branded
- Keep command phrasing as `lux logs` and `[lux] ...` status lines.

### 5. Brand Outro Redesign
- In `src/scenes/BrandScene.tsx`:
  - remove whoosh dependency and usage (`rotate_whoosh_trimmed.m4a`)
  - use `Audio` with `staticFile('chime_trimmed.m4a')`
  - add light-themed motion treatment (for example bloom/floodlight sweep) synchronized with logo reveal
  - preserve brand copy content (`Lux`, tagline) unless explicitly changed later

## Acceptance Criteria
1. New opening scene plays first for exactly 120 frames with the exact sentence.
2. Existing narrative scenes start later by 120 frames and otherwise behave the same.
3. Total composition duration is 1445 frames.
4. No whoosh/whip audio plays in the final scene; chime audio plays instead.
5. No remaining user-visible `Lasso` branding in `kalshi_demo`.

## Verification Plan
1. `npm run lint` in `projects/kalshi_demo`
2. `npx remotion compositions src/index.ts` and verify:
   - Lux-branded composition ID
   - `durationInFrames = 1445`
3. Render first pass:
   - `npx remotion render src/index.ts <composition-id> out/review/kalshi_demo_lux_intro_chime.mp4`
4. Manual review focus:
   - intro readability and pacing
   - transition from intro to terminal pop-in
   - Lux branding consistency
   - final scene light/chime feel (no whip/whoosh character)
