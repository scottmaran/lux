from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.integration


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return None
    return details.get("path")


def test_live_concurrent_jobs_do_not_cross_attribute_events(
    integration_stack,
    timeline_validator,
) -> None:
    """Concurrent live runs keep filesystem rows attributed only to originating job IDs."""
    path_one = f"/work/concurrent_one_{uuid.uuid4().hex[:8]}.txt"
    path_two = f"/work/concurrent_two_{uuid.uuid4().hex[:8]}.txt"

    job_one = integration_stack.submit_job(f"sleep 1; printf one > {path_one}")
    job_two = integration_stack.submit_job(f"sleep 1; printf two > {path_two}")

    status_one = integration_stack.wait_for_job(job_one)
    status_two = integration_stack.wait_for_job(job_two)
    assert status_one["status"] == "complete", f"job_one failed: {status_one}"
    assert status_two["status"] == "complete", f"job_two failed: {status_two}"

    rows = integration_stack.wait_for_timeline_rows(
        lambda timeline_rows: (
            any(_details_path(row) == path_one and row.get("job_id") == job_one for row in timeline_rows)
            and any(_details_path(row) == path_two and row.get("job_id") == job_two for row in timeline_rows)
        ),
        timeout_sec=120,
        message="concurrent jobs missing expected timeline rows",
    )

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

    timeline_validator(log_root=integration_stack.log_root)
