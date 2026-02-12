# Example Flow: Lasso (Agent Harness)

## Overview summary
This document is a fully self-contained, procedural example of what the Lasso stack should do end to end. It shows two distinct scenarios (TUI and server-mode job), the user prompts, the underlying commands, the expected workspace changes, the log rows across all log files, and the final UI output derived from filtered logs. All timestamps are UTC.

Run-layout note (Feb 2026): all collector/harness artifacts are run-scoped
under `logs/<run_id>/...` where `<run_id>` is typically
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
  -f compose.yml -f compose.codex.yml \
  up -d --pull never collector agent
```

3) Launch the harness TUI (Scenario A).
```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml \
  run --rm \
  -e HARNESS_MODE=tui \
  harness
```

4) Start the stack for server mode (Scenario B).
```bash
export HARNESS_API_TOKEN=dev-token
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml \
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
  -f compose.yml -f compose.codex.yml \
  exec -T collector \
  collector-merge-filtered --config /logs/merge_filtering_example.yaml
```
Note: the current collector entrypoint also writes `filtered_ebpf_summary.jsonl`
and the default merge config uses that summary file for UI-friendly `net_summary`
rows. This example keeps raw `filtered_ebpf.jsonl` to keep the snippets small.

7) (Optional) Tear down between scenarios.
```bash
docker compose --env-file ~/.config/lasso/compose.env \
  -f compose.yml -f compose.codex.yml \
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
- `logs/<run_id>/harness/sessions/session_20260128_200000_ab12/meta.json`: 1 JSON object
- `logs/<run_id>/harness/sessions/session_20260128_200000_ab12/stdin.log`: 2 lines
- `logs/<run_id>/harness/sessions/session_20260128_200000_ab12/stdout.log`: 2 lines

Example snippets:
`logs/<run_id>/harness/sessions/session_20260128_200000_ab12/meta.json`
```json
{
  "command": "codex -C /work -s danger-full-access",
  "ended_at": "2026-01-28T20:00:05.000Z",
  "exit_code": 0,
  "mode": "tui",
  "session_id": "session_20260128_200000_ab12",
  "started_at": "2026-01-28T20:00:00.100Z",
  "stdin_path": "/logs/<run_id>/harness/sessions/session_20260128_200000_ab12/stdin.log",
  "stdout_path": "/logs/<run_id>/harness/sessions/session_20260128_200000_ab12/stdout.log"
}
```

`logs/<run_id>/harness/sessions/session_20260128_200000_ab12/stdin.log`
```
Confirm the current working directory.
Create a new notes.txt file in a new directory personal_files.
```

`logs/<run_id>/harness/sessions/session_20260128_200000_ab12/stdout.log`
```
/work
Created /work/personal_files/notes.txt
```

### Scenario B (server mode)
Log row counts:
- `logs/<run_id>/harness/jobs/job_20260128_200500_cd34/input.json`: 1 JSON object
- `logs/<run_id>/harness/jobs/job_20260128_200500_cd34/stdout.log`: 2 lines
- `logs/<run_id>/harness/jobs/job_20260128_200500_cd34/stderr.log`: 0 lines
- `logs/<run_id>/harness/jobs/job_20260128_200500_cd34/status.json`: 1 JSON object

Example snippets:
`logs/<run_id>/harness/jobs/job_20260128_200500_cd34/input.json`
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

`logs/<run_id>/harness/jobs/job_20260128_200500_cd34/stdout.log`
```
/work
Created /work/personal_files/notes.txt
```

`logs/<run_id>/harness/jobs/job_20260128_200500_cd34/stderr.log`
```
```

`logs/<run_id>/harness/jobs/job_20260128_200500_cd34/status.json`
```json
{
  "ended_at": "2026-01-28T20:05:02.050Z",
  "error": null,
  "error_path": "/logs/<run_id>/harness/jobs/job_20260128_200500_cd34/stderr.log",
  "exit_code": 0,
  "job_id": "job_20260128_200500_cd34",
  "output_path": "/logs/<run_id>/harness/jobs/job_20260128_200500_cd34/stdout.log",
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
- `logs/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `logs/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`logs/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"audit_seq":2001,"audit_key":"exec","agent_owned":true}
```

`logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}
```

`logs/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}}
```

### Scenario B (server mode)
Agent-owned row counts (all rows in these files are agent-owned for this scenario):
- `logs/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `logs/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`logs/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"audit_seq":3001,"audit_key":"exec","agent_owned":true}
```

`logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}
```

`logs/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}}
```

## Collector container logs
### Scenario A (TUI)
Log row counts:
- `logs/<run_id>/collector/raw/audit.log`: 15 lines (5 logical events, 3 lines each)
- `logs/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `logs/<run_id>/collector/raw/ebpf.jsonl`: 1 row
- `logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `logs/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`logs/<run_id>/collector/raw/audit.log` (single logical event with multiple lines)
```text
type=SYSCALL msg=audit(1769630402.100:2001): arch=c00000b7 syscall=221 success=yes exit=0 ppid=5090 pid=5101 uid=1001 gid=1001 comm="bash" exe="/usr/bin/bash" key="exec"
type=EXECVE msg=audit(1769630402.100:2001): argc=3 a0="bash" a1="-lc" a2="pwd"
type=CWD msg=audit(1769630402.100:2001): cwd="/work"
```

