# Video Kit

`packages/video-kit/` contains reusable visual primitives extracted from prior
projects.

## Current Modules

- `terminal/`
  - `TerminalWindow`
  - `ScrollingTerminal`
  - `TypingText`
  - `MouseCursor`
  - terminal line types and theme tokens
- `lux-ui/`
  - `DashboardLayout`
  - `StatsBar`
  - `FilterBar`
  - `Timeline`
  - `TimelineEvent`
  - `RunsPanel`
  - dashboard types and theme tokens

## Scope Rules

- Keep visual primitives and reusable data types in `video-kit`.
- Keep campaign scenes, story-specific text, and project assets in each project.
