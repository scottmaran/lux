# @lux/video-kit

Shared Remotion visual primitives for Lux marketing videos.

This package is workspace-local (`private: true`) and intended for reuse across
projects under `marketing/remotion/projects/`.

## Available Modules

### `terminal`

Components:
- `TerminalWindow`
- `ScrollingTerminal`
- `TypingText`
- `MouseCursor`

Types:
- `TerminalLineStyle`
- `TerminalLine`
- `TerminalPrefixColorMap`
- `TerminalTheme`

Theme export:
- `DEFAULT_TERMINAL_THEME`

### `lux-ui`

Components:
- `DashboardLayout`
- `StatsBar`
- `FilterBar`
- `Timeline`
- `TimelineEvent`
- `RunsPanel`

Types:
- `DashboardRun`
- `DashboardMetrics`
- `DashboardTimelineEvent`
- `DashboardTimeRange`
- `LuxUiTheme`

Theme export:
- `DEFAULT_LUX_UI_THEME`

### `audio`

Exports:
- `AudioCue` (type)
- `EMPTY_AUDIO_LIBRARY`

### `codex-session`

Components:
- `CodexSession`

Types:
- `CodexSessionProps`
- `CodexSessionPreset`
- `CodexSessionCommandStep`
- `CodexSessionRow`
- `CodexSessionRowPart`
- `CodexSessionRowPush`
- `CodexSessionCardConfig`
- `CodexSessionTheme`

Theme export:
- `DEFAULT_CODEX_SESSION_THEME`

Preset exports:
- `CODEX_SESSION_SOURCE_REPLICA` (translation of `codex_session_source.mp4`)

## Top-Level Exports

`src/index.ts` re-exports:
- `audio`
- `codex-session`
- `lux-ui`
- `terminal`

## Quick Usage

```tsx
import {
  TerminalWindow,
  ScrollingTerminal,
  type TerminalLine,
  DashboardLayout,
  type DashboardMetrics,
  type DashboardRun,
  type DashboardTimelineEvent,
} from '@lux/video-kit';
```

## Scope Boundaries

Included here:
- Reusable visual primitives and shared UI/terminal data types.

Not included here:
- Campaign-specific scenes
- Project-specific copy
- Project-specific assets/audio files
