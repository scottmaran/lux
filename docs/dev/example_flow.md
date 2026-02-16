# Example Flow: Lasso (Agent Harness)

## Overview summary
This document is a fully self-contained, procedural example of what the Lasso stack should do end to end. It shows two distinct scenarios (TUI and server-mode job), the user prompts, the underlying commands, the expected workspace changes, the log rows across all log files, and the final UI output derived from filtered logs. All timestamps are UTC.

Run-layout note (Feb 2026): all collector/harness artifacts are run-scoped
under `<log_root>/<run_id>/...` where `<run_id>` is typically
`lasso__YYYY_MM_DD_HH_MM_SS`.

## Setup and entry commands
1) Prepare a clean run-scoped environment.
```bash
set -a
source ~/.config/lasso/compose.env
set +a

export LASSO_VERSION=local
export LASSO_RUN_ID="lasso__$(date +%Y_%m_%d_%H_%M_%S)"

mkdir -p "$LASSO_LOG_ROOT/$LASSO_RUN_ID"
printf '{\n  "run_id": "%s",\n  "started_at": "%s"\n}\n' \
  "$LASSO_RUN_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$LASSO_LOG_ROOT/.active_run.json"
```

2) Start collector + agent for TUI (Scenario A).
```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f tests/integration/compose.provider.codex.override.yml \
  up -d --pull never collector agent
```

3) Launch the harness TUI (Scenario A).
```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f tests/integration/compose.provider.codex.override.yml \
  run --rm \
  -e HARNESS_MODE=tui \
  harness
```

4) Start the stack for server mode (Scenario B).
```bash
export HARNESS_API_TOKEN=dev-token
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f tests/integration/compose.provider.codex.override.yml \
  up -d --pull never harness
```

5) Trigger a server-mode job (Scenario B).
```bash
curl -s -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Confirm the current working directory, then create /work/personal_files/notes.txt"}' \
  http://127.0.0.1:8081/run
```

6) Merge filtered audit + eBPF logs into the unified timeline (both scenarios).
```bash
cat > "$LASSO_LOG_ROOT/merge_filtering_example.yaml" <<YAML
schema_version: timeline.filtered.v1
inputs:
  - path: /logs/${LASSO_RUN_ID}/collector/filtered/filtered_audit.jsonl
    source: audit
  - path: /logs/${LASSO_RUN_ID}/collector/filtered/filtered_ebpf.jsonl
    source: ebpf
output:
  jsonl: /logs/${LASSO_RUN_ID}/collector/filtered/filtered_timeline.jsonl
sorting:
  strategy: ts_source_pid
YAML

docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f tests/integration/compose.provider.codex.override.yml \
  exec -T collector \
  collector-merge-filtered --config /logs/merge_filtering_example.yaml
```
Note: the current collector entrypoint also writes `filtered_ebpf_summary.jsonl`
and the default merge config uses that summary file for UI-friendly `net_summary`
rows. This example keeps raw `filtered_ebpf.jsonl` to keep the snippets small.

7) (Optional) Tear down between scenarios.
```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f tests/integration/compose.provider.codex.override.yml \
  down --remove-orphans
```

## Example input and expected output (two scenarios)
### Example input
```
...The user will then have the TUI of their given agent (default) codex and they are free to use it however they see fit or normally use it. For our example, the user will ask codex to confirm the current working directory. Then it will ask codex to create a new notes.txt file in a new directory personal_files.
```

### Scenario A: TUI session
User prompts (TUI):
1) "Confirm the current working directory."
2) "Create a new notes.txt file in a new directory personal_files."

Expected underlying commands (agent actions):
1) `pwd`
2) `mkdir -p /work/personal_files`
3) `touch /work/personal_files/notes.txt`

Expected workspace result:
- Directory exists: `/work/personal_files`
- File exists: `/work/personal_files/notes.txt`

### Scenario B: Server-mode job
User prompt (server job):
1) "Confirm the current working directory, then create /work/personal_files/notes.txt"

Expected underlying commands (agent actions):
1) `pwd`
2) `mkdir -p /work/personal_files`
3) `touch /work/personal_files/notes.txt`

