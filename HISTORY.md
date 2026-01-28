# Agent Harness History

This document reconstructs how agent_harness came to be and why key design decisions were made, focusing on context that is not fully captured in the current docs. It is written as a linear narrative with phases and dates so a new reader can understand the intent behind the current structure.

**Phase 0: Foundations and audit mindset (Jan 2-3, 2026)**
The project starts with a broader "NoBloat" philosophy: keep the system interpretable, make every session loggable, and keep knowledge and raw transcripts separate from work. That emphasis on traceability and clean, agent-readable artifacts became the backdrop for why agent_harness had to produce evidence-grade logs rather than rely on agent self-reporting.

**Phase 1: Docker Desktop and the VM boundary (Jan 9, 2026)**
While setting up Docker Desktop, it became clear that on macOS all containers run inside a Linux VM (LinuxKit). The audit boundary is the VM kernel, not the host OS. This clarified that any reliable process-level attribution had to happen inside the VM, because host-level tools only see the VM process, not container PIDs. That discovery shaped the entire "collector inside the VM" architecture.

**Phase 2: MCP/skills are guidance, not enforcement (Jan 10, 2026)**
Early exploration focused on using MCPs and skills to force logging. The key realization was that MCPs and skills are advisory: if an agent has any direct execution path, it can bypass a "log-everything" MCP. Removing exec tools would require rewriting each agent, which was explicitly rejected. This pushed the design toward out-of-process observation rather than in-process tool enforcement.

**Phase 3: Observer model and the first logging scope (Jan 11, 2026)**
The project pivoted to an observer model: launch the agent normally, but record its side effects at the OS level. Two distinctions mattered:
- Exec events do not equal file changes; a process can start and do nothing, or write files without further exec.
- File watchers alone are insufficient because they lack PID attribution.
This drove the need for kernel-level audit sources and for correlating events via PID/PPID and a session ID. Reads were explicitly excluded due to noise and volume, while filesystem metadata changes (chmod/chown/xattr/utime) were kept in scope.

**Phase 4: Full scope definition and component roles (Jan 18, 2026)**
The scope expanded beyond exec + file changes after identifying blind spots:
- Network calls can change remote state without touching local files.
- IPC/service calls (e.g., keychain, D-Bus) can occur without exec or file writes.
- Stdout/stderr is often the only evidence of agent output.
This phase defined the four logical roles:
- Harness: runs the agent, assigns session IDs, captures stdio/PTY, emits session logs.
- Collector: observes kernel events (exec, file changes, network, IPC) with PID attribution.
- Proxy: logs HTTP(S) method/URL/status when possible.
- Sink: protected log storage, readable by the agent but not writable.
Interactive sessions required a PTY proxy to preserve TUI behavior while still capturing output.

**Phase 5: Platform and audit stack commitments (Jan 18-19, 2026)**
The platform scope narrowed to Linux in a VM (Docker Desktop for macOS), with Ubuntu 22.04 LTS as the default container base. The audit stack became a hybrid:
- auditd for exec + filesystem changes (including metadata).
- eBPF for network egress and IPC connection metadata with PID attribution.
- HTTP(S) proxy for method/URL/status (HTTPS without MITM yields host/port only).
DNS visibility was treated as part of network capture. This choice balanced auditd stability with eBPF flexibility for network/IPC.

**Phase 6: Trust boundaries and log placement (Jan 19, 2026)**
The term "verifiable" was tightened to "auditable and tamper-resistant within VM scope." The host was designated trusted, while the agent container was explicitly untrusted. Logs were moved to a host sink, with a read-only mount into the agent so it can inspect evidence during the session. This requirement made it impractical to keep harness and agent in the same container because a single mount cannot be both rw and ro for different processes.

**Phase 7: SSH vs Docker socket for harness control (Jan 21, 2026)**
When deciding how the harness should control the agent (especially for TUI sessions), three options were evaluated: Docker socket, SSH PTY, and WebTTY. Docker socket access was judged too privileged for an attach/control path because it effectively grants root on the Docker daemon host (the LinuxKit VM). The design instead favored SSH-based control: the agent image runs sshd, and the harness connects over SSH with a PTY. That preserves the trust boundary while still enabling full TUI interaction and stdio capture. The Docker socket remained a packaging tradeoff only if the harness must create containers; otherwise the agent can be predeclared in Compose to avoid handing the harness runtime control.

**Phase 8: Collector implementation and the Tracee detour (Jan 19-21, 2026)**
The collector work started with Tracee (Aqua's eBPF tool) to validate feasibility quickly, but it introduced complexity and errors. The project reverted to a smaller, purpose-built pipeline:
- auditd rules were added and auditd.conf was fixed to write to `/logs/audit.log`.
- A custom eBPF loader was built (Rust + aya) with a kernel program in C.
- The collector image became multi-stage to compile eBPF artifacts cleanly.
- Test scripts were added to generate activity and verify both audit and eBPF logs.
Subsequent iterations expanded coverage: sendmsg/recvmsg, TCP DNS parsing, /proc socket enrichment for src endpoints, and unix socket type resolution.

**Phase 9: Harness and agent container scaffolding (late Jan 2026)**
The agent container became a real target workload: it installs Codex CLI and exposes SSH for the harness to attach. The harness container provides a control plane for non-interactive jobs and a PTY proxy for interactive sessions, writing its own stdio logs into the host sink. Integration scripts were added to run stub and Codex tests, and a Compose override was created to mount host Codex credentials when needed. This phase shifted the project from a collector-only testbed to an end-to-end harness.

**Phase 10: Audit log filtering and human-readable output (late Jan 2026)**
Once auditd logs were flowing, the focus shifted to making them reviewable by humans. A dedicated filter stage was introduced to collapse multi-record audit events into a concise JSONL stream of exec and filesystem events, with attribution to sessions and jobs. This included:
- A configurable filter script that groups audit sequences, applies agent-ownership rules, and emits normalized JSONL.
- A formal schema and filtering rules documented in `collector/auditd_data.md` and `collector/config/filtering_rules.md`.
- Wiring the filter into the collector container so it can run alongside auditd and eBPF in live-tail mode or batch mode.
- Unit tests and integration scripts covering no-harness, job, and TUI runs to validate expected exec/fs output and correct session/job mapping.

**Open questions and deliberate TODOs**
Some choices were intentionally deferred and still appear as TODOs in the docs:
- Stable log schema contract and deterministic merge/ordering rules.
- Kernel feature requirements and minimum versions for audit sources.
- Proxy enforcement rules (to prevent bypass).
- Log rotation/retention policy for auditd and eBPF outputs.

This history explains why the current repo looks the way it does: it is not just "containers + logging," but a layered response to the core constraint of auditing third-party agents without rewriting them or relying on their cooperation.
