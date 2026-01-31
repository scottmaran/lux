# UI Design - Agent Harness Log Viewer

## Goals
- Read-only UI for inspecting what agent runs did and when.
- Fast scan: select a session, see the correlated logs immediately.
- Support very large logs with virtualization and paged loading.
- Keep the architecture ready for live tailing later without a rewrite.
- Keep the prototype minimal: zero-build static UI + tiny HTTP API.

## Layout
- Full-width top band for summary and controls.
- Two vertical columns beneath:
  - Left (dominant width): log timeline.
  - Right (narrow rail): session & jobs list and metadata expansion.

## Top Band (Summary and Controls)
- Summary tiles (current view): counts for exec, fs_create, fs_unlink, fs_meta, net_summary, unix_connect.
- Source toggles: Audit, eBPF (Proxy reserved for later).
- Event type filters reflect the timeline schema (see below).
- Time controls:
  - Presets: 15m, 1h, 24h, 7d.
  - Absolute range picker.
- Live tail control is present but can be disabled in the prototype.
- Run scope filter: Sessions / Jobs / Unattributed.

## Runs Column (Right)
- Combined list (sessions + jobs) sorted by `started_at`.
- Sessions from `logs/sessions/*/meta.json`.
- Jobs from `logs/jobs/*/input.json` + `status.json`.
- Each row shows:
  - `session_id` or `job_id`
  - `mode` (tui or exec) for sessions
  - `status`, `exit_code`
  - `started_at`, `ended_at`, duration
- Selecting a session expands it to reveal `meta.json` fields.
- Selecting a job expands it to reveal `input.json` + `status.json` fields.
- Selecting a run filters the log timeline by `session_id` or `job_id`.
  - Time range can auto-scope to run start/end but ID filtering is primary.

## Logs Column (Left)
- Virtualized timeline list for performance.
- Default row fields:
  - Timestamp (RFC3339 with sub-second precision)
  - Source (audit or ebpf)
  - Event type
  - Process (`comm`, `pid`, `ppid`)
  - Target (derived from `details`, see schema below)
- No event inspector in phase 1.

### Target Derivation (from `details`)
- `exec`: `details.cmd` (secondary: `details.cwd`)
- `fs_create` / `fs_unlink` / `fs_meta`: `details.path` (secondary: `details.cmd`)
- `net_summary`: `details.dst_ip:dst_port` + `details.dns_names`
- `unix_connect`: `details.unix.path`

## Data Sources
- `logs/filtered_timeline.jsonl`
  - Unified, filtered timeline used by the UI (schema `timeline.filtered.v1`).
- `logs/filtered_audit.jsonl`
  - Filtered audit events (schema `auditd.filtered.v1`), primarily for debugging.
- `logs/filtered_ebpf.jsonl`
  - Filtered eBPF events (schema `ebpf.filtered.v1`), primarily for debugging.
- `logs/sessions/<session_id>/meta.json`
  - Session metadata used in the session list.
- `logs/jobs/<job_id>/input.json` and `status.json`
  - Job metadata used in the run list.
- `logs/sessions/<session_id>/stdin.log` and `stdout.log`
  - Session IO streams (not shown in phase 1).
- `logs/jobs/<job_id>/stdout.log` and `stderr.log`
  - Job IO streams (not shown in phase 1).

## Normalization Rules
- Normalization and merging are handled by the collector.
- The UI consumes `filtered_timeline.jsonl` directly.
- Each row uses the timeline schema:
  - Common fields: `session_id`, optional `job_id`, `ts`, `source`, `event_type`, `pid`, `ppid`, `uid`, `gid`, `comm`, `exe`.
  - Event-specific data lives under `details`.
- Timeline sort order is stable: `ts`, then `source`, then `pid`.

## Filtering Model
- Run selection filters by `session_id` or `job_id` from timeline rows.
- Top band filters further narrow the stream by source and event type.
- Time filters are additive (apply within the selected run or overall).
- Default view shows all sources with the last 24h selected.
- Unattributed events use `session_id: "unknown"` and no `job_id`.

## Performance Expectations
- Use virtualization for the log list.
- Page by cursor or time range, not by loading whole files in the browser.
- Summary counts can be limited to the current time window or loaded page for the prototype.

## Live Tailing Considerations
- Use a cursor-based API shape now (even if implemented by polling).
- UI log list should be append-only in live mode with pause/resume.
- Cursor should be based on `ts` + `source` + `pid` (not file offsets), because the merged timeline file is regenerated.
- When tailing, re-request a small overlap window to avoid missing late-arriving events; dedupe client-side.
- Later swap polling for SSE or WebSocket without changing the UI model.

## Minimal API Requirement (Prototype)
- Browsers cannot read `/logs/*` directly; the UI must call a tiny HTTP API.
- Minimal endpoints:
  - `GET /api/timeline?start=...&end=...` (time window) or `GET /api/timeline?limit=...&before_ts=...`
  - `GET /api/sessions` (from `logs/sessions/*/meta.json`)
  - `GET /api/jobs` (from `logs/jobs/*/input.json` + `status.json`)
  - Optional: `GET /api/summary?start=...&end=...` for top-band counts

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
