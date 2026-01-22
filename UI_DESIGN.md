# UI Design - Agent Harness Log Viewer

## Goals
- Read-only UI for inspecting what agent runs did and when.
- Fast scan: select a session, see the correlated logs immediately.
- Support very large logs with virtualization and paged loading.
- Keep the architecture ready for live tailing later without a rewrite.

## Layout
- Full-width top band for summary and controls.
- Two vertical columns beneath:
  - Left (dominant width): log timeline.
  - Right (narrow rail): session list and metadata expansion.

## Top Band (Summary and Controls)
- Summary tiles: counts for exec, fs change, fs meta, net, unix, stdout, stdin.
- Source toggles: Audit, eBPF, Stdout, Stdin.
- Event type filters: exec, fs change, fs meta, net, unix.
- Time controls:
  - Presets: 15m, 1h, 24h, 7d.
  - Absolute range picker.
- Live tail control is present but can be disabled in the prototype.

## Sessions Column (Right)
- List sessions from `logs/sessions/*`.
- Each row shows:
  - `session_id`
  - `mode` (tui or exec)
  - `started_at`, `ended_at`, duration
  - `exit_code` and status badge
- Selecting a session expands it to reveal `meta.json` fields.
- Selecting a session filters the log timeline by session time window.
  - If `ended_at` is missing, treat the window as ongoing.

## Logs Column (Left)
- Virtualized timeline list for performance.
- Default row fields:
  - Timestamp (normalized to ISO)
  - Source (audit or ebpf)
  - Event type
  - Process (`comm`, `pid`, `ppid`)
  - Target (file path, host, socket, or syscall detail)
- No event inspector in phase 1.

## Data Sources
- `logs/audit.log` and `logs/example_audit.log`
  - Raw auditd text lines, multiple lines per event.
- `logs/ebpf.jsonl` and `logs/example_ebpf.jsonl`
  - JSONL, one event per line.
- `logs/sessions/<session_id>/meta.json`
  - Session metadata used in the session list.
- `logs/sessions/<session_id>/stdin.log` and `stdout.log`
  - Session IO streams (not shown in phase 1).

## Normalization Rules
- Audit events are grouped by `msg=audit(epoch:sequence)` into a single row.
- Audit event type uses `key=` when present (exec, fs_change, fs_meta).
- eBPF events use `event_type` (net_connect, unix_connect, etc).
- All timestamps normalize to ISO UTC for sorting and filtering.
- Final timeline sort order: timestamp, then stable tiebreaker.

## Filtering Model
- Session selection applies a time window filter.
- Top band filters further narrow the stream by source and event type.
- Default view shows all sources with the last 24h selected.

## Performance Expectations
- Use virtualization for the log list.
- Page by cursor or time range, not by loading whole files.
- Precompute summary counts for the top band.

## Live Tailing Considerations
- Use a cursor-based API shape now (even if implemented by polling).
- UI log list should be append-only in live mode with pause/resume.
- Later swap polling for SSE or WebSocket without changing the UI model.

## Phase 1 Non-Goals
- No event inspector panel.
- No correlation accuracy or integrity warnings.
- No TUI playback or transcript view.
- No annotations or export tools.

## Visual System (Swiss Style)
- Canvas background: #F0F0E8 with high contrast black borders.
- Panels: #E5E5E0 and #FFFFFF.
- Typography:
  - Headers: serif, bold, tight tracking.
  - Body: clean sans serif.
  - Meta labels: mono, uppercase, tracking wide.
- Shapes:
  - Square corners only.
  - 1px black borders.
  - Hard shadows only.
- Labels and status use bracket syntax like `[ STATUS: READY ]`.
