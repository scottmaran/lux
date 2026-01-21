


# Prompt 

I want to create a containerized harness to produce auditable, structured logs for third-party AI agent software. This will include:
  - Process tree: exec events with args/uid/gid when available.
  - Filesystem changes: writes/renames/unlinks plus metadata changes (chmod/chown/xattr/utime); reads excluded for noise.
  - Network egress: destination/protocol/port; DNS lookups when available; HTTP(S) proxy for method/URL/status.
  - Local IPC/service: connections to local daemons (e.g. Unix domain sockets, D-Bus).
  - Stdout/stderr: captured by the harness (pipes for non-interactive, PTY for interactive).

Agents have read-only access to logs during the session and may use them.

# Summary

- Goal: build a harness for third-party agents that produces auditable, structured logs and exposes those logs back to the agent as read-only evidence.
- Scope: auditable local side effects and interactions; not a full reconstruction of model
reasoning.
- Signals to capture: 
    - process exec events (cmdline, uid/gid, PID/PPID)
    - filesystem changes including metadata (write/rename/unlink/chmod/chown/xattr/utime)
    - network egress metadata (dest/protocol/port, HTTP(S) proxy method/URL/status, and DNS lookups)
    - local IPC connection metadata (endpoint + PID)
    - stdout/stderr (plus stdin if interactive)
- Correlation: tag the root agent process with a session ID, inherit it across the PID tree, and
build a timeline by timestamp + PID to associate file/network/IPC events with the originating
process.
- Storage: logs written to a host sink outside the VM; the agent gets read-only access during the
session, with clear session boundaries.
- Explicit exclusions: file reads, env‑var mutation logging, and payload content for
network/IPC.

# Design doc
Scope and purpose

- The harness must produce auditable, structured logs of an agent's observable actions and side effects within a defined local scope (filesystem + processes + network + IPC + stdout/stderr).
- Logs must be attributable to a single session with consistent timestamps, PID/PPID lineage, and a unique session ID.
- The scope is local state and interaction auditability, not full behavioral reconstruction or model reasoning.

Threat model and trust boundary

- Tamper resistance within VM scope means the agent user/container cannot modify or delete logs; the host is trusted.
- Logs are stored on the host outside the VM; the agent sees a read-only view during the session.
- Out of scope: host compromise and VM root.

Process execution (exec)

- Record every process start in the agent’s process tree with command line, executable path, uid/gid, parent PID, and timestamp.
- Capture arguments where possible; note that some audit sources truncate or omit args, and this must be logged as a
limitation.
- Exec logging is used for attribution (what started) and correlation, not as proof of state change.

Filesystem changes (no reads)

- Record all file creation, writes, truncations, renames, deletes within the scoped workspace.
- Record all metadata changes: chmod/chown, xattr changes, utimes/mtime/atime adjustments, symlink creation, and
permission/ownership transitions.
- Reads are explicitly out of scope due to verbosity; no read syscalls are logged.

Network egress

- Log outbound connections with destination IP/port, protocol, and timestamp; record DNS lookups if available.
- Use an HTTP(S) proxy to log method + URL + status for HTTP traffic; payloads and response bodies are not required.
- For HTTPS without MITM, the proxy logs host/port only and cannot see URL or status; raw connect metadata still
provides coverage for non-HTTP protocols.
- Network logging is for remote side effects/requests, not for full content capture.

Local IPC/service interactions

- Log local IPC connection attempts with endpoint identity and process attribution; this is metadata only, not
payloads.
- Explicitly target common Linux IPC mechanisms: Unix domain sockets, D-Bus connections.
- IPC logging records who connected to what, not what was said.

Stdout/stderr (and stdin when applicable)

- The harness launches the agent and owns its stdio file descriptors.
- For non-interactive sessions, capture stdout/stderr via pipes and log exact output bytes.
- For interactive sessions, allocate a PTY; capture stdout/stderr and user input (stdin) for full conversational logs.
- Stdout/stderr are logged because they often contain results without any file writes.

Audit mechanism (hybrid)

- Use auditd (kernel audit subsystem) for exec + filesystem writes/renames/unlinks + metadata changes (chmod/chown/xattr/utime).
- Use eBPF for network egress and local IPC connection metadata with PID attribution; capture DNS lookups when available.
- Use HTTP(S) proxy for method/URL/status; for HTTPS without MITM, host/port only.
- Emit separate audit and eBPF event streams and merge by timestamp + PID/PPID + session ID.

Collection mechanics

- Use kernel‑level audit sources to observe exec + file change + IPC/network events; user‑space file watchers are
insufficient for attribution.
- Correlate events by PID/PPID and session ID; map to agent‑visible actions in a single timeline.
- Store logs in a host sink outside the VM where the agent cannot modify or delete them (read-only to agent).

Log schema contract (TODO)

- Define schema_version, required fields, and event types for all log entries.

Log ordering/merge rules (TODO)

- Define deterministic ordering (per-writer sequence numbers, timestamps, and tie-breakers).

Explicit non‑goals / exclusions

- No logging of file reads or content of IPC/network payloads by default.
- No capture of environment variable mutations inside a running process (unless explicitly added later as session
metadata).
- No guarantees about detecting actions that neither create processes nor touch files, networks, or IPC (pure
in‑memory computation).

# Roles

- Harness: runs the agent, captures stdio, assigns session ID, emits session‑level logs.
- Collector: observes OS‑level events (exec, file changes, network, IPC); requires privileged access to VM kernel audit sources.
- Proxy: logs method/URL/status for HTTP; for HTTPS without MITM, host/port only.
- Sink: where logs are stored (host directory outside the VM).
