# Overview

A running log of implementation work on agent_harness

# Blocks of Work

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

# To Do:
- DNS parsing now covers UDP/TCP port 53 via sendto/recvfrom/sendmsg/recvmsg and detects TCP by length prefix, but DoH/DoT traffic is
still opaque.
- src_ip/src_port are now best-effort from `/proc/<pid>/net/*`, but short-lived or in-progress sockets can still show 0.0.0.0/:: and 0.
- unix sock_type is resolved from `/proc/<pid>/net/unix`, but can still be "unknown" if the socket disappears before lookup.
