


# Prompt 

I want to wrap third-party agents to produce consistent, verifiable logs within an explicit scope. This will include:
  - Process tree: exec events with args/uid/gid when available (note: args can be truncated by some auditors).
  - Filesystem changes: writes/renames/unlinks plus metadata changes (chmod/chown/xattr/utime); reads excluded for noise.
  - Network egress: destination/protocol/port; optional HTTP proxy for method/URL.
  - Local IPC/service: connections to local daemons (e.g. Unix sockets/XPC/Mach/D‑Bus endpoints).
  - Stdout/stderr: captured by the supervisor (pipes for non‑interactive, PTY for interactive).

Additionally, the agent may then be able to leverage this logging itself.

# Summary

- Goal: build a wrapper/harness for third‑party agents that produces consistent, verifiable logs
and can optionally expose those logs back to the agent as read‑only evidence.
- Scope: verifiable local side effects and interactions; not a full reconstruction of model
reasoning.
- Signals to capture: process exec events (cmdline, uid/gid, PID/PPID), filesystem changes
including metadata (write/rename/unlink/chmod/chown/xattr/utime), network egress metadata (dest/
protocol/port), local IPC connection metadata (endpoint + PID), and stdout/stderr (plus stdin if
interactive).
- Correlation: tag the root agent process with a session ID, inherit it across the PID tree, and
build a timeline by timestamp + PID to associate file/network/IPC events with the originating
process.
- Storage: logs written to a protected sink the agent cannot modify (read‑only to agent), with
clear session boundaries.
- Explicit exclusions (for now): file reads, env‑var mutation logging, and payload content for
network/IPC.

# Design doc
Scope and purpose

- The wrapper must produce verifiable, structured logs of an agent’s observable actions and side effects within a
defined local scope (filesystem + processes + network + IPC + stdout/stderr).
- Logs must be attributable to a single session with consistent timestamps, PID/PPID lineage, and a unique session
ID.
- The scope is “local state and interaction verifiability,” not full behavioral reconstruction or model reasoning.

Process execution (exec)

- Record every process start in the agent’s process tree with command line, executable path, uid/gid, parent PID, and
timestamp.
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
- Optionally use an HTTP(S) proxy to log method + URL + status; payloads and response bodies are not required.
- Network logging is for “remote side effects/requests,” not for full content capture.

Local IPC/service interactions

- Log local IPC connection attempts with endpoint identity and process attribution; this is metadata only, not
payloads.
- Explicitly target common OS IPC mechanisms:
    - Linux: Unix domain sockets, D‑Bus connections.
    - macOS: XPC/Mach service connections.
    - Windows: named pipes / RPC / ALPC.
- IPC logging records “who connected to what,” not “what was said.”

Stdout/stderr (and stdin when applicable)

- The supervisor/wrapper launches the agent and owns its stdio file descriptors.
- For non‑interactive sessions, capture stdout/stderr via pipes and log exact output bytes.
- For interactive sessions, allocate a PTY; capture stdout/stderr and user input (stdin) for full conversational
logs.
- Stdout/stderr are logged because they often contain results without any file writes.

Collection mechanics

- Use kernel‑level audit sources to observe exec + file change + IPC/network events; user‑space file watchers are
insufficient for attribution.
- Correlate events by PID/PPID and session ID; map to agent‑visible actions in a single timeline.
- Store logs in a protected sink where the agent cannot modify or delete them (read‑only to agent).

Explicit non‑goals / exclusions

- No logging of file reads or content of IPC/network payloads by default.
- No capture of environment variable mutations inside a running process (unless explicitly added later as session
metadata).
- No guarantees about detecting actions that neither create processes nor touch files, networks, or IPC (pure
in‑memory computation).

# Roles

  - Harness: runs the agent, captures stdio, assigns session ID, emits session‑level logs.
  - Collector: observes OS‑level events (exec, file changes, network, IPC).
  - Sink: where logs are stored (protected VM volume, host directory, or remote append‑only store).
