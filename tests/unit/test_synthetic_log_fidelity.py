from __future__ import annotations

import importlib.util
import json
import shlex
from pathlib import Path

import pytest

from tests.support.synthetic_logs import (
    make_dns_query_event,
    make_dns_response_event,
    make_net_connect_event,
    make_net_send_event,
    make_syscall,
    make_unix_connect_event,
)


pytestmark = pytest.mark.unit


ROOT_DIR = Path(__file__).resolve().parents[2]
EXAMPLE_AUDIT_PATH = ROOT_DIR / "example_logs" / "audit.log"
EXAMPLE_EBPF_PATH = ROOT_DIR / "example_logs" / "ebpf.jsonl"
AUDIT_FILTER_SCRIPT = ROOT_DIR / "collector" / "scripts" / "filter_audit_logs.py"


def _load_audit_filter_module():
    spec = importlib.util.spec_from_file_location("filter_audit_logs", AUDIT_FILTER_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {AUDIT_FILTER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_audit_kv_line(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in shlex.split(line, posix=True):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def _first_real_audit_syscall_line() -> str:
    for line in EXAMPLE_AUDIT_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("type=SYSCALL") and 'key="exec"' in line:
            return line
    raise AssertionError("No exec SYSCALL line found in example_logs/audit.log")


def _real_ebpf_events() -> list[dict]:
    events: list[dict] = []
    for line in EXAMPLE_EBPF_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def _first_real_event_of_type(events: list[dict], event_type: str) -> dict:
    for event in events:
        if event.get("event_type") == event_type:
            return event
    raise AssertionError(f"No event_type={event_type} found in example_logs/ebpf.jsonl")


def test_synthetic_exec_syscall_contains_realistic_core_fields() -> None:
    """Synthetic SYSCALL lines include collector-relevant fields also present in real audit output."""
    real_line = _first_real_audit_syscall_line()
    real_fields = _parse_audit_kv_line(real_line)

    synthetic_line = make_syscall(
        ts="1769030400.100",
        seq=123,
        pid=101,
        ppid=100,
        key="exec",
        comm="bash",
        exe="/usr/bin/bash",
    )
    synthetic_fields = _parse_audit_kv_line(synthetic_line)

    required = {
        "type",
        "msg",
        "arch",
        "syscall",
        "success",
        "exit",
        "pid",
        "ppid",
        "uid",
        "gid",
        "comm",
        "exe",
        "key",
    }

    assert required.issubset(real_fields), f"Real sample missing expected keys: {required - set(real_fields)}"
    assert required.issubset(synthetic_fields), (
        f"Synthetic line missing expected keys: {required - set(synthetic_fields)}"
    )


def test_synthetic_audit_line_parses_through_real_audit_filter_parser() -> None:
    """Synthetic SYSCALL format is accepted by the real audit parser path."""
    module = _load_audit_filter_module()
    synthetic_line = make_syscall(
        ts="1769030400.100",
        seq=200,
        pid=201,
        ppid=200,
        key="exec",
        comm="bash",
        exe="/usr/bin/bash",
    )
    parsed = module.parse_line(synthetic_line)
    assert parsed is not None, f"parse_line rejected synthetic syscall: {synthetic_line}"
    assert parsed.get("type") == "SYSCALL"
    assert parsed.get("seq") == 200


def test_synthetic_ebpf_builders_match_real_event_shapes() -> None:
    """Synthetic eBPF builders cover configured event types with production-shape keys."""
    real_events = _real_ebpf_events()

    builders = {
        "net_connect": make_net_connect_event(pid=101, ppid=100),
        "net_send": make_net_send_event(pid=101, ppid=100),
        "dns_query": make_dns_query_event(pid=101, ppid=100),
        "dns_response": make_dns_response_event(pid=101, ppid=100),
        "unix_connect": make_unix_connect_event(pid=101, ppid=100),
    }

    common_keys = {
        "schema_version",
        "ts",
        "event_type",
        "pid",
        "ppid",
        "uid",
        "gid",
        "comm",
        "cgroup_id",
        "syscall_result",
    }

    for event_type, synthetic in builders.items():
        real = _first_real_event_of_type(real_events, event_type)
        assert common_keys.issubset(synthetic), (
            f"synthetic {event_type} missing common keys: {common_keys - set(synthetic)}"
        )
        assert common_keys.issubset(real), (
            f"real {event_type} sample missing common keys: {common_keys - set(real)}"
        )
        assert set(synthetic).issubset(set(real)), (
            f"synthetic {event_type} has unexpected top-level keys: {set(synthetic) - set(real)}"
        )

        if event_type in {"net_connect", "net_send"}:
            assert isinstance(synthetic.get("net"), dict)
            assert set(synthetic["net"]).issubset(set(real.get("net", {})))
        if event_type in {"dns_query", "dns_response"}:
            assert isinstance(synthetic.get("dns"), dict)
            assert set(synthetic["dns"]).issubset(set(real.get("dns", {})))
        if event_type == "unix_connect":
            assert isinstance(synthetic.get("unix"), dict)
            assert set(synthetic["unix"]).issubset(set(real.get("unix", {})))
