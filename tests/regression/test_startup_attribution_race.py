from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.regression


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return None
    return details.get("path")


def _row_is_fs_for_path(row: dict, path: str) -> bool:
    event_type = str(row.get("event_type") or "")
    return event_type.startswith("fs_") and _details_path(row) == path


def test_regression_startup_attribution_race_concurrent_timeout_jobs(
    regression_stack,
    timeline_validator,
) -> None:
    """
    Concurrent startup with `timeout` as the run root must not leave early fs rows
    as unknown/cross-attributed before run ownership metadata converges.
    """
    path_one = f"/work/startup_race_one_{uuid.uuid4().hex[:8]}.txt"
    path_two = f"/work/startup_race_two_{uuid.uuid4().hex[:8]}.txt"

    prompt_one = f"printf one > {path_one}; sleep 0.25; printf one_more >> {path_one}; sleep 0.5"
    prompt_two = f"printf two > {path_two}; sleep 0.25; printf two_more >> {path_two}; sleep 0.5"

    # timeout_sec ensures the harness wraps commands with `timeout`, which is an owned root_comm
    # and exercises startup ownership mapping under concurrent pressure.
    job_one = regression_stack.submit_job(prompt_one, timeout_sec=120)
    job_two = regression_stack.submit_job(prompt_two, timeout_sec=120)

    status_one = regression_stack.wait_for_job(job_one)
    status_two = regression_stack.wait_for_job(job_two)
    assert status_one["status"] == "complete", f"job_one failed: {status_one}"
    assert status_two["status"] == "complete", f"job_two failed: {status_two}"

    rows = regression_stack.wait_for_timeline_rows(
        lambda timeline_rows: (
            any(_row_is_fs_for_path(row, path_one) for row in timeline_rows)
            and any(_row_is_fs_for_path(row, path_two) for row in timeline_rows)
        ),
        timeout_sec=120,
        message="startup-race regression scenario missing expected fs rows",
    )

    rows_one = [row for row in rows if _row_is_fs_for_path(row, path_one)]
    rows_two = [row for row in rows if _row_is_fs_for_path(row, path_two)]
    assert rows_one, f"Missing fs rows for job_one path={path_one}"
    assert rows_two, f"Missing fs rows for job_two path={path_two}"

    wrong_one = [row for row in rows_one if row.get("job_id") != job_one]
    wrong_two = [row for row in rows_two if row.get("job_id") != job_two]
    assert not wrong_one, f"job_one startup rows misattributed: {wrong_one}"
    assert not wrong_two, f"job_two startup rows misattributed: {wrong_two}"

    timeline_validator(log_root=regression_stack.run_root)
