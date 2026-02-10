from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.regression


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return None
    return details.get("path")


def test_regression_dcf5673_concurrent_runs_do_not_leak_event_ownership(
    regression_stack,
    timeline_validator,
) -> None:
    """Fixed in dcf5673: concurrent live runs must not cross-attribute fs rows by time window."""
    path_one = f"/work/regression_one_{uuid.uuid4().hex[:8]}.txt"
    path_two = f"/work/regression_two_{uuid.uuid4().hex[:8]}.txt"

    prompt_one = f"printf one > {path_one}; sleep 0.5; printf one_more >> {path_one}"
    prompt_two = f"printf two > {path_two}; sleep 0.5; printf two_more >> {path_two}"

    job_one = regression_stack.submit_job(prompt_one, timeout_sec=240)
    job_two = regression_stack.submit_job(prompt_two, timeout_sec=240)

    status_one = regression_stack.wait_for_job(job_one)
    status_two = regression_stack.wait_for_job(job_two)
    assert status_one["status"] == "complete", f"job_one failed: {status_one}"
    assert status_two["status"] == "complete", f"job_two failed: {status_two}"

    rows = regression_stack.wait_for_timeline_rows(
        lambda timeline_rows: (
            any(_details_path(row) == path_one and row.get("job_id") == job_one for row in timeline_rows)
            and any(_details_path(row) == path_two and row.get("job_id") == job_two for row in timeline_rows)
        ),
        timeout_sec=120,
        message="regression scenario missing expected timeline rows",
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
    assert not wrong_one, f"cross-attributed rows for path_one: {wrong_one}"
    assert not wrong_two, f"cross-attributed rows for path_two: {wrong_two}"

    timeline_validator(log_root=regression_stack.log_root)
