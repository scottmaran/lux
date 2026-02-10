from __future__ import annotations

import os
import shutil
import uuid

import pytest

from tests.support.synthetic_logs import build_job_fs_sequence


pytestmark = pytest.mark.stress


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    return details.get("path")


def _trial_count() -> int:
    raw = os.getenv("LASSO_STRESS_TRIALS", "3").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise AssertionError(f"Invalid LASSO_STRESS_TRIALS={raw}") from exc
    if value < 1:
        raise AssertionError("LASSO_STRESS_TRIALS must be >= 1")
    return value


def test_repeated_concurrent_job_trials_avoid_cross_attribution(
    stress_stack,
    timeline_validator,
) -> None:
    """Repeated concurrent job trials never cross-attribute fs events between jobs."""
    trials = _trial_count()
    for trial in range(trials):
        path_a = f"/work/stress_a_{trial}_{uuid.uuid4().hex[:8]}.txt"
        path_b = f"/work/stress_b_{trial}_{uuid.uuid4().hex[:8]}.txt"
        job_a = stress_stack.submit_job(f"sleep 1; printf a > {path_a}")
        job_b = stress_stack.submit_job(f"sleep 1; printf b > {path_b}")
        status_a = stress_stack.wait_for_job(job_a)
        status_b = stress_stack.wait_for_job(job_b)
        assert status_a["status"] == "complete", f"trial={trial} job_a failed: {status_a}"
        assert status_b["status"] == "complete", f"trial={trial} job_b failed: {status_b}"

        jobs_dir = stress_stack.log_root / "jobs"
        for entry in jobs_dir.iterdir():
            if not entry.is_dir():
                continue
            if entry.name not in {job_a, job_b}:
                shutil.rmtree(entry, ignore_errors=True)

        root_a = stress_stack.read_json(stress_stack.log_root / "jobs" / job_a / "input.json")["root_pid"]
        root_b = stress_stack.read_json(stress_stack.log_root / "jobs" / job_b / "input.json")["root_pid"]
        assert isinstance(root_a, int)
        assert isinstance(root_b, int)
        child_a = root_a * 1000 + trial * 10 + 1
        child_b = root_b * 1000 + trial * 10 + 2

        audit_lines = []
        audit_lines.extend(
            build_job_fs_sequence(
                root_pid=root_a,
                child_pid=child_a,
                target_path=path_a,
                seq_start=1000 + trial * 20,
                ts_root="1769030400.100",
                ts_child="1769030400.120",
                ts_fs="1769030400.210",
            )
        )
        audit_lines.extend(
            build_job_fs_sequence(
                root_pid=root_b,
                child_pid=child_b,
                target_path=path_b,
                seq_start=1010 + trial * 20,
                ts_root="1769030400.101",
                ts_child="1769030400.121",
                ts_fs="1769030400.220",
            )
        )
        rows = stress_stack.run_collector_pipeline(audit_lines=audit_lines)["timeline"]
        assert any(_details_path(row) == path_a and row.get("job_id") == job_a for row in rows)
        assert any(_details_path(row) == path_b and row.get("job_id") == job_b for row in rows)

        wrong_a = [
            row
            for row in rows
            if _details_path(row) == path_a and row.get("job_id") != job_a
        ]
        wrong_b = [
            row
            for row in rows
            if _details_path(row) == path_b and row.get("job_id") != job_b
        ]
        assert not wrong_a, f"trial={trial} path_a cross-attribution: {wrong_a}"
        assert not wrong_b, f"trial={trial} path_b cross-attribution: {wrong_b}"

    timeline_validator(
        log_root=stress_stack.log_root,
        timeline_path=stress_stack.log_root / "filtered_timeline.synthetic.jsonl",
    )
