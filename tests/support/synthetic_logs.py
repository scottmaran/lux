from __future__ import annotations

"""
Synthetic log/event builders used by fixture, integration, regression, and
stress tests.

The helpers in this module generate minimal-but-valid audit and eBPF records
that mimic collector-relevant structure from runtime output. Tests use these
builders to produce deterministic inputs for attribution, filtering, summary,
and merge assertions without depending on host-level audit/eBPF timing.
"""

from datetime import datetime, timezone


def make_syscall(
    *,
    ts: str,
    seq: int,
    pid: int,
    ppid: int,
    key: str,
    comm: str,
    exe: str,
    uid: int = 1001,
    gid: int = 1001,
    success: str = "yes",
    exit_code: int = 0,
) -> str:
    return (
        f'type=SYSCALL msg=audit({ts}:{seq}): arch=c00000b7 syscall=221 success={success} exit={exit_code} '
        f'pid={pid} ppid={ppid} uid={uid} gid={gid} comm="{comm}" exe="{exe}" key="{key}"'
    )


def make_execve(*, ts: str, seq: int, argv: list[str]) -> str:
    args = " ".join(f'a{i}="{arg}"' for i, arg in enumerate(argv))
    return f"type=EXECVE msg=audit({ts}:{seq}): argc={len(argv)} {args}"


def make_cwd(*, ts: str, seq: int, cwd: str) -> str:
    return f'type=CWD msg=audit({ts}:{seq}): cwd="{cwd}"'


def make_path(*, ts: str, seq: int, name: str, nametype: str) -> str:
    return f'type=PATH msg=audit({ts}:{seq}): item=0 name="{name}" nametype={nametype}'


def build_job_fs_sequence(
    *,
    root_pid: int,
    child_pid: int,
    target_path: str,
    seq_start: int,
    ts_root: str,
    ts_child: str,
    ts_fs: str,
) -> list[str]:
    command = f"printf data > {target_path}"
    return [
        make_syscall(
            ts=ts_root,
            seq=seq_start,
            pid=root_pid,
            ppid=1,
            key="exec",
            comm="bash",
            exe="/usr/bin/bash",
        ),
        make_execve(ts=ts_root, seq=seq_start, argv=["bash", "-lc", command]),
        make_syscall(
            ts=ts_child,
            seq=seq_start + 1,
            pid=child_pid,
            ppid=root_pid,
            key="exec",
            comm="bash",
            exe="/usr/bin/bash",
        ),
        make_execve(ts=ts_child, seq=seq_start + 1, argv=["bash", "-lc", command]),
        make_cwd(ts=ts_child, seq=seq_start + 1, cwd="/work"),
        make_syscall(
            ts=ts_fs,
            seq=seq_start + 2,
            pid=child_pid,
            ppid=root_pid,
            key="fs_watch",
            comm="bash",
            exe="/usr/bin/bash",
        ),
        make_path(ts=ts_fs, seq=seq_start + 2, name=target_path, nametype="CREATE"),
    ]


def make_net_send_event(*, pid: int, ppid: int, dst_ip: str = "93.184.216.34", dst_port: int = 443, bytes_sent: int = 11) -> dict:
    ts = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "schema_version": "ebpf.v1",
        "ts": ts,
        "event_type": "net_send",
        "pid": pid,
        "ppid": ppid,
        "uid": 1001,
        "gid": 1001,
        "comm": "bash",
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "net": {
            "protocol": "tcp",
            "family": "ipv4",
            "src_ip": "172.18.0.3",
            "src_port": 44444,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "bytes": bytes_sent,
        },
    }
