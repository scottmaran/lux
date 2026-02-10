from __future__ import annotations

import os

import pytest

from tests.conftest import assert_timeline_invariants, attributed_rows


def _prompt(path: str) -> str:
    return (
        f"sleep 1; printf 'stress' > {path}; "
        "curl -sI https://example.com >/dev/null || true; "
        "echo stress-ok"
    )


@pytest.mark.stress
@pytest.mark.stress_smoke
def test_stress_smoke_repeatable_trials(live_stack_factory) -> None:
    """Stress smoke executes repeatable live trials and preserves job attribution."""
    trials = int(os.getenv("LASSO_STRESS_SMOKE_TRIALS", "3"))
    stack = live_stack_factory(run_cmd_template="bash -lc {prompt}", ownership_root_comm=[])

    jobs: list[tuple[str, str]] = []
    for idx in range(trials):
        path = f"/work/stress_smoke_{idx}.txt"
        job_id = stack.submit_job(_prompt(path), name=f"stress-smoke-{idx}")["job_id"]
        jobs.append((job_id, path))

    for job_id, _path in jobs:
        finished = stack.wait_for_job(job_id, timeout_sec=300)
        assert finished["status"] == "complete", stack.diagnostics()

    for job_id, path in jobs:
        stack.wait_for_row(
            "filtered_timeline.jsonl",
            lambda row, job_id=job_id, path=path: row.get("job_id") == job_id
            and (row.get("details") or {}).get("path") == path,
            timeout_sec=120,
        )

    timeline = stack.read_jsonl("filtered_timeline.jsonl")
    owned = attributed_rows(timeline)
    assert owned, stack.diagnostics()
    assert_timeline_invariants(owned, stack.sessions_metadata(), stack.jobs_metadata())
