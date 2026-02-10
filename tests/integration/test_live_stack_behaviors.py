from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tests.conftest import assert_timeline_invariants, attributed_rows


def _job_prompt(path: str) -> str:
    return (
        f"sleep 1; printf 'ok' > {path}; "
        "curl -sI https://example.com >/dev/null || true; "
        "echo job-complete"
    )


@pytest.mark.integration
def test_job_lifecycle_artifacts_are_persisted(live_stack_factory) -> None:
    """A submitted live job persists input/status/stdout artifacts with root_pid metadata."""
    stack = live_stack_factory(
        run_cmd_template="bash -lc {prompt}",
        ownership_root_comm=[],
    )

    path = "/work/integration_lifecycle.txt"
    submitted = stack.submit_job(_job_prompt(path), name="integration-lifecycle")
    job_id = submitted["job_id"]
    finished = stack.wait_for_job(job_id)

    assert finished["status"] == "complete", stack.diagnostics()
    assert finished.get("exit_code") == 0, stack.diagnostics()
    assert isinstance(finished.get("root_pid"), int), finished

    input_meta = stack.read_job_input(job_id)
    status_meta = stack.read_job_status_file(job_id)
    assert input_meta.get("job_id") == job_id
    assert status_meta.get("job_id") == job_id
    assert isinstance(input_meta.get("root_pid"), int), input_meta
    assert isinstance(status_meta.get("root_pid"), int), status_meta

    stdout_path = stack.log_root / "jobs" / job_id / "stdout.log"
    assert stdout_path.exists()
    assert stdout_path.read_text(encoding="utf-8", errors="replace").strip()


@pytest.mark.integration
def test_filesystem_and_network_events_are_owned_by_job(live_stack_factory) -> None:
    """Live filtered audit/eBPF/timeline outputs contain attributed fs+net job activity."""
    stack = live_stack_factory(
        run_cmd_template="bash -lc {prompt}",
        ownership_root_comm=[],
    )

    path = "/work/integration_fs_net.txt"
    job_id = stack.submit_job(_job_prompt(path), name="integration-fs-net")["job_id"]
    finished = stack.wait_for_job(job_id)
    assert finished["status"] == "complete", stack.diagnostics()

    stack.wait_for_row(
        "filtered_audit.jsonl",
        lambda row: row.get("job_id") == job_id
        and str(row.get("event_type", "")).startswith("fs_")
        and row.get("path") == path,
    )
    stack.wait_for_row(
        "filtered_ebpf.jsonl",
        lambda row: row.get("job_id") == job_id and row.get("event_type") in {"net_connect", "net_send"},
    )
    stack.wait_for_row(
        "filtered_timeline.jsonl",
        lambda row: row.get("job_id") == job_id and (row.get("details") or {}).get("path") == path,
    )

    timeline = stack.read_jsonl("filtered_timeline.jsonl")
    assert timeline, stack.diagnostics()
    owned = attributed_rows(timeline)
    assert owned, stack.diagnostics()
    assert_timeline_invariants(owned, stack.sessions_metadata(), stack.jobs_metadata())


@pytest.mark.integration
def test_concurrent_jobs_and_session_attribution_sanity(live_stack_factory) -> None:
    """Concurrent jobs and a TUI session keep isolated ownership attribution in timeline output."""
    stack = live_stack_factory(
        run_cmd_template="bash -lc {prompt}",
        ownership_root_comm=[],
    )

    session_path = "/work/integration_session_path.txt"
    tui_cmd = f"bash -lc \"sleep 4; printf 'session' > {session_path}; echo tui-complete\""

    tui_result: dict[str, object] = {}

    def _run_tui() -> None:
        tui_result["proc"] = stack.run_tui_command(tui_cmd, name="concurrency-session")

    tui_thread = threading.Thread(target=_run_tui, daemon=True)
    tui_thread.start()

    job_a_path = "/work/integration_concurrent_a.txt"
    job_b_path = "/work/integration_concurrent_b.txt"

    job_a = stack.submit_job(_job_prompt(job_a_path), name="concurrency-job-a")["job_id"]
    job_b = stack.submit_job(_job_prompt(job_b_path), name="concurrency-job-b")["job_id"]

    finished_a = stack.wait_for_job(job_a)
    finished_b = stack.wait_for_job(job_b)

    assert finished_a["status"] == "complete", stack.diagnostics()
    assert finished_b["status"] == "complete", stack.diagnostics()

    tui_thread.join(timeout=120)
    proc = tui_result.get("proc")
    assert proc is not None, "TUI command thread did not return"
    assert proc.returncode == 0, f"TUI failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"

    session_dir = stack.latest_session()
    assert session_dir is not None, stack.diagnostics()
    session_meta = stack.session_meta(session_dir)
    session_id = session_meta["session_id"]

    stack.wait_for_row(
        "filtered_timeline.jsonl",
        lambda row: row.get("job_id") == job_a and (row.get("details") or {}).get("path") == job_a_path,
    )
    stack.wait_for_row(
        "filtered_timeline.jsonl",
        lambda row: row.get("job_id") == job_b and (row.get("details") or {}).get("path") == job_b_path,
    )
    stack.wait_for_row(
        "filtered_timeline.jsonl",
        lambda row: row.get("session_id") == session_id and (row.get("details") or {}).get("path") == session_path,
    )

    timeline = stack.read_jsonl("filtered_timeline.jsonl")
    owned = attributed_rows(timeline)
    assert owned, stack.diagnostics()
    assert_timeline_invariants(owned, stack.sessions_metadata(), stack.jobs_metadata())

    # No cross-attribution between concurrent jobs.
    for row in timeline:
        details = row.get("details") or {}
        path = details.get("path")
        if path == job_a_path:
            assert row.get("job_id") == job_a
        if path == job_b_path:
            assert row.get("job_id") == job_b
