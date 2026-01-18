# Agent Harness VM Layout (Option A: VM + Two Containers)

## Purpose
- Provide a consistent local deployment that produces verifiable logs for third-party agents.
- Keep the same log schema and harness behavior across local and enterprise installs.

## Topology (conceptual)
```text
Host OS
  └─ Linux VM
      ├─ Agent container (harness + agent)
      └─ Collector container (OS audit)
```

## Components and responsibilities
- Agent container
  - Runs the harness as the entrypoint.
  - Harness launches the agent as a child process and captures stdout/stderr.
  - Writes session-level logs (session ID, stdout/stderr, optional stdin).

- Collector container
  - Subscribes to kernel audit sources (exec + file changes + metadata + network + IPC).
  - Emits audit events with PID/PPID + timestamps.

- Log sink (storage)
  - Host-mounted directory or remote append-only store.
  - The agent must not be able to modify stored logs.

## Mounts and permissions (exact model)
Host directories
- ~/agent_harness/workspace  (user workspace, normal read/write)
- ~/agent_harness/logs       (log sink, protected)

VM mounts
- /vm/workspace  -> host ~/agent_harness/workspace (rw)
- /vm/logs       -> host ~/agent_harness/logs      (rw for harness/collector)

Agent container mounts
- /work  -> /vm/workspace (rw for agent)
- /logs  -> /vm/logs (rw for harness, no write for agent user)

Permission model inside agent container
- Harness runs as root (or a dedicated uid that owns /logs).
- Agent runs as uid 1001 with no write permission to /logs.
- /logs owned by harness uid, mode 0750.
- The agent user is not in the logs group.

Collector container mounts
- /logs -> /vm/logs (rw, writes audit events)

## Event flow
1) Harness starts, creates session_id, writes session header to /logs.
2) Harness spawns the agent process (root drops to uid 1001 for agent).
3) Collector logs exec + file changes + metadata + network + IPC for the VM kernel.
4) Harness logs stdout/stderr in parallel.
5) Log merger (optional) correlates by PID/session_id into a unified timeline.

## Minimal compose sketch (inside VM)
```yaml
version: "3.8"
services:
  agent:
    image: agent-harness:latest
    entrypoint: ["/usr/local/bin/harness", "run", "--agent", "/usr/local/bin/codex"]
    volumes:
      - /vm/workspace:/work:rw
      - /vm/logs:/logs:rw
    environment:
      - HARNESS_LOG_DIR=/logs
    # Harness runs as root so it can write logs and drop privileges for the agent.

  collector:
    image: harness-collector:latest
    privileged: true
    pid: "host"
    volumes:
      - /vm/logs:/logs:rw
    environment:
      - COLLECTOR_OUTPUT=/logs/audit.jsonl
```

## Notes
- The agent should never run with write access to /logs.
- The collector needs elevated privileges to observe kernel events.
- Host log export is just the host-mounted ~/agent_harness/logs directory.
- Enterprise deployments can swap the sink to a remote append-only store.
