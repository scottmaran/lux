from __future__ import annotations

"""
Shared pytest utilities for the full test suite.

This module:
- registers shared pytest plugins used across test layers,
- provides helpers to read/parse JSON and JSONL test artifacts,
- loads session/job ownership metadata from harness log outputs, and
- exposes a single timeline validator fixture used by integration,
  regression, and stress tests.
"""

import json
from pathlib import Path
from typing import Any

import pytest

pytest_plugins = ["tests.support.pytest_docker"]


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_ts(value: str | None) -> tuple[int, int]:
    """
    Normalize timeline timestamp strings into a sortable tuple.

    The validator compares adjacent timeline rows and must do that without
    relying on string ordering quirks. This helper accepts RFC3339-like values
    (including `Z` and optional fractional seconds), strips timezone suffixes
    after normalizing UTC `Z`, and returns `(date_clock_key, microseconds)` so
    `validate_timeline_outputs` can enforce non-decreasing event order.
    """
    if not value:
        raise AssertionError("Missing timestamp value.")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    date_part, time_part = normalized.split("T", 1)
    day = int(date_part.replace("-", ""))
    if "+" in time_part:
        time_part = time_part.split("+", 1)[0]
    if "." in time_part:
        clock, frac = time_part.split(".", 1)
        frac = (frac + "000000")[:6]
    else:
        clock = time_part
        frac = "000000"
    hh, mm, ss = [int(piece) for piece in clock.split(":")]
    micros = int(frac)
    return (day * 100000000 + hh * 10000 + mm * 100 + ss, micros)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Invalid JSON at {path}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"Invalid JSONL row in {path}: {line}") from exc
    return rows


def load_sessions(log_root: Path) -> dict[str, dict[str, Any]]:
    sessions_dir = log_root / "harness" / "sessions"
    if not sessions_dir.exists():
        sessions_dir = log_root / "sessions"
    session_map: dict[str, dict[str, Any]] = {}
    if not sessions_dir.exists():
        return session_map
    for entry in sessions_dir.iterdir():
        if not entry.is_dir():
            continue
        meta = read_json(entry / "meta.json")
        if not isinstance(meta, dict):
            continue
        session_id = str(meta.get("session_id") or entry.name)
        session_map[session_id] = meta
    return session_map


def load_jobs(log_root: Path) -> dict[str, dict[str, Any]]:
    jobs_dir = log_root / "harness" / "jobs"
    if not jobs_dir.exists():
        jobs_dir = log_root / "jobs"
    job_map: dict[str, dict[str, Any]] = {}
    if not jobs_dir.exists():
        return job_map
    for entry in jobs_dir.iterdir():
        if not entry.is_dir():
            continue
        input_meta = read_json(entry / "input.json") or {}
        status_meta = read_json(entry / "status.json") or {}
        job_id = str(input_meta.get("job_id") or status_meta.get("job_id") or entry.name)
        job_map[job_id] = {
            "input": input_meta,
            "status": status_meta,
        }
    return job_map


def validate_timeline_outputs(
    *,
    log_root: Path,
    timeline_path: Path | None = None,
    require_rows: bool = True,
) -> list[dict[str, Any]]:
    """
    A passing timeline must satisfy all of the following:
    - at least one JSONL row exists (unless `require_rows=False`),
    - each row has required envelope keys and a dict `details` payload,
    - rows are timestamp-ordered,
    - ownership is valid and exclusive:
      - session-owned rows (`session_id != "unknown"`) must not also set `job_id`,
      - job-owned rows (`session_id == "unknown"`) must set a known `job_id`,
    - referenced session/job IDs exist in on-disk metadata,
    - event-specific required details are present (`fs_*`, `exec`, `net_summary`),
    - every referenced session/job includes integer `root_pid` metadata.
    """
    if timeline_path is not None:
        timeline = timeline_path
    else:
        timeline = log_root / "collector" / "filtered" / "filtered_timeline.jsonl"
        if not timeline.exists():
            timeline = log_root / "filtered_timeline.jsonl"
    rows = read_jsonl(timeline)
    if require_rows and not rows:
        raise AssertionError(f"Timeline is empty: {timeline}")

    sessions = load_sessions(log_root)
    jobs = load_jobs(log_root)

    required_common = {"schema_version", "session_id", "ts", "source", "event_type", "details"}
    previous_ts: tuple[int, int] | None = None
    referenced_sessions: set[str] = set()
    referenced_jobs: set[str] = set()

    for index, row in enumerate(rows):
        missing = required_common - set(row.keys())
        if missing:
            raise AssertionError(f"Row {index} missing required fields: {sorted(missing)}")

        if not isinstance(row.get("details"), dict):
            raise AssertionError(f"Row {index} has non-dict details payload.")

        ts_key = parse_ts(str(row["ts"]))
        if previous_ts and ts_key < previous_ts:
            raise AssertionError(f"Timeline out of order at row {index}: {row['ts']}")
        previous_ts = ts_key

        session_id = row.get("session_id")
        job_id = row.get("job_id")
        if session_id != "unknown":
            if job_id is not None:
                raise AssertionError(f"Row {index} has both session and job owners: {row}")
            if session_id not in sessions:
                raise AssertionError(f"Row {index} references missing session_id={session_id}")
            referenced_sessions.add(str(session_id))
        else:
            if not job_id:
                raise AssertionError(f"Row {index} has unknown session without job owner.")
            if str(job_id) not in jobs:
                raise AssertionError(f"Row {index} references missing job_id={job_id}")
            referenced_jobs.add(str(job_id))

        event_type = str(row.get("event_type"))
        details = row.get("details", {})
        if event_type.startswith("fs_") and not details.get("path"):
            raise AssertionError(f"Row {index} fs event missing details.path: {row}")
        if event_type == "exec" and not details.get("cmd"):
            raise AssertionError(f"Row {index} exec event missing details.cmd: {row}")
        if event_type == "net_summary":
            needed = {"dst_ip", "dst_port", "send_count", "bytes_sent_total", "ts_first", "ts_last"}
            missing_net = needed - set(details.keys())
            if missing_net:
                raise AssertionError(
                    f"Row {index} net_summary missing keys {sorted(missing_net)}: {row}"
                )

    for session_id in sorted(referenced_sessions):
        root_pid = sessions.get(session_id, {}).get("root_pid")
        if not isinstance(root_pid, int):
            raise AssertionError(f"Session {session_id} is missing integer root_pid.")

    for job_id in sorted(referenced_jobs):
        payload = jobs.get(job_id, {})
        input_pid = payload.get("input", {}).get("root_pid")
        status_pid = payload.get("status", {}).get("root_pid")
        if not isinstance(input_pid, int) or not isinstance(status_pid, int):
            raise AssertionError(
                f"Job {job_id} is missing integer root_pid in input.json and/or status.json."
            )

    return rows


@pytest.fixture
def timeline_validator():
    """Returns the shared timeline validator function."""
    return validate_timeline_outputs