Expected workspace result:
- Directory exists: `/work/personal_files`
- File exists: `/work/personal_files/notes.txt`

## Containers in this stack
- harness: control plane for TUI sessions and server jobs, writes session/job metadata and IO logs.
- agent: runs Codex CLI and executes the underlying commands.
- collector: captures raw auditd + eBPF logs and emits filtered JSONL + merged timeline.

## Harness container logs
### Scenario A (TUI)
Log row counts:
- `<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/meta.json`: 1 JSON object
- `<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/stdin.log`: 2 lines
- `<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/stdout.log`: 2 lines

Example snippets:
`<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/meta.json`
```json
{
  "command": "codex -C /work -s danger-full-access",
  "ended_at": "2026-01-28T20:00:05.000Z",
  "exit_code": 0,
  "mode": "tui",
  "session_id": "session_20260128_200000_ab12",
  "started_at": "2026-01-28T20:00:00.100Z",
  "stdin_path": "<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/stdin.log",
  "stdout_path": "<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/stdout.log"
}
```

`<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/stdin.log`
```
Confirm the current working directory.
Create a new notes.txt file in a new directory personal_files.
```

`<log_root>/<run_id>/harness/sessions/session_20260128_200000_ab12/stdout.log`
```
/work
Created /work/personal_files/notes.txt
```

### Scenario B (server mode)
Log row counts:
- `<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/input.json`: 1 JSON object
- `<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/stdout.log`: 2 lines
- `<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/stderr.log`: 0 lines
- `<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/status.json`: 1 JSON object

Example snippets:
`<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/input.json`
```json
{
  "job_id": "job_20260128_200500_cd34",
  "submitted_at": "2026-01-28T20:05:00.500Z",
  "started_at": "2026-01-28T20:05:00.520Z",
  "prompt": "Confirm the current working directory, then create /work/personal_files/notes.txt",
  "cwd": "/work",
  "env": {},
  "command": "codex -C /work -s danger-full-access exec {prompt}"
}
```

`<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/stdout.log`
```
/work
Created /work/personal_files/notes.txt
```

`<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/stderr.log`
```
```

`<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/status.json`
```json
{
  "ended_at": "2026-01-28T20:05:02.050Z",
  "error": null,
  "error_path": "<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/stderr.log",
  "exit_code": 0,
  "job_id": "job_20260128_200500_cd34",
  "output_path": "<log_root>/<run_id>/harness/jobs/job_20260128_200500_cd34/stdout.log",
  "started_at": "2026-01-28T20:05:00.520Z",
  "status": "complete",
  "submitted_at": "2026-01-28T20:05:00.500Z"
}
```

## Agent container logs (agent-owned rows visible in the log sink)
Note: when the summary stage is enabled, `filtered_ebpf_summary.jsonl` provides
`net_summary` rows and is the default input to the merged timeline. The raw
`filtered_ebpf.jsonl` still exists for lower-level inspection.
### Scenario A (TUI)
Agent-owned row counts (all rows in these files are agent-owned for this scenario):
- `<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"audit_seq":2001,"audit_key":"exec","agent_owned":true}
```

`<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}
```

`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}}
```

### Scenario B (server mode)
Agent-owned row counts (all rows in these files are agent-owned for this scenario):
- `<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"audit_seq":3001,"audit_key":"exec","agent_owned":true}
```

`<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}
```

`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}}
```

## Collector container logs
### Scenario A (TUI)
Log row counts:
- `<log_root>/<run_id>/collector/raw/audit.log`: 15 lines (5 logical events, 3 lines each)
- `<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `<log_root>/<run_id>/collector/raw/ebpf.jsonl`: 1 row
- `<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`<log_root>/<run_id>/collector/raw/audit.log` (single logical event with multiple lines)
```text
type=SYSCALL msg=audit(1769630402.100:2001): arch=c00000b7 syscall=221 success=yes exit=0 ppid=5090 pid=5101 uid=1001 gid=1001 comm="bash" exe="/usr/bin/bash" key="exec"
type=EXECVE msg=audit(1769630402.100:2001): argc=3 a0="bash" a1="-lc" a2="pwd"
type=CWD msg=audit(1769630402.100:2001): cwd="/work"
```

