# Lasso VM Layout (VM + Containers, Host Sink)

## Purpose
- Provide a consistent local deployment that produces auditable, structured logs for third-party agents.
- Keep the same log schema and harness behavior across local and enterprise installs.

## Topology (conceptual)
```text
Host OS
  ├─ Log sink (default: ~/lasso-logs)
  └─ Linux VM
      ├─ Harness container (orchestrates agent)
      ├─ Agent container (third-party agent)
      ├─ Collector container (OS audit)
```

## Components and responsibilities
- Harness container
  - Launches and attaches to the agent container, capturing stdout/stderr (PTY for interactive).
  - Writes session-level logs (session ID, stdout/stderr, optional stdin) to the host sink.
  - Connects to the agent container over SSH (internal-only) to start sessions and capture I/O.

- Agent container
  - Runs the third-party agent.
  - Has read-only access to logs for live inspection; no write access to the sink.

- Collector container
  - Runs auditd rules for exec + file changes + metadata changes.
  - Runs a custom eBPF loader for network egress + IPC connection metadata (plus DNS lookups when available).
  - Emits audit and eBPF events with PID/PPID + timestamps.

- Log sink (storage)
  - Host directory outside the VM.
  - Writable by harness/collector; read-only to the agent.
  - Runtime artifacts are grouped by run under `/logs/lasso__YYYY_MM_DD_HH_MM_SS/...`.

## Mounts and permissions (exact model)
Host directories
- ~/lasso-workspace  (user workspace, normal read/write; default)
- ~/lasso-logs       (log sink, protected; default)

VM mounts
- /vm/workspace  -> host ~/lasso-workspace (rw)
- /vm/logs       -> host ~/lasso-logs      (rw for harness/collector)

Agent container mounts
- /work  -> /vm/workspace (rw for agent)
- /logs  -> /vm/logs (ro for agent)

Harness container mounts
- /work  -> /vm/workspace (rw)
- /logs  -> /vm/logs (rw)
- /harness/keys -> shared volume with agent for authorized_keys (rw)

Permission model inside agent container
- Agent runs as uid 1001 with no write permission to /logs.
- /logs owned by harness uid or root, mode 0755.
- The agent user is not in the logs group.
- Drop CAP_SYS_ADMIN and set no_new_privs to prevent remounting /logs as rw.

Collector container mounts
- /logs -> /vm/logs (rw, writes audit and eBPF events)
- /work -> /vm/workspace (ro, required to load auditd path watches)
- /sys/fs/bpf -> /sys/fs/bpf (rw, eBPF maps/programs)
- /sys/kernel/tracing -> /sys/kernel/tracing (rw, tracefs if mounted here)
- /sys/kernel/debug -> /sys/kernel/debug (rw, debugfs/tracefs access)

## Event flow
1) Harness starts, creates session_id, writes session header to /logs.
2) Harness creates the agent container with /logs mounted read-only and attaches to its stdio.
3) Collector runs auditd for exec + file changes + metadata and eBPF (custom loader) for network + IPC (plus DNS lookups when available).
4) Harness logs stdout/stderr in parallel; agent can read /logs during the session.
5) Log merger (optional) correlates by PID/session_id into a unified timeline.

## Minimal compose sketch (inside VM)
```yaml
version: "3.8"
services:
  agent:
    image: ghcr.io/scottmaran/lasso-agent:${LASSO_VERSION}
    volumes:
      - /vm/workspace:/work:rw
      - /vm/logs:/logs:ro
      - harness_keys:/config:ro

  harness:
    image: ghcr.io/scottmaran/lasso-harness:${LASSO_VERSION}
    volumes:
      - /vm/workspace:/work:rw
      - /vm/logs:/logs:rw
      - harness_keys:/harness/keys:rw
    environment:
      - LASSO_RUN_ID=lasso__2026_02_12_12_23_54
      - HARNESS_LOG_DIR=/logs/${LASSO_RUN_ID}/harness
      - HARNESS_TIMELINE_PATH=/logs/${LASSO_RUN_ID}/collector/filtered/filtered_timeline.jsonl
      - HARNESS_AGENT_WORKDIR=/work
    ports:
      - 127.0.0.1:8081:8081
    depends_on:
      - agent
    # Harness connects to the agent via SSH for TTY and non-interactive runs.

  collector:
    image: ghcr.io/scottmaran/lasso-collector:${LASSO_VERSION}
    privileged: true
    pid: "host"
    volumes:
      - /vm/logs:/logs:rw
      - /vm/workspace:/work:ro
      - /sys/fs/bpf:/sys/fs/bpf:rw
      - /sys/kernel/tracing:/sys/kernel/tracing:rw
      - /sys/kernel/debug:/sys/kernel/debug:rw
    environment:
      - LASSO_RUN_ID=lasso__2026_02_12_12_23_54
      - COLLECTOR_AUDIT_LOG=/logs/${LASSO_RUN_ID}/collector/raw/audit.log
      - COLLECTOR_EBPF_OUTPUT=/logs/${LASSO_RUN_ID}/collector/raw/ebpf.jsonl

volumes:
  harness_keys:
```

## Notes
- The agent should never run with write access to /logs; mount it read-only.
- The harness uses SSH to control the agent container; it does not require container runtime access.
- The collector needs privileged + pid: host with access to bpffs and tracefs/audit interfaces.
- Ensure tracefs is mounted in the VM (commonly /sys/kernel/tracing or /sys/kernel/debug/tracing).
- Only one audit daemon can consume audit events; the collector should be the sole audit consumer in the VM.
- Auditd emits raw audit logs; normalization to JSONL happens in a later processing step.
- Trust boundary: the host is trusted; the agent container is untrusted; VM root is out of scope.
- Host log export is the host-mounted `~/lasso-logs` directory by default (configurable via `LASSO_LOG_ROOT`).
- If you add an HTTP proxy later, enforce its use with firewall rules so the agent cannot bypass it.
