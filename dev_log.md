# Overview

A running log of implementation work on agent_harness

# Collector

Blocks of Work

## Block 1:
- Implemented Rust/aya eBPF program + loader (tracepoints for connect/sendto/recvfrom) emitting JSONL events via ring buffer.
- Updated collector image build to compile and ship the eBPF artifacts, with entrypoint running auditd plus the loader.
- Added test automation in `collector/scripts/run_test.sh` and activity generation in `collector/scripts/ebpf_activity.sh` to validate logs.
- Aligned log output to `/logs` and kept schema/testing docs current in `collector/README.md` and `collector/eBPF_data.md`.

### Details 

- Reworked eBPF event emission to avoid stack overflows and updated tracepoint/helper usage for aya 0.12 in collector/ebpf/ebpf/src/
lib.rs.
- Switched aya dependencies to git tag aya-v0.12.0 in collector/ebpf/ebpf/Cargo.toml and collector/ebpf/loader/Cargo.toml, and removed
the unsupported linker flag in collector/ebpf/.cargo/config.toml.
- Fixed loader compatibility (manual Pod/Zeroable, RingBuf::try_from, map/program lookup context) in collector/ebpf/loader/src/main.rs.
- Copied the correct eBPF artifact into the image in collector/Dockerfile.
- Adjusted the unix-socket activity test to use /tmp inside the container in collector/scripts/ebpf_activity.sh.

## Block 2:
- Expanded eBPF coverage to include sendmsg/recvmsg and TCP DNS paths, plus socket FD tracking for richer context.
- Added userspace socket enrichment from `/proc/<pid>/net/*` to populate src/dst endpoints and unix socket types when available.
- Updated schema notes to reflect the new network/DNS handling and remaining gaps.

### Details 
- Extended the eBPF event payload with `fd` and added maps for sendmsg/recvmsg + connected sockets; introduced tracepoints and parsing of
msghdr/iovec in `collector/ebpf/ebpf/src/lib.rs`.
- Added connected-socket fallback for sendto/recvfrom when no sockaddr is passed, enabling DNS extraction for connected UDP/TCP flows in
`collector/ebpf/ebpf/src/lib.rs`.
- Loader now resolves inet socket endpoints by scanning `/proc/<pid>/net/{tcp,udp,tcp6,udp6}` and unix socket types via
`/proc/<pid>/net/unix`, feeding those fields into net/unix event JSON in `collector/ebpf/loader/src/main.rs`.
- DNS parsing now detects TCP length-prefixed payloads and uses socket info for transport/server fields; zero-address handling was added to
trigger `/proc` fallback in `collector/ebpf/loader/src/main.rs`.
- Updated documentation notes in `collector/eBPF_data.md` and refreshed the To Do section in `dev_log.md` to reflect current behavior.

## Block 3:
- Implemented an auditd filtering pipeline that emits compact JSONL exec/fs events with session/job attribution.
- Added filtering configuration + schema docs, plus unit and integration tests for the filter.

### Details
- Added `collector/scripts/filter_audit_logs.py` to parse auditd sequences, apply ownership rules, and emit filtered JSONL, including optional
session/job mapping and live-tail buffering.
- Wired the filter into the collector image and entrypoint; added `python3-yaml` dependency and config at `collector/config/filtering.yaml`.
- Documented filtered output schema and rules in `collector/auditd_data.md` and `collector/config/filtering_rules.md`, and added `TESTING.md`.
- Created audit-filter integration scripts for no-harness, job, and TUI flows under `scripts/`.

## Block 4:
- Extended the eBPF filter to follow audit exec events in real time so PID ownership stays accurate in long-running sessions.
- Added an optional pending buffer to recover eBPF events that arrive before ownership is established.

### Details
- The eBPF filter now tails raw `audit.log` in `--follow` mode and updates its PID tree on new execs, while still tailing `ebpf.jsonl`.
- Added a bounded pending buffer (TTL + size limits) to hold early eBPF events until ownership is learned; disabled by default.
- Documented pending buffer settings in `collector/config/ebpf_filtering.yaml`.

## Block 5:
- Fixed follow-mode race conditions and gaps in the eBPF filter’s audit tailing path.
- Added follow-mode tests for audit tailing, pending buffering, and log rotation behavior.

### Details
- Added an audit cursor (inode + offset) so follow mode resumes after the initial ownership scan without missing execs.
- On log rotation, the audit tail now reads from the start of the new file instead of skipping early lines.
- Fixed the pending-buffer race by re-checking ownership under consistent lock ordering before enqueueing.
- Enabled the pending buffer by default and covered follow-mode behaviors with unit tests.

## Block 6:
- Added an eBPF summary stage and a merge step to produce a unified, UI-friendly timeline.
- Wired the new stages into the collector entrypoint to keep summary + merged outputs refreshed.

