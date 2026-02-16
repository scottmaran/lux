# `ebpf_filtering.yaml` (eBPF Filter Config)
Layer: Contract

This file configures the eBPF filter stage (`collector-ebpf-filter`), which:
- reads raw eBPF events (`ebpf.jsonl`),
- uses raw audit exec lineage (`audit.log`) to maintain an ownership PID tree,
- attributes events to `session_id`/`job_id`,
- emits `ebpf.filtered.v1` JSONL.

File:
- `collector/config/ebpf_filtering.yaml`

Schema:
- Output schema contract: `docs/contracts/schemas/ebpf.filtered.v1.md`

## Runtime wiring (env overrides)
In container runs, `compose.yml` and/or the collector entrypoint can override
config paths and inputs/outputs via env vars:

- `COLLECTOR_EBPF_FILTER_CONFIG`: config file path
- `COLLECTOR_AUDIT_LOG`: raw audit log path (input; used for exec lineage)
- `COLLECTOR_EBPF_LOG`: raw eBPF JSONL path (input)
  - In this repo, `compose.yml` sets `COLLECTOR_EBPF_OUTPUT` for the loader,
    and the entrypoint passes that through to the filter as `COLLECTOR_EBPF_LOG`.
- `COLLECTOR_EBPF_FILTER_OUTPUT`: filtered eBPF JSONL path (output)
- `COLLECTOR_SESSIONS_DIR`: run-scoped sessions metadata directory
- `COLLECTOR_JOBS_DIR`: run-scoped jobs metadata directory
- `COLLECTOR_ROOT_COMM`: comma-separated root comm override (overrides `ownership.root_comm` when set)

Note:
- The shipped YAML defaults can look "flat" (`/logs/...`). In real runs they
  are overridden to run-scoped paths under
  `/logs/${LASSO_RUN_ID:-lasso__adhoc}/...` (host equivalent:
  `<log_root>/<run_id>/...`).

## Key fields (current)

`schema_version`
- The schema version string written into each output row (default:
  `ebpf.filtered.v1`).

`input.audit_log` / `input.ebpf_log`
- Paths to raw logs. Often overridden by:
  - `COLLECTOR_AUDIT_LOG`
  - `COLLECTOR_EBPF_OUTPUT` / `COLLECTOR_EBPF_LOG`

`sessions_dir` / `jobs_dir`
- Paths to harness metadata directories, used to map events to `session_id` or
  `job_id` based on root PID/SID markers.

`ownership.uid`
- Default UID for agent-owned events (commonly 1001).

`ownership.root_comm`
- Process names treated as eligible "roots" for agent ownership heuristics.

`ownership.pid_ttl_sec`
- Optional PID TTL (seconds) to reduce PID reuse attribution risk (0 disables).

`ownership.exec_keys`
- Audit rule keys that represent exec events in `audit.log` (default `exec`).

`include.event_types`
- Which raw event types to keep (for example `net_connect`, `dns_query`, `unix_connect`).

`exclude.*`
- Suppression lists to drop known noise (`comm`), unix socket paths, and/or
  destination ports/IPs.

`linking.attach_cmd_to_net`
- If enabled, the filter attaches a best-effort `cmd` string to network events
  by reusing the last seen audit exec `cmd` for the same PID.

`pending_buffer`
- Optional bounded buffer used in follow mode to hold early events that arrive
  before ownership is known.
- Controls:
  - `enabled`
  - `ttl_sec`
  - `max_per_pid`
  - `max_total`

## Follow mode note
The collector runs the eBPF filter with `--follow` in normal deployments so it:
- continuously tails audit exec events to keep the PID ownership tree current,
- continuously tails `ebpf.jsonl` for new events.
