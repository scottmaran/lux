# Overview
The collector container to audit the VM OS that the agent and harness containers live in.

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
