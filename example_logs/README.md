# example_logs/

This directory is a snapshot of a real `lasso` **log root** (like `~/lasso-logs`).

- The currently-selected run is recorded in `example_logs/.active_run.json`.
- Each run lives at `example_logs/<run_id>/`.

Within a run, key paths are:

- Raw collector outputs:
  - `collector/raw/audit.log`
  - `collector/raw/ebpf.jsonl`
- Filtered collector outputs:
  - `collector/filtered/filtered_audit.jsonl`
  - `collector/filtered/filtered_ebpf.jsonl`
  - `collector/filtered/filtered_ebpf_summary.jsonl`
  - `collector/filtered/filtered_timeline.jsonl`
- Harness artifacts:
  - `harness/sessions/<session_id>/*`
  - `harness/labels/sessions/<session_id>.json`

Tests and docs should prefer reading `.active_run.json` (instead of hardcoding a specific run ID).
