from __future__ import annotations

import pytest

from tests.integration.helpers import (
    codex_exec_success_template,
    codex_tui_failure_command,
    codex_tui_success_command,
    resolve_codex_mode,
)


@pytest.mark.integration
@pytest.mark.agent_codex_tui
def test_agent_codex_tui_success_lane(live_stack_factory) -> None:
    """TUI/PTY launch path executes codex lane and records session artifacts with ownership."""
    mode = resolve_codex_mode()
    stack = live_stack_factory(
        run_cmd_template=codex_exec_success_template(mode),
        ownership_root_comm=["codex"] if mode == "real" else [],
        include_codex_mount=(mode == "real"),
    )

    output_path = "/work/agent_codex_tui_success.txt"
    command = codex_tui_success_command(mode, output_path)
    proc = stack.run_tui_command(command, name="agent-codex-tui-success", timeout_sec=360)

    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}\n{stack.diagnostics()}"

    session_dir = stack.latest_session()
    assert session_dir is not None, stack.diagnostics()
    meta = stack.session_meta(session_dir)
    session_id = meta["session_id"]

    assert meta.get("exit_code") == 0, meta
    assert isinstance(meta.get("root_pid"), int), meta

    stdout_path = session_dir / "stdout.log"
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    assert stdout_text.strip(), stack.diagnostics()

    stack.wait_for_row("filtered_timeline.jsonl", lambda row: row.get("session_id") == session_id)

    if mode == "stub":
        stack.wait_for_row(
            "filtered_timeline.jsonl",
            lambda row: row.get("session_id") == session_id and (row.get("details") or {}).get("path") == output_path,
        )


@pytest.mark.integration
@pytest.mark.agent_codex_tui
def test_agent_codex_tui_expected_failure_classification(live_stack_factory) -> None:
    """TUI lane surfaces expected failing command behavior with session diagnostics."""
    mode = resolve_codex_mode()
    stack = live_stack_factory(
        run_cmd_template=codex_exec_success_template(mode),
        ownership_root_comm=["codex"] if mode == "real" else [],
        include_codex_mount=(mode == "real"),
    )

    command = codex_tui_failure_command(mode)
    proc = stack.run_tui_command(command, name="agent-codex-tui-failure", timeout_sec=300)

    session_dir = stack.latest_session()
    assert session_dir is not None, stack.diagnostics()
    meta = stack.session_meta(session_dir)
    stdout_path = session_dir / "stdout.log"
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""

    classification = "command_failed"
    diagnostic = "\n".join(
        [
            f"classification={classification}",
            f"return_code={proc.returncode}",
            f"session_exit_code={meta.get('exit_code')}",
            "stdout:",
            stdout_text[-500:],
            "script stdout:",
            proc.stdout[-500:],
            "script stderr:",
            proc.stderr[-500:],
            stack.diagnostics(),
        ]
    )

    assert meta.get("exit_code") not in (None, 0), diagnostic
    assert proc.returncode != 0 or meta.get("exit_code") != 0, diagnostic
