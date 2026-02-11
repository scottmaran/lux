from __future__ import annotations

import uuid

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.agent_codex]


def _contains_error_signature(text: str) -> bool:
    lowered = text.lower()
    signatures = [
        "traceback",
        "error:",
        "permission denied",
        "agent_unreachable",
        "unauthorized",
        " 404",
        " 500",
    ]
    return any(sig in lowered for sig in signatures)


def test_codex_exec_run_returns_prompt_related_output_and_live_artifacts(
    codex_stack,
    timeline_validator,
) -> None:
    """Codex exec lane produces successful output and live owned timeline artifacts."""
    token = f"LASSO_EXEC_PASS_{uuid.uuid4().hex[:10]}"
    prompt = f"Reply with exactly this token: {token}"

    job_id, status = codex_stack.submit_and_wait(prompt, timeout_sec=300)
    assert status["status"] == "complete", f"Codex exec did not complete: {status}"
    assert status.get("exit_code") == 0, f"Codex exec exit_code was not zero: {status}"

    stdout_path = codex_stack.host_log_path_from_container_path(str(status.get("output_path")))
    stderr_path = codex_stack.host_log_path_from_container_path(str(status.get("error_path")))
    assert stdout_path.exists(), f"Missing stdout log: {stdout_path}"
    assert stderr_path.exists(), f"Missing stderr log: {stderr_path}"

    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    assert stdout_text.strip(), f"Expected non-empty codex stdout: {stdout_path}"
    assert token in stdout_text, (
        "Codex stdout does not look prompt-related; expected token missing.\n"
        f"token={token}\nstdout={stdout_text}\nstderr={stderr_text}"
    )
    assert not _contains_error_signature(stdout_text), f"Unexpected error signature in stdout: {stdout_text}"

    codex_stack.wait_for_jsonl_rows(
        codex_stack.filtered_audit_path,
        lambda rows: any(
            row.get("job_id") == job_id and row.get("event_type") == "exec" and row.get("source") == "audit"
            for row in rows
        ),
        timeout_sec=120,
        message=f"Missing live filtered_audit exec rows for codex job_id={job_id}",
    )
    codex_stack.wait_for_job_timeline_rows(job_id, timeout_sec=120)

    timeline_validator(log_root=codex_stack.log_root)
