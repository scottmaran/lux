from __future__ import annotations

import uuid

import pytest

from tests.support.synthetic_logs import build_job_fs_sequence


pytestmark = pytest.mark.integration


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    return details.get("path")


def test_concurrent_jobs_do_not_cross_attribute_events(
    integration_stack,
    timeline_validator,
) -> None:
    """Concurrent runs keep fs_* events attributed only to the originating job."""
    path_one = f"/work/concurrent_one_{uuid.uuid4().hex[:8]}.txt"
    path_two = f"/work/concurrent_two_{uuid.uuid4().hex[:8]}.txt"

    job_one = integration_stack.submit_job(f"sleep 2; printf one > {path_one}")
    job_two = integration_stack.submit_job(f"sleep 2; printf two > {path_two}")
    status_one = integration_stack.wait_for_job(job_one)
    status_two = integration_stack.wait_for_job(job_two)
    assert status_one["status"] == "complete"
    assert status_two["status"] == "complete"

    root_one = integration_stack.read_json(integration_stack.log_root / "jobs" / job_one / "input.json")["root_pid"]
    root_two = integration_stack.read_json(integration_stack.log_root / "jobs" / job_two / "input.json")["root_pid"]
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
            seq_start=200,
            ts_root="1769030400.100",
            ts_child="1769030400.120",
            ts_fs="1769030400.210",
        )
    )
    audit_lines.extend(
        build_job_fs_sequence(
            root_pid=root_two,
            child_pid=child_two,
            target_path=path_two,
            seq_start=300,
            ts_root="1769030400.105",
            ts_child="1769030400.125",
            ts_fs="1769030400.220",
        )
    )
    rows = integration_stack.run_collector_pipeline(audit_lines=audit_lines)["timeline"]
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
    assert not wrong_one, f"path_one cross-attributed rows: {wrong_one}"
    assert not wrong_two, f"path_two cross-attributed rows: {wrong_two}"
    timeline_validator(
        log_root=integration_stack.log_root,
        timeline_path=integration_stack.log_root / "filtered_timeline.synthetic.jsonl",
    )
