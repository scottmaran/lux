from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest

from tests.support import synthetic_logs


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_AUDIT = REPO_ROOT / "example_logs" / "audit.log"
EXAMPLE_EBPF = REPO_ROOT / "example_logs" / "ebpf.jsonl"


def _read_ebpf_rows() -> list[dict]:
    rows: list[dict] = []
    with EXAMPLE_EBPF.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _first_by_event_type(rows: list[dict], event_type: str) -> dict | None:
    for row in rows:
        if row.get("event_type") == event_type:
            return row
    return None


def _audit_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in shlex.split(line):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def _first_audit_line_by_type(record_type: str) -> str | None:
    with EXAMPLE_AUDIT.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(f"type={record_type} "):
                return line.strip()
    return None


@pytest.mark.unit
def test_synthetic_builders_cover_required_ebpf_event_types() -> None:
    """Synthetic builder module emits all required eBPF event categories."""
    events = [
        synthetic_logs.ebpf_net_connect(),
        synthetic_logs.ebpf_net_send(),
        synthetic_logs.ebpf_dns_query(),
        synthetic_logs.ebpf_dns_response(),
        synthetic_logs.ebpf_unix_connect(),
    ]
    event_types = {event["event_type"] for event in events}
    assert event_types == {
        "net_connect",
        "net_send",
        "dns_query",
        "dns_response",
        "unix_connect",
    }


@pytest.mark.unit
def test_synthetic_ebpf_shape_matches_real_reference_after_normalization() -> None:
    """Synthetic eBPF records match real reference shape after volatile-field normalization."""
    real_rows = _read_ebpf_rows()

    synthetic_by_type = {
        "net_connect": synthetic_logs.ebpf_net_connect(),
        "net_send": synthetic_logs.ebpf_net_send(),
        "dns_query": synthetic_logs.ebpf_dns_query(),
        "dns_response": synthetic_logs.ebpf_dns_response(),
        "unix_connect": synthetic_logs.ebpf_unix_connect(),
    }

    for event_type, synthetic_row in synthetic_by_type.items():
        real_row = _first_by_event_type(real_rows, event_type)
        assert real_row is not None, f"missing real reference row for {event_type}"

        # Volatile fields are compared by type/key presence, not value equality.
        assert set(synthetic_row.keys()) == set(real_row.keys())

        if event_type in {"net_connect", "net_send"}:
            assert set(synthetic_row["net"].keys()) == set(real_row["net"].keys())
        if event_type in {"dns_query", "dns_response"}:
            assert set(synthetic_row["dns"].keys()) == set(real_row["dns"].keys())
        if event_type == "unix_connect":
            assert set(synthetic_row["unix"].keys()) == set(real_row["unix"].keys())


@pytest.mark.unit
def test_synthetic_audit_shape_matches_real_reference_after_normalization() -> None:
    """Synthetic raw audit lines include the same structural keys as real audit records."""
    real_syscall = _first_audit_line_by_type("SYSCALL")
    real_execve = _first_audit_line_by_type("EXECVE")
    real_cwd = _first_audit_line_by_type("CWD")
    real_path = _first_audit_line_by_type("PATH")

    assert real_syscall and real_execve and real_cwd and real_path

    synthetic_syscall = synthetic_logs.audit_syscall_line(
        ts_sec=1767225600,
        seq=1,
        pid=10,
        ppid=1,
        uid=1001,
        gid=1001,
        comm="bash",
        exe="/usr/bin/bash",
        key="exec",
    )
    synthetic_execve = synthetic_logs.audit_execve_line(ts_sec=1767225600, seq=1, argv=["bash", "-lc", "pwd"])
    synthetic_cwd = synthetic_logs.audit_cwd_line(ts_sec=1767225600, seq=1, cwd="/work")
    synthetic_path = synthetic_logs.audit_path_line(
        ts_sec=1767225600,
        seq=1,
        name="/work/a.txt",
        nametype="CREATE",
    )

    syscall_keys = set(_audit_fields(synthetic_syscall))
    assert syscall_keys <= set(_audit_fields(real_syscall))

    execve_keys = set(_audit_fields(synthetic_execve))
    assert execve_keys <= set(_audit_fields(real_execve))

    cwd_keys = set(_audit_fields(synthetic_cwd))
    assert cwd_keys <= set(_audit_fields(real_cwd))

    path_keys = set(_audit_fields(synthetic_path))
    assert path_keys <= set(_audit_fields(real_path))
