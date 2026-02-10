from __future__ import annotations

import datetime as dt
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from tests.support.live_stack import LiveStack, StackConfig


def _parse_ts(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    raw = value.rstrip("Z")
    if "." in raw:
        base, frac = raw.split(".", 1)
        raw = f"{base}.{(frac + '000000')[:6]}"
    try:
        return dt.datetime.fromisoformat(raw).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _has_non_unknown_session(event: dict) -> bool:
    session_id = event.get("session_id")
    return isinstance(session_id, str) and session_id not in {"", "unknown"}


def _has_job(event: dict) -> bool:
    return bool(event.get("job_id"))


def attributed_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if _has_non_unknown_session(row) or _has_job(row)]


def _require_fields(event: dict, required: list[str], errors: list[str], idx: int) -> None:
    for field in required:
        current = event
        parts = field.split(".")
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                errors.append(f"row {idx}: missing required field '{field}'")
                break
            current = current.get(part)


def assert_timeline_invariants(
    rows: list[dict],
    sessions_meta: dict[str, dict],
    jobs_meta: dict[str, dict],
) -> None:
    errors: list[str] = []

    prev_ts: dt.datetime | None = None
    required_base = ["schema_version", "session_id", "ts", "source", "event_type"]
    event_requirements = {
        "exec": ["details.cmd"],
        "fs_create": ["details.path"],
        "fs_write": ["details.path"],
        "fs_unlink": ["details.path"],
        "fs_rename": ["details.path"],
        "fs_meta": ["details.path"],
        "net_summary": ["details.dst_ip", "details.dst_port", "details.send_count", "details.bytes_sent_total"],
        "unix_connect": ["details.unix"],
    }

    referenced_sessions: set[str] = set()
    referenced_jobs: set[str] = set()

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {idx}: expected object, got {type(row)!r}")
            continue

        has_session = _has_non_unknown_session(row)
        has_job = _has_job(row)
        if has_session == has_job:
            errors.append(
                "row {}: ownership must reference exactly one owner (session_id != unknown XOR job_id)".format(
                    idx
                )
            )

        session_id = row.get("session_id")
        if has_session:
            if session_id not in sessions_meta:
                errors.append(f"row {idx}: unknown session_id '{session_id}'")
            else:
                referenced_sessions.add(str(session_id))

        job_id = row.get("job_id")
        if has_job:
            if job_id not in jobs_meta:
                errors.append(f"row {idx}: unknown job_id '{job_id}'")
            else:
                referenced_jobs.add(str(job_id))

        _require_fields(row, required_base, errors, idx)

        event_type = row.get("event_type")
        if isinstance(event_type, str):
            _require_fields(row, event_requirements.get(event_type, []), errors, idx)

        ts_value = _parse_ts(row.get("ts"))
        if ts_value is None:
            errors.append(f"row {idx}: invalid ts value '{row.get('ts')}'")
        elif prev_ts is not None and ts_value < prev_ts:
            errors.append(
                f"row {idx}: timeline ordering violation ({row.get('ts')} < {prev_ts.isoformat()})"
            )
        else:
            prev_ts = ts_value

    for session_id in referenced_sessions:
        meta = sessions_meta.get(session_id, {})
        ended_at = meta.get("ended_at")
        if ended_at and not isinstance(meta.get("root_pid"), int):
            errors.append(f"session '{session_id}' is completed but missing integer root_pid")

    for job_id in referenced_jobs:
        meta = jobs_meta.get(job_id, {})
        ended_at = meta.get("ended_at")
        if ended_at and not isinstance(meta.get("root_pid"), int):
            errors.append(f"job '{job_id}' is completed but missing integer root_pid")

    if errors:
        joined = "\n".join(f"- {item}" for item in errors)
        raise AssertionError(f"timeline invariants failed:\n{joined}")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _docker_ready() -> bool:
    result = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    return result.returncode == 0


def pytest_runtest_setup(item: pytest.Item) -> None:
    live_markers = {"integration", "stress", "regression", "agent_codex_exec", "agent_codex_tui"}
    if any(item.get_closest_marker(name) for name in live_markers):
        if not _docker_ready():
            pytest.skip("docker daemon is unavailable; live stack tests cannot run")


@pytest.fixture
def live_stack_factory(repo_root: Path, tmp_path: Path):
    stacks: list[LiveStack] = []

    def _create(
        *,
        run_cmd_template: str,
        ownership_root_comm: list[str],
        include_codex_mount: bool = False,
        lasso_version: str | None = None,
    ) -> LiveStack:
        stack_dir = tmp_path / f"stack_{uuid.uuid4().hex[:8]}"
        stack_dir.mkdir(parents=True, exist_ok=True)
        stack = LiveStack(
            repo_root=repo_root,
            base_dir=stack_dir,
            config=StackConfig(
                run_cmd_template=run_cmd_template,
                ownership_root_comm=ownership_root_comm,
                include_codex_mount=include_codex_mount,
                lasso_version=lasso_version or os.getenv("LASSO_VERSION", "v0.1.4"),
                api_token=os.getenv("HARNESS_API_TOKEN", "dev-token"),
            ),
        )
        stack.start()
        stacks.append(stack)
        return stack

    yield _create

    for stack in reversed(stacks):
        stack.stop()
