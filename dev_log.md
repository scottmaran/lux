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

# To Do:
- DNS parsing is UDP-only via sendto/recvfrom: we only hook sys_enter/exit_sendto + sys_enter/exit_recvfrom and only emit DNS when port
53 is seen there. That captures UDP DNS and misses TCP DNS (port 53 over connect/send/recv), plus sendmsg/recvmsg paths some libs
use. DoH/DoT isn’t captured at all.
- src_ip/src_port are zeroed: the eBPF program never looks up the socket’s local endpoint, so the loader only has the destination
address. That’s why src_ip shows 0.0.0.0/:: and src_port is 0 in net_* events.
- unix socket sock_type fixed to stream: we don’t read the real socket type from the kernel, so the loader hardcodes "stream". If a
process uses datagram/seqpacket unix sockets, we’ll mislabel them until we fetch the true type.