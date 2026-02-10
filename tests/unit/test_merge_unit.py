from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.module_loader import load_module


MERGE_MODULE = load_module(
    "merge_filtered_logs",
    Path(__file__).resolve().parents[2] / "collector" / "scripts" / "merge_filtered_logs.py",
)


@pytest.mark.unit
def test_normalize_event_moves_source_specific_fields_into_details() -> None:
    """Merge normalization preserves common keys and nests source-specific values under details."""
    event = {
        "schema_version": "auditd.filtered.v1",
        "session_id": "session_1",
        "ts": "2026-01-01T00:00:00.000Z",
        "source": "audit",
        "event_type": "exec",
        "pid": 100,
        "cmd": "pwd",
        "cwd": "/work",
    }
    normalized = MERGE_MODULE.normalize_event(event, "audit", "timeline.filtered.v1")
    assert normalized["schema_version"] == "timeline.filtered.v1"
    assert normalized["source"] == "audit"
    assert normalized["pid"] == 100
    assert normalized["details"]["cmd"] == "pwd"
    assert normalized["details"]["cwd"] == "/work"


@pytest.mark.unit
def test_parse_ts_rejects_invalid_values() -> None:
    """Timestamp parser returns None for malformed timeline timestamps."""
    assert MERGE_MODULE.parse_ts("not-a-timestamp") is None


@pytest.mark.unit
def test_parse_ts_normalizes_subsecond_precision() -> None:
    """Timestamp parser accepts RFC3339 timestamps with nanosecond precision."""
    parsed = MERGE_MODULE.parse_ts("2026-01-01T00:00:00.123456789Z")
    assert parsed is not None
    assert parsed.microsecond == 123456
