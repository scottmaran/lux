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
- `codex-session/`
  - `CodexSession`
  - source-replica preset for `codex_session_source.mp4`
  - typed row/timeline configuration for reusable Codex session visuals
  - optional cursor blink, thinking-state emphasis animation, and event-driven
    row-push motion controls
  - optional footer input cursor controls for post-session typing state

## Scope Rules

- Keep visual primitives and reusable data types in `video-kit`.
- Keep campaign scenes, story-specific text, and project assets in each project.
