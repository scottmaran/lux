from __future__ import annotations

import os
import uuid

import pytest


pytestmark = pytest.mark.stress


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return None
    return details.get("path")


def _row_mentions_path_in_cmd(row: dict, path: str) -> bool:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return False
    return path in str(details.get("cmd") or "")


def _trial_count() -> int:
    raw = os.getenv("LUX_STRESS_TRIALS", "3").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise AssertionError(f"Invalid LUX_STRESS_TRIALS={raw}") from exc
    if value < 1:
        raise AssertionError("LUX_STRESS_TRIALS must be >= 1")
    return value


def _row_is_fs_for_path(row: dict, path: str) -> bool:
    event_type = str(row.get("event_type") or "")
    return event_type.startswith("fs_") and _details_path(row) == path


def _run_trial(
    stress_stack,
    trial: int,
    *,
    ready_predicate=None,
) -> tuple[str, str, str, str, list[dict]]:
    path_a = f"/work/stress_a_{trial}_{uuid.uuid4().hex[:8]}.txt"
    path_b = f"/work/stress_b_{trial}_{uuid.uuid4().hex[:8]}.txt"

    prompt_a = f"sleep 0.5; printf a > {path_a}; sleep 0.5; printf a2 >> {path_a}"
    prompt_b = f"sleep 0.5; printf b > {path_b}; sleep 0.5; printf b2 >> {path_b}"

    job_a = stress_stack.submit_job(prompt_a, timeout_sec=240)
    job_b = stress_stack.submit_job(prompt_b, timeout_sec=240)

    status_a = stress_stack.wait_for_job(job_a)
    status_b = stress_stack.wait_for_job(job_b)
    assert status_a["status"] == "complete", f"trial={trial} job_a failed: {status_a}"
    assert status_b["status"] == "complete", f"trial={trial} job_b failed: {status_b}"

    rows = stress_stack.wait_for_timeline_rows(
        lambda timeline_rows: (
            any(_row_is_fs_for_path(row, path_a) for row in timeline_rows)
            and any(_row_is_fs_for_path(row, path_b) for row in timeline_rows)
            and (ready_predicate(timeline_rows, path_a, path_b) if ready_predicate else True)
        ),
        timeout_sec=120,
        message=f"trial={trial}: missing expected fs timeline rows",
    )
    return path_a, path_b, job_a, job_b, rows


def test_repeated_live_concurrent_trials_avoid_cross_attribution_fs_rows(
    stress_stack,
) -> None:
    """Repeated live concurrent trials never cross-attribute fs_* rows between jobs."""
    trials = _trial_count()

    for trial in range(trials):
        path_a, path_b, job_a, job_b, rows = _run_trial(stress_stack, trial)
        rows_a = [row for row in rows if _row_is_fs_for_path(row, path_a)]
        rows_b = [row for row in rows if _row_is_fs_for_path(row, path_b)]
        assert rows_a, f"trial={trial} path_a rows missing from timeline"
        assert rows_b, f"trial={trial} path_b rows missing from timeline"

        wrong_a = [
            row
            for row in rows_a
            if row.get("job_id") not in {None, job_a}
        ]
        wrong_b = [
            row
            for row in rows_b
            if row.get("job_id") not in {None, job_b}
        ]
        assert not wrong_a, f"trial={trial} path_a cross-attribution: {wrong_a}"
        assert not wrong_b, f"trial={trial} path_b cross-attribution: {wrong_b}"

        if any(row.get("job_id") is not None for row in rows_a):
            assert any(row.get("job_id") == job_a for row in rows_a), (
                f"trial={trial} path_a has labeled rows but none mapped to {job_a}"
            )
        if any(row.get("job_id") is not None for row in rows_b):
            assert any(row.get("job_id") == job_b for row in rows_b), (
                f"trial={trial} path_b has labeled rows but none mapped to {job_b}"
            )


def test_repeated_live_concurrent_trials_avoid_cross_attribution_wrapper_exec_rows(
    stress_stack,
) -> None:
    """
    Repeated live concurrent trials never cross-attribute exec wrapper rows
    whose command text contains path-specific prompts.
    """
    trials = _trial_count()

    def _wrapper_rows_ready(rows: list[dict], path_a: str, path_b: str) -> bool:
        return any(
            row.get("event_type") == "exec" and _row_mentions_path_in_cmd(row, path_a)
            for row in rows
        ) and any(
            row.get("event_type") == "exec" and _row_mentions_path_in_cmd(row, path_b)
            for row in rows
        )

    for trial in range(trials):
        path_a, path_b, job_a, job_b, rows = _run_trial(
            stress_stack,
            trial,
            ready_predicate=_wrapper_rows_ready,
        )
        rows_a = [
            row
            for row in rows
            if row.get("event_type") == "exec" and _row_mentions_path_in_cmd(row, path_a)
        ]
        rows_b = [
            row
            for row in rows
            if row.get("event_type") == "exec" and _row_mentions_path_in_cmd(row, path_b)
        ]
        assert rows_a, f"trial={trial} path_a wrapper-exec rows missing from timeline"
        assert rows_b, f"trial={trial} path_b wrapper-exec rows missing from timeline"

        wrong_a = [
            row
            for row in rows_a
            if row.get("job_id") not in {None, job_a}
        ]
        wrong_b = [
            row
            for row in rows_b
            if row.get("job_id") not in {None, job_b}
        ]
        assert not wrong_a, f"trial={trial} path_a wrapper-exec cross-attribution: {wrong_a}"
        assert not wrong_b, f"trial={trial} path_b wrapper-exec cross-attribution: {wrong_b}"
