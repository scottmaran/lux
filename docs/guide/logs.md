# Logs Guide

This guide explains where logs live, how `lasso logs` reads them, and why
`lasso logs stats` can show zeros while a session is still running.

## Log root layout (default)
The log root is configured in `~/.config/lasso/config.yaml` under
`paths.log_root` (default: `~/lasso-logs`). Common paths:

- `audit.log` – raw auditd stream from the collector.
- `ebpf.jsonl` – raw eBPF stream from the collector.
- `filtered_timeline.jsonl` – merged, UI-friendly timeline output.
- `sessions/<id>/` – TUI session logs and metadata.
- `jobs/<id>/` – server-mode job logs and metadata.
- `labels/` – optional display-name labels for sessions/jobs.

## `lasso logs stats`
`lasso logs stats` estimates average MB/hour based on **completed TUI
sessions only**.

What it reads:
- `logs/sessions/*/meta.json`

Requirements to count a session:
- `started_at` and `ended_at` must both exist (RFC3339 timestamps).
- Duration must be greater than zero.

What it ignores:
- **Running** TUI sessions (no `ended_at` yet).
- **Jobs** under `logs/jobs/*`.

So if you run `lasso logs stats` while a TUI session is still open, it is
expected to return zeroes. End the session and rerun to see populated
values.

## `lasso logs tail`
Use this to quickly inspect log streams:

```bash
lasso logs tail --file audit
lasso logs tail --file ebpf
lasso logs tail --file timeline
```

`--file` can also be a path relative to the log root.

## Troubleshooting zero stats
1) Confirm the log root in `~/.config/lasso/config.yaml`.
2) Check for `ended_at` in `logs/sessions/<id>/meta.json`.
3) If you only ran `lasso run` jobs, use `lasso jobs list/get` instead.
