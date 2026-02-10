from __future__ import annotations

import pytest

from tests.conftest import assert_timeline_invariants, attributed_rows


def _prompt(path: str) -> str:
    return (
        f"sleep 1; printf 'regression' > {path}; "
        "curl -sI https://example.com >/dev/null || true; "
        "echo regression-ok"
    )


@pytest.mark.regression
def test_regression_concurrent_job_attribution_is_not_cross_wired(live_stack_factory) -> None:
    """Regression: overlapping job execution must not cross-attribute filesystem events."""
    stack = live_stack_factory(run_cmd_template="bash -lc {prompt}", ownership_root_comm=[])

    path_a = "/work/regression_concurrent_a.txt"
    path_b = "/work/regression_concurrent_b.txt"

    job_a = stack.submit_job(_prompt(path_a), name="regression-a")["job_id"]
    job_b = stack.submit_job(_prompt(path_b), name="regression-b")["job_id"]

    finished_a = stack.wait_for_job(job_a, timeout_sec=300)
    finished_b = stack.wait_for_job(job_b, timeout_sec=300)
    assert finished_a["status"] == "complete", stack.diagnostics()
    assert finished_b["status"] == "complete", stack.diagnostics()

    stack.wait_for_row(
        "filtered_timeline.jsonl",
        lambda row: row.get("job_id") == job_a and (row.get("details") or {}).get("path") == path_a,
    )
    stack.wait_for_row(
        "filtered_timeline.jsonl",
        lambda row: row.get("job_id") == job_b and (row.get("details") or {}).get("path") == path_b,
    )

    timeline = stack.read_jsonl("filtered_timeline.jsonl")
    owned = attributed_rows(timeline)
    assert owned, stack.diagnostics()
    assert_timeline_invariants(owned, stack.sessions_metadata(), stack.jobs_metadata())

    # Historical bug class: events from concurrent jobs leaking to the wrong owner.
    for row in timeline:
        details = row.get("details") or {}
        if details.get("path") == path_a:
            assert row.get("job_id") == job_a
        if details.get("path") == path_b:
            assert row.get("job_id") == job_b