`<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"audit_seq":2001,"audit_key":"exec","agent_owned":true}
{"schema_version":"auditd.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:03.050Z","source":"audit","event_type":"fs_create","path":"/work/personal_files","cwd":"/work","comm":"mkdir","exe":"/usr/bin/mkdir","pid":5102,"ppid":5090,"uid":1001,"gid":1001,"audit_seq":2003,"audit_key":"fs_watch","agent_owned":true,"cmd":"mkdir -p /work/personal_files"}
```

`<log_root>/<run_id>/collector/raw/ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.v1","ts":"2026-01-28T20:00:01.500000000Z","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"}}
```

`<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}
```

`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"comm":"bash","exe":"/usr/bin/bash","details":{"cmd":"pwd","cwd":"/work","audit_seq":2001,"audit_key":"exec"}}
```

### Scenario B (server mode)
Log row counts:
- `<log_root>/<run_id>/collector/raw/audit.log`: 15 lines (5 logical events, 3 lines each)
- `<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `<log_root>/<run_id>/collector/raw/ebpf.jsonl`: 1 row
- `<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`<log_root>/<run_id>/collector/raw/audit.log` (single logical event with multiple lines)
```text
type=SYSCALL msg=audit(1769630702.900:3002): arch=c00000b7 syscall=221 success=yes exit=0 ppid=6090 pid=6102 uid=1001 gid=1001 comm="mkdir" exe="/usr/bin/mkdir" key="exec"
type=EXECVE msg=audit(1769630702.900:3002): argc=4 a0="mkdir" a1="-p" a2="/work/personal_files" a3=""
type=CWD msg=audit(1769630702.900:3002): cwd="/work"
```

`<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"audit_seq":3001,"audit_key":"exec","agent_owned":true}
{"schema_version":"auditd.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.950Z","source":"audit","event_type":"fs_create","path":"/work/personal_files/notes.txt","cwd":"/work","comm":"touch","exe":"/usr/bin/touch","pid":6103,"ppid":6090,"uid":1001,"gid":1001,"audit_seq":3005,"audit_key":"fs_watch","agent_owned":true,"cmd":"touch /work/personal_files/notes.txt"}
```

`<log_root>/<run_id>/collector/raw/ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.v1","ts":"2026-01-28T20:05:01.200000000Z","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53}}
```

`<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}
```

`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"comm":"bash","exe":"/usr/bin/bash","details":{"cmd":"pwd","cwd":"/work","audit_seq":3001,"audit_key":"exec"}}
```

