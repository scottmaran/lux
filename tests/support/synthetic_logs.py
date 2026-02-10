from __future__ import annotations

from datetime import datetime, timezone


def _ts(value: str | None = None) -> str:
    if value:
        return value
    return datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def ebpf_net_connect(
    *,
    ts: str | None = None,
    pid: int = 1234,
    ppid: int = 1200,
    uid: int = 1001,
    gid: int = 1001,
    comm: str = "python3",
    dst_ip: str = "127.0.0.1",
    dst_port: int = 22,
    src_ip: str = "0.0.0.0",
    src_port: int = 0,
    protocol: str = "tcp",
    family: str = "ipv4",
    syscall_result: int = 0,
) -> dict:
    return {
        "schema_version": "ebpf.v1",
        "ts": _ts(ts),
        "event_type": "net_connect",
        "pid": pid,
        "ppid": ppid,
        "uid": uid,
        "gid": gid,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": syscall_result,
        "net": {
            "protocol": protocol,
            "family": family,
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
        },
    }


def ebpf_net_send(
    *,
    ts: str | None = None,
    bytes_sent: int = 64,
    **kwargs,
) -> dict:
    event = ebpf_net_connect(ts=ts, **kwargs)
    event["event_type"] = "net_send"
    event["net"]["bytes"] = bytes_sent
    event["syscall_result"] = bytes_sent
    return event


def ebpf_dns_query(
    *,
    ts: str | None = None,
    pid: int = 1234,
    ppid: int = 1200,
    uid: int = 1001,
    gid: int = 1001,
    comm: str = "python3",
    query_name: str = "example.com",
    query_type: str = "A",
    server_ip: str = "127.0.0.11",
    server_port: int = 53,
    transport: str = "udp",
) -> dict:
    return {
        "schema_version": "ebpf.v1",
        "ts": _ts(ts),
        "event_type": "dns_query",
        "pid": pid,
        "ppid": ppid,
        "uid": uid,
        "gid": gid,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "dns": {
            "transport": transport,
            "query_name": query_name,
            "query_type": query_type,
            "server_ip": server_ip,
            "server_port": server_port,
        },
    }


def ebpf_dns_response(
    *,
    ts: str | None = None,
    pid: int = 1234,
    ppid: int = 1200,
    uid: int = 1001,
    gid: int = 1001,
    comm: str = "python3",
    query_name: str = "example.com",
    query_type: str = "A",
    answers: list[str] | None = None,
    rcode: str = "NOERROR",
    transport: str = "udp",
) -> dict:
    return {
        "schema_version": "ebpf.v1",
        "ts": _ts(ts),
        "event_type": "dns_response",
        "pid": pid,
        "ppid": ppid,
        "uid": uid,
        "gid": gid,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "dns": {
            "transport": transport,
            "query_name": query_name,
            "query_type": query_type,
            "rcode": rcode,
            "answers": answers or ["93.184.216.34"],
        },
    }


def ebpf_unix_connect(
    *,
    ts: str | None = None,
    pid: int = 1234,
    ppid: int = 1200,
    uid: int = 1001,
    gid: int = 1001,
    comm: str = "python3",
    path: str = "/var/run/docker.sock",
    sock_type: str = "stream",
    abstract: bool = False,
    syscall_result: int = 0,
) -> dict:
    return {
        "schema_version": "ebpf.v1",
        "ts": _ts(ts),
        "event_type": "unix_connect",
        "pid": pid,
        "ppid": ppid,
        "uid": uid,
        "gid": gid,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": syscall_result,
        "unix": {
            "path": path,
            "abstract": abstract,
            "sock_type": sock_type,
        },
    }


def audit_syscall_line(
    *,
    ts_sec: int,
    seq: int,
    pid: int,
    ppid: int,
    uid: int,
    gid: int,
    comm: str,
    exe: str,
    key: str,
    success: str = "yes",
    exit_code: int = 0,
) -> str:
    return (
        f'type=SYSCALL msg=audit({ts_sec}.123:{seq}): arch=c00000b7 syscall=221 success={success} '
        f'exit={exit_code} pid={pid} ppid={ppid} uid={uid} gid={gid} comm="{comm}" exe="{exe}" key="{key}"'
    )


def audit_execve_line(*, ts_sec: int, seq: int, argv: list[str]) -> str:
    args = " ".join(f'a{i}="{arg}"' for i, arg in enumerate(argv))
    return f"type=EXECVE msg=audit({ts_sec}.123:{seq}): argc={len(argv)} {args}"


def audit_cwd_line(*, ts_sec: int, seq: int, cwd: str) -> str:
    return f'type=CWD msg=audit({ts_sec}.123:{seq}): cwd="{cwd}"'


def audit_path_line(*, ts_sec: int, seq: int, name: str, nametype: str) -> str:
    return f'type=PATH msg=audit({ts_sec}.123:{seq}): item=0 name="{name}" nametype={nametype}'
