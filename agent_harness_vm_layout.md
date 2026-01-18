# Agent Harness VM Layout (Option A: VM + Containers, Host Sink)

## Purpose
- Provide a consistent local deployment that produces verifiable logs for third-party agents.
- Keep the same log schema and harness behavior across local and enterprise installs.

## Topology (conceptual)
```text
Host OS
  ├─ Log sink (~/agent_harness/logs)
  └─ Linux VM
      ├─ Harness container (orchestrates agent)
      ├─ Agent container (third-party agent)
      ├─ Collector container (OS audit)
      └─ Proxy container (HTTP logging)
```

## Components and responsibilities
- Harness container
  - Launches and attaches to the agent container, capturing stdout/stderr (PTY for interactive).
  - Writes session-level logs (session ID, stdout/stderr, optional stdin) to the host sink.
  - Requires access to the container runtime (e.g., Docker socket) to create the agent container.

- Agent container
  - Runs the third-party agent.
  - Has read-only access to logs for live inspection; no write access to the sink.

- Collector container
  - Subscribes to kernel audit sources (exec + file changes + metadata + network + IPC).
  - Emits audit events with PID/PPID + timestamps.

- Proxy container
  - Logs HTTP method/URL/status for HTTP traffic (no payloads).
  - Emits proxy logs to the host sink.

- Log sink (storage)
  - Host directory outside the VM.
  - Writable by harness/collector/proxy; read-only to the agent.

## Mounts and permissions (exact model)
Host directories
- ~/agent_harness/workspace  (user workspace, normal read/write)
- ~/agent_harness/logs       (log sink, protected)

VM mounts
- /vm/workspace  -> host ~/agent_harness/workspace (rw)
- /vm/logs       -> host ~/agent_harness/logs      (rw for harness/collector)

Agent container mounts
- /work  -> /vm/workspace (rw for agent)
- /logs  -> /vm/logs (ro for agent)

Harness container mounts
- /work  -> /vm/workspace (rw)
- /logs  -> /vm/logs (rw)
- /var/run/docker.sock -> /var/run/docker.sock (rw)

Permission model inside agent container
- Agent runs as uid 1001 with no write permission to /logs.
- /logs owned by harness uid or root, mode 0750.
- The agent user is not in the logs group.
- Drop CAP_SYS_ADMIN and set no_new_privs to prevent remounting /logs as rw.

Collector container mounts
- /logs -> /vm/logs (rw, writes audit events)

Proxy container mounts
- /logs -> /vm/logs (rw, writes HTTP logs)

## Event flow
1) Harness starts, creates session_id, writes session header to /logs.
2) Harness creates the agent container with /logs mounted read-only and attaches to its stdio.
3) Collector logs exec + file changes + metadata + network + IPC for the VM kernel.
4) Proxy logs HTTP method/URL/status for HTTP traffic.
5) Harness logs stdout/stderr in parallel; agent can read /logs during the session.
6) Log merger (optional) correlates by PID/session_id into a unified timeline.

## Minimal compose sketch (inside VM)
```yaml
version: "3.8"
services:
  harness:
    image: agent-harness:latest
    volumes:
      - /vm/workspace:/work:rw
      - /vm/logs:/logs:rw
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - HARNESS_LOG_DIR=/logs
      - HARNESS_AGENT_IMAGE=third-party-agent:latest
      - HARNESS_AGENT_CMD=/usr/local/bin/codex
      - HARNESS_AGENT_WORKDIR=/work
      - HARNESS_AGENT_LOGS_MOUNT=/logs:ro
    depends_on:
      - proxy
    # Harness creates the agent container with TTY support and /logs mounted read-only.

  collector:
    image: harness-collector:latest
    privileged: true
    pid: "host"
    volumes:
      - /vm/logs:/logs:rw
    environment:
      - COLLECTOR_OUTPUT=/logs/audit.jsonl

  proxy:
    image: harness-proxy:latest
    volumes:
      - /vm/logs:/logs:rw
    environment:
      - PROXY_LOG=/logs/http.jsonl
```

## Notes
- The agent should never run with write access to /logs; mount it read-only.
- The harness needs container runtime access; treat it as trusted.
- The collector needs elevated privileges to observe kernel events.
- Host log export is the host-mounted ~/agent_harness/logs directory.
- Enforce proxy use with firewall rules so the agent cannot bypass it.