`logs/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"audit_seq":2001,"audit_key":"exec","agent_owned":true}
{"schema_version":"auditd.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:03.050Z","source":"audit","event_type":"fs_create","path":"/work/personal_files","cwd":"/work","comm":"mkdir","exe":"/usr/bin/mkdir","pid":5102,"ppid":5090,"uid":1001,"gid":1001,"audit_seq":2003,"audit_key":"fs_watch","agent_owned":true,"cmd":"mkdir -p /work/personal_files"}
```

`logs/<run_id>/collector/raw/ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.v1","ts":"2026-01-28T20:00:01.500000000Z","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"}}
```

`logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}
```

`logs/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:01.500000000Z","source":"ebpf","event_type":"unix_connect","pid":5090,"ppid":5080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000abc","syscall_result":0,"unix":{"path":"/run/dbus/system_bus_socket","abstract":false,"sock_type":"stream"},"cmd":"codex -C /work -s danger-full-access"}}
{"schema_version":"timeline.filtered.v1","session_id":"session_20260128_200000_ab12","ts":"2026-01-28T20:00:02.100Z","source":"audit","event_type":"exec","pid":5101,"ppid":5090,"uid":1001,"gid":1001,"comm":"bash","exe":"/usr/bin/bash","details":{"cmd":"pwd","cwd":"/work","audit_seq":2001,"audit_key":"exec"}}
```

### Scenario B (server mode)
Log row counts:
- `logs/<run_id>/collector/raw/audit.log`: 15 lines (5 logical events, 3 lines each)
- `logs/<run_id>/collector/filtered/filtered_audit.jsonl`: 5 rows
- `logs/<run_id>/collector/raw/ebpf.jsonl`: 1 row
- `logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`: 1 row
- `logs/<run_id>/collector/filtered/filtered_timeline.jsonl`: 6 rows

Example snippets:
`logs/<run_id>/collector/raw/audit.log` (single logical event with multiple lines)
```text
type=SYSCALL msg=audit(1769630702.900:3002): arch=c00000b7 syscall=221 success=yes exit=0 ppid=6090 pid=6102 uid=1001 gid=1001 comm="mkdir" exe="/usr/bin/mkdir" key="exec"
type=EXECVE msg=audit(1769630702.900:3002): argc=4 a0="mkdir" a1="-p" a2="/work/personal_files" a3=""
type=CWD msg=audit(1769630702.900:3002): cwd="/work"
```

`logs/<run_id>/collector/filtered/filtered_audit.jsonl`
```jsonl
{"schema_version":"auditd.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","cmd":"pwd","cwd":"/work","comm":"bash","exe":"/usr/bin/bash","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"audit_seq":3001,"audit_key":"exec","agent_owned":true}
{"schema_version":"auditd.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.950Z","source":"audit","event_type":"fs_create","path":"/work/personal_files/notes.txt","cwd":"/work","comm":"touch","exe":"/usr/bin/touch","pid":6103,"ppid":6090,"uid":1001,"gid":1001,"audit_seq":3005,"audit_key":"fs_watch","agent_owned":true,"cmd":"touch /work/personal_files/notes.txt"}
```

`logs/<run_id>/collector/raw/ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.v1","ts":"2026-01-28T20:05:01.200000000Z","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53}}
```

`logs/<run_id>/collector/filtered/filtered_ebpf.jsonl`
```jsonl
{"schema_version":"ebpf.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}
```

`logs/<run_id>/collector/filtered/filtered_timeline.jsonl`
```jsonl
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:01.200000000Z","source":"ebpf","event_type":"dns_query","pid":6090,"ppid":6080,"uid":1001,"gid":1001,"comm":"codex","details":{"cgroup_id":"0x0000000000000def","syscall_result":0,"dns":{"transport":"udp","query_name":"example.com","query_type":"A","server_ip":"127.0.0.11","server_port":53},"cmd":"codex -C /work -s danger-full-access exec"}}
{"schema_version":"timeline.filtered.v1","session_id":"unknown","job_id":"job_20260128_200500_cd34","ts":"2026-01-28T20:05:02.100Z","source":"audit","event_type":"exec","pid":6101,"ppid":6090,"uid":1001,"gid":1001,"comm":"bash","exe":"/usr/bin/bash","details":{"cmd":"pwd","cwd":"/work","audit_seq":3001,"audit_key":"exec"}}
```

## Final UI output from filtered logs
### Scenario A (TUI)
`logs/<run_id>/collector/filtered/filtered_timeline.jsonl` (full file for this scenario)
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
`logs/<run_id>/collector/filtered/filtered_timeline.jsonl` (full file for this scenario)
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
