# Run-Scoped Log Layout
Layer: Contract

Lasso writes logs under one directory per `lasso up` lifecycle:

```text
<log_root>/
  lasso__YYYY_MM_DD_HH_MM_SS/
    collector/
      raw/
        audit.log
        ebpf.jsonl
      filtered/
        filtered_audit.jsonl
        filtered_ebpf.jsonl
        filtered_ebpf_summary.jsonl
        filtered_timeline.jsonl
    harness/
      sessions/
        <session_id>/
          meta.json
          stdin.log
          stdout.log
          filtered_timeline.jsonl
      jobs/
        <job_id>/
          input.json
          status.json
          stdout.log
          stderr.log
          filtered_timeline.jsonl
      labels/
        sessions/
        jobs/
```

Notes:
- The active run is the current stack lifecycle started by `lasso up`.
- `lasso logs ...` and `lasso jobs ...` default to the active run.
- For historical inspection, use `--run-id <id>` or `--latest`.
- `lasso down` clears active-run state; historical run directories remain on disk.
- In manual `docker compose` workflows, export one shared `LASSO_RUN_ID` for collector/harness commands so artifacts stay in the same run directory.
- For UI defaults in manual workflows, write `<log_root>/.active_run.json` or pass explicit `run_id` selectors.
