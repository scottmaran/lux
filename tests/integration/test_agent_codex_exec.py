from __future__ import annotations

from tests.integration.helpers import (
    codex_exec_failure_template,
    codex_exec_success_template,
    resolve_codex_mode,
)

import pytest


@pytest.mark.integration
@pytest.mark.agent_codex_exec
def test_agent_codex_exec_success_lane(live_stack_factory) -> None:
    """`/run` executes codex-lane command end-to-end and yields owned timeline evidence."""
    mode = resolve_codex_mode()
    stack = live_stack_factory(
        run_cmd_template=codex_exec_success_template(mode),
        ownership_root_comm=["codex"] if mode == "real" else [],
        include_codex_mount=(mode == "real"),
    )

    stack.assert_core_services_running()
    prompt = "Summarize this in one line: Codex integration exec lane success"
    job_id = stack.submit_job(prompt, name="agent-codex-exec-success")["job_id"]
    finished = stack.wait_for_job(job_id, timeout_sec=360)

    assert finished["status"] == "complete", stack.diagnostics()
    assert finished.get("exit_code") == 0, stack.diagnostics()

    input_meta = stack.read_job_input(job_id)
    command = str(input_meta.get("command", ""))
    if mode == "real":
        assert "codex" in command

    stdout_path = stack.log_root / "jobs" / job_id / "stdout.log"
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    assert stdout_text.strip(), stack.diagnostics()

    stack.wait_for_row("filtered_timeline.jsonl", lambda row: row.get("job_id") == job_id)


@pytest.mark.integration
@pytest.mark.agent_codex_exec
def test_agent_codex_exec_expected_failure_classification(live_stack_factory) -> None:
    """Codex exec lane failures are surfaced with deterministic failed status and diagnostics."""
    mode = resolve_codex_mode()
    stack = live_stack_factory(
        run_cmd_template=codex_exec_failure_template(mode),
        ownership_root_comm=["codex"] if mode == "real" else [],
        include_codex_mount=(mode == "real"),
    )

    prompt = "This prompt should land in a known failing codex lane"
    job_id = stack.submit_job(prompt, name="agent-codex-exec-failure")["job_id"]
    finished = stack.wait_for_job(job_id, timeout_sec=240)

    stdout_path = stack.log_root / "jobs" / job_id / "stdout.log"
    stderr_path = stack.log_root / "jobs" / job_id / "stderr.log"
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""

    classification = finished.get("error") or "command_failed"
    assert finished["status"] == "failed", stack.diagnostics()
    assert finished.get("exit_code") not in (None, 0), stack.diagnostics()
    assert classification in {"command_failed", "timeout", "agent_unreachable"}

    diagnostic = "\n".join(
        [
            "expected codex failure diagnostics:",
            f"classification={classification}",
            f"exit_code={finished.get('exit_code')}",
            "stdout:",
            stdout_text[-500:],
            "stderr:",
            stderr_text[-500:],
            "timeline excerpt:",
            stack.diagnostics(),
        ]
    )
    assert stdout_text.strip() or stderr_text.strip(), diagnostic
