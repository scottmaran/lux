from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.integration


def _rows_are_job_scoped(rows: list[dict], job_id: str) -> bool:
    if not rows:
        return False
    return all(row.get("job_id") == job_id for row in rows)


def _rows_are_session_scoped(rows: list[dict], session_id: str) -> bool:
    if not rows:
        return False
    return all(row.get("session_id") == session_id for row in rows)


def test_run_root_created_and_flat_log_files_not_written(integration_stack) -> None:
    """Stack startup writes logs under run/service subdirectories, not flat log_root files."""
    run_root = integration_stack.run_root
    integration_stack.wait_for(
        lambda: run_root.exists(),
        timeout_sec=30.0,
        message=f"run root was not created: {run_root}",
    )

    expected_dirs = (
        run_root / "collector" / "raw",
        run_root / "collector" / "filtered",
        run_root / "harness" / "jobs",
        run_root / "harness" / "sessions",
        run_root / "harness" / "labels" / "sessions",
        run_root / "harness" / "labels" / "jobs",
    )
    for path in expected_dirs:
        integration_stack.wait_for(
            lambda p=path: p.exists(),
            timeout_sec=30.0,
            message=f"expected path missing: {path}",
        )

    legacy_flat_files = (
        integration_stack.log_root / "audit.log",
        integration_stack.log_root / "ebpf.jsonl",
        integration_stack.log_root / "filtered_audit.jsonl",
        integration_stack.log_root / "filtered_ebpf.jsonl",
        integration_stack.log_root / "filtered_ebpf_summary.jsonl",
        integration_stack.log_root / "filtered_timeline.jsonl",
    )
    for legacy in legacy_flat_files:
        assert not legacy.exists(), f"legacy flat path should not exist: {legacy}"


def test_job_timeline_copy_is_materialized_per_job(integration_stack) -> None:
    """Each completed job materializes a dedicated filtered_timeline.jsonl copy."""
    path_token = f"/work/job_copy_{uuid.uuid4().hex[:8]}.txt"
    job_id, status = integration_stack.submit_and_wait(f"printf copy > {path_token}; sleep 2", timeout_sec=180)
    assert status["status"] == "complete", f"job did not complete: {status}"

    integration_stack.wait_for_job_timeline_rows(job_id, timeout_sec=120, required_path=path_token)

    job_timeline_path = integration_stack.job_dir(job_id) / "filtered_timeline.jsonl"
    rows = integration_stack.wait_for_jsonl_rows(
        job_timeline_path,
        lambda items: _rows_are_job_scoped(items, job_id),
        timeout_sec=120,
        message=f"job timeline copy missing or not scoped for job_id={job_id}",
    )
    assert any((row.get("details") or {}).get("path") == path_token for row in rows), (
        f"job timeline copy missing expected fs path row for {path_token}"
    )


def test_session_timeline_copy_is_materialized_per_session(integration_stack) -> None:
    """Each completed TUI session materializes a dedicated filtered_timeline.jsonl copy."""
    tui_name = f"layout-session-{uuid.uuid4().hex[:8]}"
    before = {entry.name for entry in integration_stack.sessions_dir.iterdir() if entry.is_dir()} if integration_stack.sessions_dir.exists() else set()
    result = integration_stack.run_harness_tui(
        tui_cmd="bash -lc 'pwd; echo session-copy-ok'",
        tui_name=tui_name,
        timeout_sec=180,
    )
    assert result.returncode == 0, f"TUI lane failed: stdout={result.stdout}\nstderr={result.stderr}"

    after = {entry.name for entry in integration_stack.sessions_dir.iterdir() if entry.is_dir()} if integration_stack.sessions_dir.exists() else set()
    created = sorted(after - before)
    assert len(created) == 1, f"Expected exactly one new session directory; got {created}"
    session_id = created[0]

    session_timeline_path = integration_stack.session_dir(session_id) / "filtered_timeline.jsonl"
    integration_stack.wait_for(
        lambda: session_timeline_path.exists(),
        timeout_sec=120.0,
        message=f"session timeline copy was not created for session_id={session_id}",
    )
    rows = integration_stack.read_jsonl(session_timeline_path)
    assert _rows_are_session_scoped(rows, session_id) or not rows, (
        f"session timeline copy contains rows from other sessions: {rows}"
    )
