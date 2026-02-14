# `harness.rules` (Audit Rule Set)

This file defines the audit rules loaded by the collector to capture:
- exec events (for PID lineage attribution)
- filesystem mutations within the workspace scope (`/work`)
- metadata changes within the workspace scope (`/work`)

File:
- `collector/config/rules.d/harness.rules` (loaded via `auditctl -R ...`)

## Keys and intended semantics
The rules use `-k <key>` to tag events:
- `exec`: execve/execveat events (used to build the PID/PPID tree)
- `fs_watch`: watch-based workspace signal (`-w /work -p wa`)
- `fs_change`: rename/unlink/link/symlink within `/work` via syscalls
- `fs_meta`: chmod/chown/xattr/utime within `/work` via syscalls

Downstream filtering uses these keys heavily. See:
- Raw audit format: `collector/auditd_raw_data.md`
- Filtered audit schema: `collector/auditd_filtered_data.md`

## Rule breakdown (current)

Exec (attribution anchor):
- `-a always,exit -F arch=b64 -S execve,execveat -k exec`

Workspace watch:
- `-w /work -p wa -k fs_watch`

Rename/unlink/link/symlink under `/work`:
- `-a always,exit -F arch=b64 -S renameat,renameat2,unlinkat,linkat,symlinkat -F dir=/work -k fs_change`

Metadata changes under `/work`:
- `-a always,exit -F arch=b64 -S fchmod,fchmodat,fchown,fchownat,setxattr,lsetxattr,fsetxattr,removexattr,lremovexattr,fremovexattr,utimensat -F dir=/work -k fs_meta`

Notes:
- This syscall list is chosen to be aarch64-compatible (avoid syscalls that do
  not exist on that ABI).
- `-w /work -p wa` includes attribute changes too, so you can see overlap with
  `fs_meta` rules depending on kernel/audit behavior.

