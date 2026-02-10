from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.module_loader import load_module


AUDIT_MODULE = load_module(
    "filter_audit_logs",
    Path(__file__).resolve().parents[2] / "collector" / "scripts" / "filter_audit_logs.py",
)


@pytest.mark.unit
def test_parse_line_extracts_seq_timestamp_and_fields() -> None:
    """Audit parser extracts sequence, timestamp, and fields from syscall lines."""
    line = (
        'type=SYSCALL msg=audit(1767225600.123:77): arch=c00000b7 syscall=221 success=yes '
        'exit=0 pid=10 ppid=1 uid=1001 gid=1001 comm="bash" exe="/usr/bin/bash" key="exec"'
    )
    parsed = AUDIT_MODULE.parse_line(line)
    assert parsed is not None
    assert parsed["seq"] == 77
    assert parsed["ts_iso"] == "2026-01-01T00:00:00.123Z"
    assert parsed["fields"]["comm"] == "bash"


@pytest.mark.unit
def test_decode_execve_arg_decodes_hex_utf8() -> None:
    """Hex-encoded argv payloads decode to printable utf-8 when possible."""
    value = "707974686f6e33202d63207072696e74283129"
    assert AUDIT_MODULE.decode_execve_arg(value) == "python3 -c print(1)"


@pytest.mark.unit
def test_derive_cmd_prefers_shell_lc_inner_command() -> None:
    """Shell `-lc` argv expands to the wrapped inner command for attribution."""
    argv = ["bash", "-lc", "printf test > /work/a.txt"]
    cmd = AUDIT_MODULE.derive_cmd(argv, "bash", {"bash", "sh"}, "-lc")
    assert cmd == "printf test > /work/a.txt"


@pytest.mark.unit
def test_select_path_prefers_specific_nametype_and_falls_back() -> None:
    """Path selection honors preferred nametype then falls back to first non-parent entry."""
    records = [
        {"name": "/work", "nametype": "PARENT"},
        {"name": "/work/new.txt", "nametype": "CREATE"},
    ]
    assert AUDIT_MODULE.select_path(records, "CREATE") == "/work/new.txt"
    assert AUDIT_MODULE.select_path(records, None) == "/work/new.txt"


@pytest.mark.unit
def test_derive_fs_event_type_maps_nametypes_and_key() -> None:
    """Filesystem event type mapping is deterministic from nametype and key context."""
    assert AUDIT_MODULE.derive_fs_event_type("fs_watch", {"CREATE"}) == "fs_create"
    assert AUDIT_MODULE.derive_fs_event_type("fs_watch", {"DELETE"}) == "fs_unlink"
    assert AUDIT_MODULE.derive_fs_event_type("fs_meta", {"NORMAL"}) == "fs_meta"
