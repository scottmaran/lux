from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tests.support.module_loader import load_module


EBPF_MODULE = load_module(
    "filter_ebpf_logs",
    Path(__file__).resolve().parents[2] / "collector" / "scripts" / "filter_ebpf_logs.py",
)


@pytest.mark.unit
def test_parse_ebpf_ts_handles_nanoseconds() -> None:
    """Nanosecond timestamp strings normalize into timezone-aware datetimes."""
    parsed = EBPF_MODULE.parse_ebpf_ts("2026-01-01T00:00:00.123456789Z")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.microsecond == 123456


@pytest.mark.unit
def test_build_output_keeps_event_specific_payload() -> None:
    """Output builder preserves net/dns/unix payloads by event type."""
    base = {
        "ts": "2026-01-01T00:00:00.123Z",
        "pid": 10,
        "ppid": 1,
        "uid": 1001,
        "gid": 1001,
        "comm": "python3",
        "cgroup_id": "0x1",
        "syscall_result": 0,
    }

    net_event = dict(base)
    net_event["event_type"] = "net_connect"
    net_event["net"] = {"dst_ip": "127.0.0.1", "dst_port": 22}
    net_out = EBPF_MODULE.build_output(net_event, "session_1", None, "cmd", "ebpf.filtered.v1")
    assert net_out["net"]["dst_port"] == 22

    dns_event = dict(base)
    dns_event["event_type"] = "dns_response"
    dns_event["dns"] = {"query_name": "example.com", "answers": ["1.2.3.4"]}
    dns_out = EBPF_MODULE.build_output(dns_event, "session_1", None, None, "ebpf.filtered.v1")
    assert dns_out["dns"]["query_name"] == "example.com"

    unix_event = dict(base)
    unix_event["event_type"] = "unix_connect"
    unix_event["unix"] = {"path": "/tmp/test.sock"}
    unix_out = EBPF_MODULE.build_output(unix_event, "session_1", None, None, "ebpf.filtered.v1")
    assert unix_out["unix"]["path"] == "/tmp/test.sock"


@pytest.mark.unit
def test_pending_buffer_prunes_by_ttl_and_enforces_limits() -> None:
    """Pending buffer drops expired entries and bounds total/pid queue sizes."""
    buffer = EBPF_MODULE.PendingBuffer(ttl_sec=0.5, max_per_pid=1, max_total=2)
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

    buffer.add(100, t0, {"event": 1})
    buffer.add(100, t0 + dt.timedelta(milliseconds=10), {"event": 2})
    buffer.add(200, t0 + dt.timedelta(milliseconds=20), {"event": 3})

    # max_per_pid=1 keeps latest event for pid 100.
    popped_100 = buffer.pop(100, t0 + dt.timedelta(milliseconds=20))
    assert len(popped_100) == 1
    assert popped_100[0].event["event"] == 2

    # ttl pruning removes expired events before pop.
    popped_200 = buffer.pop(200, t0 + dt.timedelta(seconds=2))
    assert popped_200 == []


@pytest.mark.unit
def test_extract_exec_respects_exec_keys_filter() -> None:
    """Ownership extraction ignores syscall groups whose audit key is not configured as exec."""
    ts = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    records = [
        {
            "type": "SYSCALL",
            "seq": 1,
            "ts": ts,
            "fields": {
                "key": "not_exec",
                "pid": "10",
                "ppid": "1",
                "uid": "1001",
                "comm": "bash",
            },
        },
        {
            "type": "EXECVE",
            "seq": 1,
            "ts": ts,
            "fields": {"a0": "bash", "a1": "-lc", "a2": "pwd"},
        },
    ]
    cfg = {"ownership": {"exec_keys": ["exec"]}, "exec": {"shell_comm": ["bash"], "shell_cmd_flag": "-lc"}}
    assert EBPF_MODULE.extract_exec(records, cfg) is None
