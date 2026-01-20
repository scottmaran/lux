# Overview
The collector container to audit the VM OS that the agent and harness containers live in.

# Implementation

## dockerfile
Uses Ubuntu 22.04 LTS to stay aligned with the platform default and keep auditd behavior
predictable across environments. Installs `auditd` plus `audispd-plugins` for future
forwarding options, and `util-linux` for mount utilities. No eBPF tooling is included yet.

## entrypoint.sh
Bootstraps auditd and loads rules without forcing the container to exit on non‑fatal
rule errors. It also ensures the log file exists and is writable by the audit group, then
starts auditd in daemon mode and tails the log so the container stays alive. The log path
is injected via `COLLECTOR_AUDIT_LOG` so the host mount can control where audit output lands.

## auditd.conf
Configured to keep audit output local and file‑backed: `local_events = yes`, RAW log
format, and an explicit `log_file` under `/logs`. Rotation is enabled with small log
chunks for local testing, and disk‑pressure actions are conservative (SUSPEND) to avoid
silent loss. The log group is `adm` (Ubuntu standard).

## harness.rules
Keeps scope narrow and attribution‑focused. It logs exec events for process lineage and
audits only writes/renames/unlinks plus metadata changes inside `/work` (no reads). The
rules use a mix of path watches and syscall filters for coverage, and avoid syscalls that
don’t exist on aarch64 kernels. This is a starter set intended to be refined for noise
reduction and tighter scoping later.

# Testing
Step‑by‑step test

1. Build the collector image:

docker build -t harness-collector:dev ./collector

2. Ensure workspace + logs exist:

mkdir -p ~/agent_harness/workspace ~/agent_harness/logs

3. Start the collector (auditd only; eBPF loader TBD):

docker run -d --name harness-collector \
--pid=host --cgroupns=host --privileged \
-e COLLECTOR_AUDIT_LOG=/logs/audit.log \
-v ~/agent_harness/logs:/logs:rw \
-v ~/agent_harness/workspace:/work:ro \
-v /sys/fs/bpf:/sys/fs/bpf:rw \
-v /sys/kernel/tracing:/sys/kernel/tracing:rw \
-v /sys/kernel/debug:/sys/kernel/debug:rw \
harness-collector:dev

The /sys mounts are reserved for the custom eBPF loader; auditd works without them.

4. Generate filesystem activity (auditd):

docker run --rm -v ~/agent_harness/workspace:/work alpine sh -c \ "echo hi > /work/a.txt; mv /work/a.txt /work/b.txt; chmod 600 /work/b.txt; rm /work/b.txt"

5. Stop the collector:

docker stop harness-collector

6. Inspect logs:

tail -n 20 ~/agent_harness/logs/audit.log
