from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import validate_timeline_outputs


pytestmark = pytest.mark.unit


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_timeline_validator_accepts_valid_minimal_job_owned_timeline(tmp_path: Path) -> None:
    """Validator accepts timeline rows with valid job ownership and metadata references."""
    log_root = tmp_path / "logs"
    _write(
        log_root / "harness" / "jobs" / "job_1" / "input.json",
        {"job_id": "job_1", "root_pid": 100},
    )
    _write(
        log_root / "harness" / "jobs" / "job_1" / "status.json",
        {"job_id": "job_1", "root_pid": 100},
    )
    timeline = log_root / "collector" / "filtered" / "filtered_timeline.jsonl"
    timeline.parent.mkdir(parents=True, exist_ok=True)
    timeline.write_text(
        json.dumps(
            {
                "schema_version": "timeline.filtered.v1",
                "session_id": "unknown",
                "job_id": "job_1",
                "ts": "2026-01-22T00:00:01.000Z",
                "source": "audit",
                "event_type": "exec",
                "details": {"cmd": "pwd"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = validate_timeline_outputs(log_root=log_root, timeline_path=timeline)
    assert len(rows) == 1


def test_timeline_validator_rejects_missing_owner(tmp_path: Path) -> None:
    """Validator rejects rows that do not provide a valid ownership shape."""
    log_root = tmp_path / "logs"
    timeline = log_root / "collector" / "filtered" / "filtered_timeline.jsonl"
    timeline.parent.mkdir(parents=True, exist_ok=True)
    timeline.write_text(
        json.dumps(
            {
                "schema_version": "timeline.filtered.v1",
                "session_id": "unknown",
                "ts": "2026-01-22T00:00:01.000Z",
                "source": "audit",
                "event_type": "exec",
                "details": {"cmd": "pwd"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="unknown session without job owner"):
        validate_timeline_outputs(log_root=log_root, timeline_path=timeline)
