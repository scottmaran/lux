# Auditd Raw Log Format (audit.log)
Layer: Contract

This document describes the raw auditd log format as written by `auditd` in the
collector container.

The collector pipeline consumes this file and produces `auditd.filtered.v1`
JSONL. For the filtered JSONL contract, see `docs/contracts/schemas/auditd.filtered.v1.md`.

Where it shows up:
- In a run-scoped deployment, the raw audit file is typically
  `logs/<run_id>/collector/raw/audit.log`.
- The exact path is controlled by `COLLECTOR_AUDIT_LOG` and the collector
  entrypoint rewrites `auditd.conf` at runtime to point `log_file` at that path.

## Record grouping
Auditd writes one record per line. Each logical event is composed of multiple
records that share the same `msg=audit(<epoch>.<subsec>:<seq>)` identifier.

Only the `SYSCALL` record usually carries the audit rule key (`key="..."`). The
related `EXECVE`, `PATH`, `CWD`, `PROCTITLE` records for the same event can show
`key=(null)` even though the event matched a keyed rule. Group by the shared
`seq` to recover the key from the `SYSCALL`.

Example (one logical exec event):
```text
type=SYSCALL msg=audit(1768893700.538:12): arch=c00000b7 syscall=221 success=yes exit=0 ... pid=598 ppid=555 uid=0 gid=0 comm="collector-ebpf-" exe="/usr/local/bin/collector-ebpf-loader" key="exec"
type=EXECVE msg=audit(1768893700.538:12): argc=1 a0="/usr/local/bin/collector-ebpf-loader"
type=CWD msg=audit(1768893700.538:12): cwd="/"
type=PATH msg=audit(1768893700.538:12): item=0 name="/usr/local/bin/collector-ebpf-loader" ... nametype=NORMAL
```

## Record types we rely on
Common record types seen in `audit.log`:
- `SYSCALL`: primary record with `pid`/`ppid`/`uid`/`gid`, syscall number, success, exit code, and usually the rule key.
- `EXECVE`: argv list for exec events.
- `PATH`: file path(s), with `nametype` describing role (`NORMAL`/`CREATE`/`DELETE`/`PARENT`).
- `CWD`: current working directory.
- `PROCTITLE`: hex-encoded command line (often redundant with `EXECVE` for our use).
- `BPRM_FCAPS`: exec metadata (capabilities).
- `CONFIG_CHANGE` / `DAEMON_START` / `DAEMON_END`: auditd lifecycle/control events.

## Rule keys used by this repo
Rule keys come from `collector/config/rules.d/harness.rules`:
- `exec`: process start events (`execve`/`execveat`) used for PID lineage attribution.
- `fs_watch`: workspace writes + attribute changes via `-w /work -p wa`.
- `fs_change`: rename/unlink/link/symlink in workspace via syscall rules.
- `fs_meta`: chmod/chown/xattr/utime in workspace via syscall rules.

## Worked examples (illustrative)
These examples are intentionally small; real audit records include many more
fields and will vary by kernel version, distro, and CPU architecture.

### Workspace rename (DELETE + CREATE PATH records)
Renames often show up as a logical audit event containing multiple `PATH`
records, including a `DELETE` for the old name and a `CREATE` for the new name:

```text
type=SYSCALL msg=audit(1768895520.570:1734): ... comm="mv" exe="/bin/busybox" key="fs_watch"
type=PATH msg=audit(1768895520.570:1734): item=2 name="/work/a.txt" ... nametype=DELETE
type=PATH msg=audit(1768895520.570:1734): item=3 name="/work/b.txt" ... nametype=CREATE
```

Downstream:
- The audit filter derives `fs_rename` when it sees both `CREATE` and `DELETE`
  nametypes in the same grouped event (regardless of the audit rule key).
- For the normalized schema, see `docs/contracts/schemas/auditd.filtered.v1.md`.

More grounded raw examples and commentary (including common gotchas like shell
builtins not producing exec events) live in `docs/dev/example_flow.md`.
