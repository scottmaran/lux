# UI Design - Lasso Log Viewer

This document describes the current UI design for the log viewer. The source of truth is the Figma redesign export in `ui/` (React + Vite). The UI is focused on fast scanning of agent activity, with lightweight inline renaming for runs via labels.

## Goals
- Provide a clean, modern, card-based interface for reviewing agent activity.
- Preserve the existing filtering and run-selection behavior.
- Keep the UI fast and responsive with a scrollable timeline.
- Support periodic auto-refresh without disrupting the user.

## Layout Overview
- **Header bar**
  - Left-aligned product title (“Lasso”) with two subtitle lines:
    “Verifiability & Auditability for your AI agents” and
    “A dedicated harness for OS-level tracking of everything your agents do”.
- **Main content (stacked sections)**
  1. **Summary Metrics**: three metric cards for Processes, File Changes, and Network Calls.
  2. **Filter Controls**: data source toggles and time range presets.
  3. **Split content**
     - **Timeline** (left, 2/3 width on large screens)
     - **Runs** (right, 1/3 width on large screens)
     - Panels are resizable on large screens via a draggable divider.

## Visual System
- **Background**: light gray (`gray-50`) for the canvas.
- **Cards**: white surfaces with soft borders (`border-gray-200`) and rounded corners (`rounded-lg`).
- **Typography**: clean sans-serif hierarchy with small supporting text in gray.
- **Accents**: blue primary accents for active states; green/purple/indigo/emerald used for event badges.
- **Icons**: lightweight line icons (lucide-react) for status, loading, and empty states.

## Summary Metrics
Three cards display aggregate counts from the currently filtered timeline:
- **Processes** = `exec` events.
- **File Changes** = `fs_create` + `fs_unlink` + `fs_meta`.
- **Network Calls** = `net_summary`.

Each card shows:
- Label
- Value (loading state renders a dash)
- Icon on the right in a tinted square.

## Filter Controls
Single card containing:
- **Data Source toggles** (multi-select): `Audit`, `eBPF`.
- **Time Range presets**: `15 min`, `1 hour`, `24 hours`, `7 days`.
- Warning banner appears if no sources are selected.

## Timeline (Left Panel)
- Card header with title, event count, and “Auto-refresh active” indicator.
- Body is a scrollable list (max height ~600px).
- Rows include:
  - Timestamp (mono, muted).
  - Source badge (Audit or eBPF).
  - Event type badge (colored by category).
  - Target/description line derived from event details.
  - Process name and PID metadata.
- Sorting: latest events first.
- States:
  - Loading spinner
  - Error state with retry
  - No sources selected
  - No events found

## Runs (Right Panel)
- Card header with title and total count.
- Scrollable list (max height ~600px).
- Each row shows:
  - Type badge (session/job).
  - Display name (if present) with inline edit affordance.
  - Truncated run ID.
  - Status badge (for jobs) and mode (for sessions).
  - Started/ended timestamps.
- Clicking a run toggles selection and filters the timeline.
- Selected row shows a subtle blue highlight and left border.
- Auto-refresh: runs list polls periodically (paused when the tab is hidden).
- Inline rename:
  - Edit icon appears on each row.
  - Clicking it swaps the name for an input field.
  - Enter/blur saves; Escape cancels; empty names are rejected.

## Behavior & Data
- **Auto-refresh**: timeline polls every 2 seconds when the tab is visible.
- **Filtering**: source + time range + selected run all combine.
- **Run selection**: filters by `session_id` or `job_id`.
- **API contract**:
  - `GET /api/timeline` → `{ rows, count }`
  - `GET /api/sessions` → `{ sessions }`
  - `GET /api/jobs` → `{ jobs }`

## Non-Goals (Phase 1)
- No event inspector panel.
- No annotation/export tools.
- No editing of evidence logs or timeline rows (run labels only).
