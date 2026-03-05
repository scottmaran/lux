# Review Workflow

This document defines how agents should review Remotion outputs in this
workspace.

## Scope

- Applies to work under `marketing/remotion/`.
- Focuses on agent review methods and artifact generation.

## Standard Agent Methods

- Use Remotion-native CLI commands for review:
  - `npx remotion compositions`
  - `npx remotion still <composition-id> <output.png> --frame=<n>`
  - `npx remotion render <composition-id> <output.mp4>` only when explicitly needed
- Prefer `remotion still` for targeted, frame-accurate visual checks.
- Do not default to full video renders during review.

## Disallowed By Default

- Do not install additional system-wide review tools for frame extraction,
  playback, or transcoding.
- Do not rely on non-Remotion binaries for default review loops.
- Exception: only if explicitly approved by the user for a specific task.

## Review Artifact Convention

- Write review artifacts under:
  - `projects/<project-name>/out/review/`
- Keep filenames descriptive and frame-aware when possible:
  - `terminal_f156.png`
  - `luxui_f220.png`

## Feedback Format

- Use composition + frame/time references in feedback:
  - `VideoKitTerminalShowcase frame 156: cursor too low`
  - `VideoKitLuxUiShowcase 00:02.1: timeline header contrast is weak`
