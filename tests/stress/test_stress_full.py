from __future__ import annotations

import os

import pytest

from tests.conftest import assert_timeline_invariants, attributed_rows


def _prompt(path: str) -> str:
    return (
        f"sleep 1; printf 'stress-full' > {path}; "
        "curl -sI https://example.com >/dev/null || true; "
        "echo stress-full-ok"
    )


@pytest.mark.stress
@pytest.mark.stress_full
def test_stress_full_trials(live_stack_factory) -> None:
    """Stress full lane runs larger live trial counts without attribution regression."""
    if os.getenv("LASSO_ENABLE_STRESS_FULL") != "1":
        pytest.skip("set LASSO_ENABLE_STRESS_FULL=1 to run stress-full lane")

    trials = int(os.getenv("LASSO_STRESS_FULL_TRIALS", "8"))
    stack = live_stack_factory(run_cmd_template="bash -lc {prompt}", ownership_root_comm=[])

    jobs: list[tuple[str, str]] = []
    for idx in range(trials):
        path = f"/work/stress_full_{idx}.txt"
        job_id = stack.submit_job(_prompt(path), name=f"stress-full-{idx}")["job_id"]
        jobs.append((job_id, path))

    for job_id, _path in jobs:
        finished = stack.wait_for_job(job_id, timeout_sec=420)
        assert finished["status"] == "complete", stack.diagnostics()

    for job_id, path in jobs:
        stack.wait_for_row(
            "filtered_timeline.jsonl",
            lambda row, job_id=job_id, path=path: row.get("job_id") == job_id
            and (row.get("details") or {}).get("path") == path,
            timeout_sec=180,
        )

    timeline = stack.read_jsonl("filtered_timeline.jsonl")
    owned = attributed_rows(timeline)
    assert owned, stack.diagnostics()
    assert_timeline_invariants(owned, stack.sessions_metadata(), stack.jobs_metadata())

    # Guard against cross-attribution across high-trial overlap.
    for job_id, path in jobs:
        for row in timeline:
            details = row.get("details") or {}
            if details.get("path") == path:
                assert row.get("job_id") == job_id
