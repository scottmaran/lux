# Auditd Data Schema (v1)

This document defines how auditd emits raw logs.

# Auditd functionality

Here is a list of some common options available to the auditctlutility.

```text
-w : adds a watch to the file. auditd will record the user activities of that particular file.
-k : on a specific auditd rule, sets an optional string or key, which can be used for identifying the rule (or a set of rules) that created a specific log entry,
-F : adds a field filter: “only match events where field X has value Y.”
-l : lists all currently loaded auditd rules in multiple lines, each line representing a rule.
-t : trims the subtrees that appear after a mount command.
-S : specifies which syscalls the rule applies to (e.g. -S execve,execveat means “only log exec syscalls.” )
-a : appends rule to the end of a comma-separated catalog of list and action pairs
    Valid list names – task, exit, user, exclude
    Valid action names – never, always
  The pairs can be in either of the following order:
    list, action
    action, list
```

# Raw auditd output
Auditd writes one record per line. Each logical event is composed of multiple
records that share the same `msg=audit(<epoch>.<subsec>:<seq>)` identifier.

Only the SYSCALL line usually carries the rule key. The related EXECVE, PATH, CWD, PROCTITLE lines for the same event can show key=(null) even though the event matched a keyed rule. Group by msg=audit(...:seq) to see the key on the SYSCALL.

Example (one logical exec event):
```text
type=SYSCALL msg=audit(1768893700.538:12): arch=c00000b7 syscall=221 success=yes exit=0 ... pid=598 ppid=555 uid=0 gid=0 comm="collector-ebpf-" exe="/usr/local/bin/collector-ebpf-loader" key="exec"
type=EXECVE msg=audit(1768893700.538:12): argc=1 a0="/usr/local/bin/collector-ebpf-loader"
type=CWD msg=audit(1768893700.538:12): cwd="/"
type=PATH msg=audit(1768893700.538:12): item=0 name="/usr/local/bin/collector-ebpf-loader" ... nametype=NORMAL
```

Common record types:
- `SYSCALL`: primary record with pid/ppid/uid/gid, syscall number, success, exit
- `EXECVE`: argv list for exec events
- `PATH`: file path(s), with `nametype` describing role (NORMAL/CREATE/DELETE/PARENT)
- `CWD`: current working directory
- `PROCTITLE`: hex-encoded command line
- `BPRM_FCAPS`: file capabilities (exec metadata)
- `CONFIG_CHANGE` / `DAEMON_START` / `DAEMON_END`: auditd lifecycle/control

Record grouping:
- The `seq` value in `msg=audit(...:<seq>)` identifies a single logical event.
- All records with the same `seq` should be grouped together.

Rule keys (from `collector/config/rules.d/harness.rules`):
- `exec`: process start events (execve/execveat)
- `fs_watch`: write/attribute activity under `/work`
- `fs_change`: rename/unlink/link/symlink under `/work`
- `fs_meta`: chmod/chown/xattr/utime under `/work`

## Example Raw Outputs from run_test.sh

### Overview

In run_test.sh we run the following commands:
```
echo hi > /work/a.txt
mv /work/a.txt /work/b.txt
chmod 600 /work/b.txt
rm /work/b.txt
```
Below are the matching raw audit records from logs/audit.log. Sequence numbers,
PIDs, and timestamps will vary per run, but the pattern is consistent. Each
logical event shares the same `msg=audit(...:<seq>)` value.

### echo hi > /work/a.txt (create/write)
Exec of the shell that runs the compound command:
```text
type=SYSCALL msg=audit(1768895520.566:1731): arch=c00000b7 syscall=221 success=yes exit=0 a0=40001e9b50 a1=4000020a60 a2=4000020a80 a3=0 items=2 ppid=7405 pid=7428 auid=4294967295 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm="sh" exe="/bin/busybox" key="exec"
type=EXECVE msg=audit(1768895520.566:1731): argc=3 a0="sh" a1="-c" a2=6563686F206869203E202F776F726B2F612E7478743B206D76202F776F726B2F612E747874202F776F726B2F622E7478743B2063686D6F6420363030202F776F726B2F622E7478743B20726D202F776F726B2F622E747874
```

#### deeper dive 
##### What the fields mean
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
Because the process being executed is sh, not echo. The command in run_test.sh runs as sh -c "echo hi > ...; mv ...; chmod ...;
rm ...". The kernel reports the process name (comm) as the program that was exec’d — here, sh from BusyBox.

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


