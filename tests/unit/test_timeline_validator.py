from __future__ import annotations

import pytest

from tests.conftest import assert_timeline_invariants


@pytest.mark.unit
def test_timeline_validator_accepts_valid_rows() -> None:
    """Validator accepts ordered rows with valid ownership and referenced metadata."""
    rows = [
        {
            "schema_version": "timeline.filtered.v1",
            "session_id": "unknown",
            "job_id": "job_1",
            "ts": "2026-01-01T00:00:00.100Z",
            "source": "audit",
            "event_type": "exec",
            "details": {"cmd": "pwd"},
        },
        {
            "schema_version": "timeline.filtered.v1",
            "session_id": "session_1",
            "ts": "2026-01-01T00:00:00.200Z",
            "source": "audit",
            "event_type": "fs_create",
            "details": {"path": "/work/a.txt"},
        },
    ]
    sessions = {"session_1": {"session_id": "session_1", "ended_at": "2026-01-01T00:00:01Z", "root_pid": 123}}
    jobs = {"job_1": {"job_id": "job_1", "ended_at": "2026-01-01T00:00:01Z", "root_pid": 456}}
    assert_timeline_invariants(rows, sessions, jobs)


@pytest.mark.unit
def test_timeline_validator_rejects_missing_root_pid_for_completed_run() -> None:
    """Validator fails when completed referenced runs omit required root_pid."""
    rows = [
        {
            "schema_version": "timeline.filtered.v1",
            "session_id": "unknown",
            "job_id": "job_2",
            "ts": "2026-01-01T00:00:00.100Z",
            "source": "audit",
            "event_type": "exec",
            "details": {"cmd": "pwd"},
        }
    ]
    jobs = {"job_2": {"job_id": "job_2", "ended_at": "2026-01-01T00:00:02Z", "root_pid": None}}
    with pytest.raises(AssertionError, match="missing integer root_pid"):
        assert_timeline_invariants(rows, {}, jobs)


@pytest.mark.unit
def test_timeline_validator_rejects_ambiguous_ownership() -> None:
    """Validator fails rows that set both concrete session and job ownership."""
    rows = [
        {
            "schema_version": "timeline.filtered.v1",
            "session_id": "session_2",
            "job_id": "job_2",
            "ts": "2026-01-01T00:00:00.100Z",
            "source": "audit",
            "event_type": "exec",
            "details": {"cmd": "pwd"},
        }
    ]
    with pytest.raises(AssertionError, match="exactly one owner"):
        assert_timeline_invariants(
            rows,
            {"session_2": {"session_id": "session_2", "root_pid": 123}},
            {"job_2": {"job_id": "job_2", "root_pid": 456}},
        )