### Details
- Created `collector/scripts/summarize_ebpf_logs.py` to emit `net_summary` rows from filtered eBPF logs.
- Added `collector/scripts/merge_filtered_logs.py` plus configs in `collector/config/ebpf_summary.yaml` and
  `collector/config/merge_filtering.yaml`.
- Updated `collector/timeline_data.md` to describe `timeline.filtered.v1` and the normalized `details` payload.
- Updated `collector/entrypoint.sh` to run summary + merge loops on an interval.

## Block 7:
- Reworked network summaries around send-burst aggregation and enriched them with DNS look-back.
- Added suppression thresholds to drop tiny bursts and refreshed fixtures/tests to match the new semantics.

### Details
- Replaced the summary logic to split bursts by idle gaps, track `connect_count`, and emit `ts_first/ts_last`.
- Added `dns_lookback_sec`, `min_send_count`, and `min_bytes_sent_total` handling in the summary config.
- Updated `collector/tests/test_ebpf_summary.py`, `collector/timeline_data.md`, and example/fixture logs under `example_logs/`.

# Agent 

## Block 1: 
Added an agent container skeleton with SSH-only access and Codex CLI via npm.

### Details
- Created the agent container files (`agent/Dockerfile`, `agent/sshd_config`, `agent/entrypoint.sh`, `agent/README.md`) with a locked-down SSH config, `agent` user (uid 1001), `/work` workspace, `/logs` read-only contract, and Codex CLI installed via `npm install -g @openai/codex`.

# UI

Blocks of Work

## Block 1:
- Added a zero-build log viewer UI and a tiny API server to read timeline, sessions, and jobs from `/logs`.
- Documented the UI contract and added a compose service for running the UI.

### Details
- Introduced `ui/server.py`, `ui/index.html`, `ui/app.js`, and `ui/styles.css` for a static UI served with an
  embedded JSON API.
- Added `UI_API.md`, `UI_DESIGN.md`, and `compose.ui.yml` to document and run the UI service.

## Block 2:
- Iterated on the zero-build UI with clearer naming and better formatting.

### Details
- Simplified labels and layout in `ui/app.js`, `ui/index.html`, and `ui/styles.css`.
- Formatted process metadata and surfaced domains ahead of IPs for network rows.
- Updated `UI_DESIGN.md`/`UI_API.md` to align with the filtered timeline pipeline.

## Block 3:
- Rebuilt the UI from the Figma export as a React + Vite app with reusable components.
- Updated the UI container to build and serve the compiled frontend.

### Details
- Added `ui/src` with `App.tsx`, timeline/runs/filters/metrics components, and a shared UI component library.
- Added `ui/package.json`, `ui/vite.config.ts`, `ui/src/index.css`, and `ui/src/styles/globals.css`.
- Updated `ui/Dockerfile` and `ui/README.md` to build the Vite app and serve it through the Python API server.
- Updated `UI_DESIGN.md` to describe the new layout and behavior.

# To Do:
- DNS parsing now covers UDP/TCP port 53 via sendto/recvfrom/sendmsg/recvmsg and detects TCP by length prefix, but DoH/DoT traffic is
still opaque.
- src_ip/src_port are now best-effort from `/proc/<pid>/net/*`, but short-lived or in-progress sockets can still show 0.0.0.0/:: and 0.
- unix sock_type is resolved from `/proc/<pid>/net/unix`, but can still be "unknown" if the socket disappears before lookup.
- decide if we want host port mapping for agent container

# Integration Tests

## Block 1: 
- Added agent-agnostic integration testing with a configurable run command and a Codex-specific compose override.
- Added stub + Codex integration scripts that spin up the stack, run `/run` jobs, verify logs, and tear down.

### Details
- Added `HARNESS_RUN_CMD_TEMPLATE` to control the non-interactive command in `harness/harness.py` and wired it through `compose.yml`.
- Introduced `compose.codex.yml` for mounting host Codex auth/skills without polluting the base compose file.
- Created `scripts/run_integration_stub.sh` and `scripts/run_integration_codex.sh` to drive the `/run` API, poll status, and validate
host-side logs.
- Documented integration flows and the manual TUI check in the new root `README.md`.
- Unlocked the agent account for SSH auth in `agent/Dockerfile` (`passwd -d agent`) so harness logins succeed.

## Block 2:
- Added audit-filter integration coverage for no-harness, job, and TUI paths.

### Details
- New scripts: `scripts/run_integration_filter_no_harness.sh`, `scripts/run_integration_filter_job.sh`,
  `scripts/run_integration_filter_tui.sh`.
- Tests validate expected exec/fs rows and session/job attribution in the filtered JSONL output.

## Block 3:
- Added an end-to-end example flow doc and stable fixtures for validating the merged timeline output.

### Details
- Created `EXAMPLE_FLOW.md` with TUI + server-mode scenarios, expected commands, and UI outputs.
- Added `example_logs/` fixtures and YAML configs for summary + merge filtering examples.