## Final UI output from filtered logs
### Scenario A (TUI)
`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl` (full file for this scenario)
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"comm":"bash","exe":"/usr/bin/bash","details":{"cmd":"pwd","cwd":"/work","audit_seq":2001,"audit_key":"exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:03.000Z","source":"audit","event_type":"exec","pid":5102,"ppid":5090,"uid":1001,"gid":1001,"comm":"mkdir","exe":"/usr/bin/mkdir","details":{"cmd":"mkdir -p /work/personal_files","cwd":"/work","audit_seq":2002,"audit_key":"exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:03.050Z","source":"audit","event_type":"fs_create","pid":5102,"ppid":5090,"uid":1001,"gid":1001,"comm":"mkdir","exe":"/usr/bin/mkdir","details":{"path":"/work/personal_files","cmd":"mkdir -p /work/personal_files","cwd":"/work","audit_seq":2003,"audit_key":"fs_watch"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:04.000Z","source":"audit","event_type":"exec","pid":5103,"ppid":5090,"uid":1001,"gid":1001,"comm":"touch","exe":"/usr/bin/touch","details":{"cmd":"touch /work/personal_files/notes.txt","cwd":"/work","audit_seq":2004,"audit_key":"exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:04.020Z","source":"audit","event_type":"fs_create","pid":5103,"ppid":5090,"uid":1001,"gid":1001,"comm":"touch","exe":"/usr/bin/touch","details":{"path":"/work/personal_files/notes.txt","cmd":"touch /work/personal_files/notes.txt","cwd":"/work","audit_seq":2005,"audit_key":"fs_watch"}}
```

UI-style filtered logs table mock (Scenario A)
```text
| ts (UTC)                    | source | event_type   | comm  | pid  | target                               |
| 2026-01-28T20:00:01.500Z     | ebpf   | unix_connect | codex | 5090 | /run/dbus/system_bus_socket          |
| 2026-01-28T20:00:02.100Z     | audit  | exec         | bash  | 5101 | pwd                                  |
| 2026-01-28T20:00:03.000Z     | audit  | exec         | mkdir | 5102 | mkdir -p /work/personal_files        |
| 2026-01-28T20:00:03.050Z     | audit  | fs_create    | mkdir | 5102 | /work/personal_files                 |
| 2026-01-28T20:00:04.000Z     | audit  | exec         | touch | 5103 | touch /work/personal_files/notes.txt |
| 2026-01-28T20:00:04.020Z     | audit  | fs_create    | touch | 5103 | /work/personal_files/notes.txt       |
```

### Scenario B (server mode)
`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl` (full file for this scenario)
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"comm":"bash","exe":"/usr/bin/bash","details":{"cmd":"pwd","cwd":"/work","audit_seq":3001,"audit_key":"exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.300Z","source":"audit","event_type":"exec","pid":6102,"ppid":6090,"uid":1001,"gid":1001,"comm":"mkdir","exe":"/usr/bin/mkdir","details":{"cmd":"mkdir -p /work/personal_files","cwd":"/work","audit_seq":3002,"audit_key":"exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.350Z","source":"audit","event_type":"fs_create","pid":6102,"ppid":6090,"uid":1001,"gid":1001,"comm":"mkdir","exe":"/usr/bin/mkdir","details":{"path":"/work/personal_files","cmd":"mkdir -p /work/personal_files","cwd":"/work","audit_seq":3003,"audit_key":"fs_watch"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.700Z","source":"audit","event_type":"exec","pid":6103,"ppid":6090,"uid":1001,"gid":1001,"comm":"touch","exe":"/usr/bin/touch","details":{"cmd":"touch /work/personal_files/notes.txt","cwd":"/work","audit_seq":3004,"audit_key":"exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.950Z","source":"audit","event_type":"fs_create","pid":6103,"ppid":6090,"uid":1001,"gid":1001,"comm":"touch","exe":"/usr/bin/touch","details":{"path":"/work/personal_files/notes.txt","cmd":"touch /work/personal_files/notes.txt","cwd":"/work","audit_seq":3005,"audit_key":"fs_watch"}}
```

UI-style filtered logs table mock (Scenario B)
```text
| ts (UTC)                    | source | event_type | comm  | pid  | target                               |
| 2026-01-28T20:05:01.200Z     | ebpf   | dns_query  | codex | 6090 | example.com                          |
| 2026-01-28T20:05:02.100Z     | audit  | exec       | bash  | 6101 | pwd                                  |
| 2026-01-28T20:05:02.300Z     | audit  | exec       | mkdir | 6102 | mkdir -p /work/personal_files        |
| 2026-01-28T20:05:02.350Z     | audit  | fs_create  | mkdir | 6102 | /work/personal_files                 |
| 2026-01-28T20:05:02.700Z     | audit  | exec       | touch | 6103 | touch /work/personal_files/notes.txt |
| 2026-01-28T20:05:02.950Z     | audit  | fs_create  | touch | 6103 | /work/personal_files/notes.txt       |
```

## Appendix: Raw `audit.log` Grounding Examples (Collector Raw Smoke)

This appendix is a worked example of what raw auditd records typically look
like for common filesystem mutations under `/work`.

It is grounded in the collector-only raw smoke integration test:
- `tests/integration/test_collector_raw_smoke.py`

In a run-scoped deployment, raw audit output lives at:
- `<log_root>/<run_id>/collector/raw/audit.log`

Sequence numbers, PIDs, and timestamps vary per run, but the pattern is
consistent. Each logical event shares the same `msg=audit(...:<seq>)` value.

### Overview

In `tests/integration/test_collector_raw_smoke.py` we generate the following filesystem commands:
```
echo hi > /work/a.txt
mv /work/a.txt /work/b.txt
chmod 600 /work/b.txt
rm /work/b.txt
```
Below are matching raw audit records from `<log_root>/<run_id>/collector/raw/audit.log`.

### echo hi > /work/a.txt (create/write)
Exec of the shell that runs the compound command:
```text
type=SYSCALL msg=audit(1768895520.566:1731): arch=c00000b7 syscall=221 success=yes exit=0 a0=40001e9b50 a1=4000020a60 a2=4000020a80 a3=0 items=2 ppid=7405 pid=7428 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="sh" exe="/bin/busybox" key="exec"
type=EXECVE msg=audit(1768895520.566:1731): argc=3 a0="sh" a1="-c" a2=6563686F206869203E202F776F726B2F612E7478743B206D76202F776F726B2F612E747874202F776F726B2F622E7478743B2063686D6F6420363030202F776F726B2F622E7478743B20726D202F776F726B2F622E747874
```

#### Deeper dive: what the fields mean
```text
  - type=SYSCALL: this line is the primary syscall record for the event.
  - msg=audit(1768895520.566:1731): timestamp + sequence number. All lines with :1731 are the same logical event.
  - arch=c00000b7: syscall ABI. c00000b7 is AArch64 (64‑bit ARM) in audit’s encoding.
  - syscall=221: the syscall number. On aarch64, 221 is execve.
  - success=yes: the syscall succeeded.
  - exit=0: return value (0 on success for exec).
  - a0..a3: raw syscall arguments (register values). For execve, they correspond to:
      - a0 = filename pointer
      - a1 = argv pointer
      - a2 = envp pointer
      - a3 unused here
        Audit shows these as raw hex addresses, not decoded.
  - items=2: number of PATH records attached to this event.
  - ppid=7405, pid=7428: parent/child process IDs.
  - auid=4294967295: “audit uid” (AUID). 4294967295 is “unset” (aka -1).
  - uid/gid/euid/egid/suid/...: real/effective/saved filesystem UIDs/GIDs.
  - tty=(none): no controlling terminal.
  - ses=4294967295: audit session id (unset here).
  - comm="sh": kernel “comm” (process name, max 15 chars).
  - exe="/bin/busybox": resolved path of the executed binary.
  - key="exec": the audit rule key that matched (from -k exec).
```
##### Why comm="sh"?
Because the process being executed is sh, not echo. The command sequence runs as `sh -c "echo hi > ...; mv ...; chmod ...; rm ..."`. The kernel reports the process name (comm) as the program that was exec’d — here, sh from BusyBox.

##### Why doesn’t echo show up?
In Alpine/BusyBox, echo is typically a shell builtin, not a separate executable. That means no new process is started for echo, so
there’s no exec event to log. The file write shows up, but the echo binary never runs because there isn’t one.

##### Why exe="/bin/busybox"?
In Alpine, /bin/sh is a symlink to BusyBox (/bin/busybox). The kernel resolves the actual binary path and reports it as the exe. So
even though you ran sh, the executable is BusyBox.

File create in /work:
```text
type=SYSCALL msg=audit(1768895520.569:1732): arch=c00000b7 syscall=56 success=yes exit=3 a0=ffffffffffffff9c a1=ffffb2971498 a2=20241 a3=1b6 items=2 ppid=7405 pid=7428 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="sh" exe="/bin/busybox" key="fs_watch"
type=PATH msg=audit(1768895520.569:1732): item=0 name="/work/" inode=5 dev=00:2d mode=040755 ouid=0 ogid=0 rdev=00:00 nametype=PARENT cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
type=PATH msg=audit(1768895520.569:1732): item=1 name="/work/a.txt" inode=11 dev=00:2b mode=0100644 ouid=0 ogid=0 rdev=00:00 nametype=CREATE cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
```

### mv /work/a.txt /work/b.txt (rename)
Exec of mv:
```text
type=SYSCALL msg=audit(1768895520.570:1733): arch=c00000b7 syscall=221 success=yes exit=0 a0=ffffb29715a8 a1=ffffb29714a8 a2=ffffb29714c8 a3=6f00766d items=2 ppid=7428 pid=7443 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="mv" exe="/bin/busybox" key="exec"
type=EXECVE msg=audit(1768895520.570:1733): argc=3 a0="mv" a1="/work/a.txt" a2="/work/b.txt"
```
Rename in /work (DELETE old path, CREATE new path):
```text
type=SYSCALL msg=audit(1768895520.570:1734): arch=c00000b7 syscall=38 success=yes exit=0 a0=ffffffffffffff9c a1=ffffebe9ef67 a2=ffffffffffffff9c a3=ffffebe9ef73 items=7 ppid=7428 pid=7443 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="mv" exe="/bin/busybox" key="fs_watch"
type=PATH msg=audit(1768895520.570:1734): item=2 name="/work/a.txt" inode=11 dev=00:2b mode=0100644 ouid=0 ogid=0 rdev=00:00 nametype=DELETE cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
type=PATH msg=audit(1768895520.570:1734): item=3 name="/work/b.txt" inode=11 dev=00:2d mode=0100644 ouid=0 ogid=0 rdev=00:00 nametype=CREATE cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
```

### chmod 600 /work/b.txt (metadata change)
Exec of chmod:
```text
type=SYSCALL msg=audit(1768895520.571:1735): arch=c00000b7 syscall=221 success=yes exit=0 a0=ffffb29715a8 a1=ffffb29714a0 a2=ffffb29714c0 a3=646f6d6863 items=2 ppid=7428 pid=7444 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="chmod" exe="/bin/busybox" key="exec"
type=EXECVE msg=audit(1768895520.571:1735): argc=3 a0="chmod" a1="600" a2="/work/b.txt"
```
Attribute change captured by watch (chmod can also match fs_meta depending on rules):
```text
type=SYSCALL msg=audit(1768895520.571:1736): arch=c00000b7 syscall=53 success=yes exit=0 a0=ffffffffffffff9c a1=ffffe9fa5f70 a2=180 a3=7ffffff items=1 ppid=7428 pid=7444 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="chmod" exe="/bin/busybox" key="fs_watch"
type=PATH msg=audit(1768895520.571:1736): item=0 name="/work/b.txt" inode=11 dev=00:2d mode=0100644 ouid=0 ogid=0 rdev=00:00 nametype=NORMAL cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
```

### rm /work/b.txt (unlink)
Exec of rm:
```text
type=SYSCALL msg=audit(1768895520.574:1737): arch=c00000b7 syscall=221 success=yes exit=0 a0=ffffb29714d0 a1=ffffb2971488 a2=ffffb29714a0 a3=646f006d72 items=2 ppid=7405 pid=7428 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="rm" exe="/bin/busybox" key="exec"
type=EXECVE msg=audit(1768895520.574:1737): argc=2 a0="rm" a1="/work/b.txt"
```
Delete in /work:
```text
type=SYSCALL msg=audit(1768895520.574:1738): arch=c00000b7 syscall=35 success=yes exit=0 a0=ffffffffffffff9c a1=ffffd6fa2f73 a2=0 a3=0 items=3 ppid=7405 pid=7428 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="rm" exe="/bin/busybox" key="fs_watch"
type=PATH msg=audit(1768895520.574:1738): item=0 name="/work/" inode=5 dev=00:2d mode=040755 ouid=0 ogid=0 rdev=00:00 nametype=PARENT cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
type=PATH msg=audit(1768895520.574:1738): item=1 name="/work/b.txt" inode=11 dev=00:2b mode=0100600 ouid=0 ogid=0 rdev=00:00 nametype=DELETE cap_fp=0 cap_fi=0 cap_fe=0 cap_fver=0 cap_frootid=0
```

For how these records are normalized into one JSON object per logical event,
see `docs/contracts/schemas/auditd.filtered.v1.md`.
