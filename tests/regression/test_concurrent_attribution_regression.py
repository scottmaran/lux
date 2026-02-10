from __future__ import annotations

import uuid

import pytest

from tests.support.synthetic_logs import build_job_fs_sequence


pytestmark = pytest.mark.regression


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    return details.get("path")


def test_regression_dcf5673_concurrent_runs_do_not_leak_event_ownership(
    regression_stack,
    timeline_validator,
) -> None:
    """Fixed in dcf5673: concurrent runs must not cross-attribute fs events by time window."""
    path_one = f"/work/regression_one_{uuid.uuid4().hex[:8]}.txt"
    path_two = f"/work/regression_two_{uuid.uuid4().hex[:8]}.txt"

    job_one = regression_stack.submit_job(f"sleep 2; printf one > {path_one}")
    job_two = regression_stack.submit_job(f"sleep 2; printf two > {path_two}")
    status_one = regression_stack.wait_for_job(job_one)
    status_two = regression_stack.wait_for_job(job_two)
    assert status_one["status"] == "complete"
    assert status_two["status"] == "complete"

    root_one = regression_stack.read_json(regression_stack.log_root / "jobs" / job_one / "input.json")["root_pid"]
    root_two = regression_stack.read_json(regression_stack.log_root / "jobs" / job_two / "input.json")["root_pid"]
    assert isinstance(root_one, int)
    assert isinstance(root_two, int)
    child_one = root_one * 1000 + 1
    child_two = root_two * 1000 + 2

    audit_lines = []
    audit_lines.extend(
        build_job_fs_sequence(
            root_pid=root_one,
            child_pid=child_one,
            target_path=path_one,
            seq_start=400,
            ts_root="1769030400.100",
            ts_child="1769030400.120",
            ts_fs="1769030400.220",
        )
    )
    audit_lines.extend(
        build_job_fs_sequence(
            root_pid=root_two,
            child_pid=child_two,
            target_path=path_two,
            seq_start=500,
            ts_root="1769030400.101",
            ts_child="1769030400.121",
            ts_fs="1769030400.221",
        )
    )
    rows = regression_stack.run_collector_pipeline(audit_lines=audit_lines)["timeline"]
    assert any(_details_path(row) == path_one and row.get("job_id") == job_one for row in rows)
    assert any(_details_path(row) == path_two and row.get("job_id") == job_two for row in rows)

    wrong_one = [
        row
        for row in rows
        if _details_path(row) == path_one and row.get("job_id") != job_one
    ]
    wrong_two = [
        row
        for row in rows
        if _details_path(row) == path_two and row.get("job_id") != job_two
    ]
    assert not wrong_one, f"cross-attributed rows for job_one: {wrong_one}"
    assert not wrong_two, f"cross-attributed rows for job_two: {wrong_two}"
    timeline_validator(
        log_root=regression_stack.log_root,
        timeline_path=regression_stack.log_root / "filtered_timeline.synthetic.jsonl",
    )
