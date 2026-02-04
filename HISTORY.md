# Lasso History (formerly agent_harness)

This document reconstructs how Lasso (formerly agent_harness) came to be and why key design decisions were made, focusing on context that is not fully captured in the current docs. It is written as a linear narrative with phases and dates so a new reader can understand the intent behind the current structure.

**Phase 0: Foundations and audit mindset (Jan 2-3, 2026)**
The project starts with a broader "NoBloat" philosophy: keep the system interpretable, make every session loggable, and keep knowledge and raw transcripts separate from work. That emphasis on traceability and clean, agent-readable artifacts became the backdrop for why the project (then called agent_harness) had to produce evidence-grade logs rather than rely on agent self-reporting.

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

**Phase 11: eBPF filtering follows exec lineage (Jan 28, 2026)**
Once the eBPF filter was in place, it became clear that long-running sessions would miss new processes unless ownership was continuously updated. The filter was extended to tail raw audit exec events in `--follow` mode so the PID tree stays current without depending on the audit filter output format. An optional, bounded pending buffer was added to capture early eBPF events that arrive before ownership is learned.

**Phase 12: Follow-mode hardening and test coverage (Jan 28, 2026)**
The first follow-mode implementation exposed gaps around audit tailing and rotation. Follow mode was hardened with an inode/offset cursor so it resumes cleanly after the initial scan, and rotated audit logs are re-read from the start. The pending buffer was enabled by default, and a follow-mode test suite was added to lock in tailing, rotation, and buffer replay behavior.

**Phase 13: Unified timeline + eBPF summary layer (Jan 30, 2026)**
Raw eBPF streams were still too noisy for human review, and the UI needed a single source of truth. A new summary stage (`collector-ebpf-summary`) collapses network activity into burst-level `net_summary` rows (send bursts split by idle gaps) and enriches them with DNS names, connect counts, byte totals, and burst timing. The summary gained a DNS look-back window and suppression thresholds to drop trivial bursts. In parallel, a merge stage now normalizes filtered audit + summarized eBPF into `logs/filtered_timeline.jsonl`, pushing source-specific fields under `details` and sorting deterministically (ts/source/pid). The collector entrypoint now runs both summary + merge loops on a short interval to keep the unified timeline up to date.

**Phase 14: End-to-end example flow and stable fixtures (Jan 28-30, 2026)**
To make the pipeline verifiable by new contributors, a comprehensive `EXAMPLE_FLOW.md` was added with step-by-step TUI and server-mode scenarios, expected commands, log row counts, and example UI outputs. Stable example logs and YAML fixtures were checked into `example_logs/` so tests and docs stay grounded in real output.

**Phase 15: Log viewer UI arrives (Jan 28-31, 2026)**
A lightweight UI + API contract was introduced to read the unified timeline and run metadata directly from `/logs`, with endpoints for sessions, jobs, timeline rows, and summary counts. The early zero-build prototype validated the data model (session/job selection, time-range filters, and summary tiles), and `compose.ui.yml` made the UI a first-class service.

**Phase 16: Figma-driven redesign and build pipeline (Feb 1, 2026)**
The UI was rebuilt from a Figma export into a React + Vite app with reusable components, preserving the read-only, filter-first behavior while improving layout and visual clarity. The `ui` container now builds the frontend and serves it via the Python API server, and `UI_DESIGN.md` was updated to describe the new structure (summary metrics, filter controls, timeline, and runs list).

**Phase 17: Lasso rebrand + CLI-first packaging (Feb 2-4, 2026)**
The project shifted from “agent_harness” as an internal code name to **Lasso** as the product name. A Rust CLI (`lasso`) became the primary entry point, standardizing config, compose wiring, and lifecycle commands. Key packaging choices were made:
- **Thin release bundles**: ship only the CLI binary + compose files; the container images live in GHCR and are referenced by tag.
- **Stable config location**: `~/.config/lasso/config.yaml` with default paths `~/lasso-logs` and `~/lasso-workspace`.
- **Parameterized compose**: `LASSO_VERSION`, `LASSO_LOG_ROOT`, and `LASSO_WORKSPACE_ROOT` drive consistent mounts across services.
- **Installer flow**: a release-installed CLI (`install_lasso.sh`) places versions under `~/.lasso/` and symlinks into `~/.local/bin`.
- **Release automation**: a GitHub Actions workflow builds bundles, optionally pushes images, and optionally publishes releases.
This phase also introduced a dedicated CLI test suite (`scripts/cli_scripts`) and updated docs (`INSTALL.md`, `CLI.md`, `lasso/README.md`) to reflect the CLI-first workflow.

**Open questions and deliberate TODOs**
Some choices were intentionally deferred and still appear as TODOs in the docs:
- Kernel feature requirements and minimum versions for audit sources.
- Proxy enforcement rules (to prevent bypass).
- Log rotation/retention policy for auditd and eBPF outputs.

This history explains why the current repo looks the way it does: it is not just "containers + logging," but a layered response to the core constraint of auditing third-party agents without rewriting them or relying on their cooperation.
