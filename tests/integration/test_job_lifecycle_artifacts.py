from __future__ import annotations

import json
import uuid

import pytest


pytestmark = pytest.mark.integration


def test_completed_job_persists_artifacts_and_root_pid(integration_stack) -> None:
    """Completed jobs persist status/input artifacts and integer root_pid metadata."""
    output_path = f"/work/lifecycle_{uuid.uuid4().hex[:8]}.txt"
    prompt = f"pwd; printf 'ok' > {output_path}"
    job_id, status = integration_stack.submit_and_wait(prompt)
    assert status["status"] == "complete"

    job_dir = integration_stack.log_root / "jobs" / job_id
    input_json = job_dir / "input.json"
    status_json = job_dir / "status.json"
    stdout_log = job_dir / "stdout.log"
    stderr_log = job_dir / "stderr.log"

    assert input_json.exists(), "Missing input.json for completed job."
    assert status_json.exists(), "Missing status.json for completed job."
    assert stdout_log.exists(), "Missing stdout.log for completed job."
    assert stderr_log.exists(), "Missing stderr.log for completed job."

    input_meta = json.loads(input_json.read_text(encoding="utf-8"))
    status_meta = json.loads(status_json.read_text(encoding="utf-8"))
    assert input_meta["job_id"] == job_id
    assert status_meta["job_id"] == job_id
    assert isinstance(input_meta.get("root_pid"), int)
    assert isinstance(status_meta.get("root_pid"), int)
    assert status_meta.get("exit_code") == 0

    host_stdout = integration_stack.host_log_path_from_container_path(str(status.get("output_path")))
    assert host_stdout.exists(), f"Missing stdout log referenced by API: {host_stdout}"
    stdout_text = host_stdout.read_text(encoding="utf-8", errors="replace")
    assert "/work" in stdout_text, f"Expected working-directory output in stdout log: {host_stdout}"
