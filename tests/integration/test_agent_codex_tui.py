from __future__ import annotations

import json
import shlex
import uuid
from pathlib import Path

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


def _session_dirs(log_root: Path) -> set[str]:
    sessions_dir = log_root / "sessions"
    if not sessions_dir.exists():
        return set()
    return {entry.name for entry in sessions_dir.iterdir() if entry.is_dir()}


def test_codex_tui_path_runs_and_persists_session_artifacts(
    codex_stack,
    timeline_validator,
) -> None:
    """Harness TUI path runs Codex command, captures artifacts, and emits live timeline rows."""
    token = f"LASSO_TUI_PASS_{uuid.uuid4().hex[:10]}"
    tui_name = f"tui-{uuid.uuid4().hex[:8]}"
    before = _session_dirs(codex_stack.log_root)

    result = codex_stack.run_harness_tui(
        tui_cmd=f"codex exec --skip-git-repo-check 'Reply with exactly this token: {token}'",
        tui_name=tui_name,
        timeout_sec=300,
    )
    assert result.returncode == 0, f"TUI path exited non-zero. stdout={result.stdout}\nstderr={result.stderr}"

    after = _session_dirs(codex_stack.log_root)
    created = sorted(after - before)
    assert len(created) == 1, f"Expected exactly one new session directory; got {created}"
    session_id = created[0]
    session_dir = codex_stack.log_root / "sessions" / session_id

    codex_stack.wait_for_session_quiescence(
        session_id,
        timeout_sec=120,
        stdout_idle_sec=8.0,
        signal_idle_sec=8.0,
        stable_polls=2,
    )

    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    stdout_text = (session_dir / "stdout.log").read_text(encoding="utf-8", errors="replace")
    assert meta.get("mode") == "tui"
    assert meta.get("exit_code") == 0, f"Expected exit_code=0 in session meta: {meta}"
    assert isinstance(meta.get("root_pid"), int), f"Expected integer root_pid in session meta: {meta}"
    assert isinstance(meta.get("root_sid"), int), f"Expected integer root_sid in session meta: {meta}"
    assert stdout_text.strip(), f"Expected non-empty TUI stdout for session {session_id}"
    assert token in stdout_text, (
        "TUI stdout does not look prompt-related; expected token missing.\n"
        f"token={token}\nstdout={stdout_text}\nexec_stdout={result.stdout}\nexec_stderr={result.stderr}"
    )
    assert not _contains_error_signature(stdout_text), f"Unexpected error signature in TUI stdout: {stdout_text}"

    codex_stack.wait_for_timeline_rows(
        lambda rows: any(row.get("session_id") == session_id for row in rows),
        timeout_sec=120,
        message=f"Missing live timeline rows for session_id={session_id}",
    )

    timeline_validator(log_root=codex_stack.log_root)


def test_codex_tui_prompt_pwd_emits_session_exec_row(
    codex_stack,
) -> None:
    """
    Real Codex TUI lane accepts a simple prompt, executes `pwd`, and emits an owned exec row.
    This is a smoke test for TUI startup + prompt execution behavior.
    """
    tui_name = f"tui-pwd-{uuid.uuid4().hex[:8]}"
    before = _session_dirs(codex_stack.log_root)
    prompt = (
        "Run the shell command `pwd` in the workspace, then reply with only the command output. "
        "Do not ask follow-up questions."
    )
    tui_cmd = f"codex -C /work -s danger-full-access {shlex.quote(prompt)}"
    handle = codex_stack.start_harness_tui_interactive(
        tui_name=tui_name,
        tui_cmd=tui_cmd,
    )
    codex_stack.prime_tui_terminal(handle, attempts=30, interval_sec=0.1)
    session_id: str | None = None
    stop_result = None
    try:
        session_id = codex_stack.wait_for_session_id_for_tui_name(tui_name, timeout_sec=90)
        codex_stack.prime_tui_terminal(handle, attempts=20, interval_sec=0.1)
        codex_stack.wait_for_timeline_rows(
            lambda rows: any(
                row.get("session_id") == session_id
                and row.get("source") == "audit"
                and row.get("event_type") == "exec"
                and isinstance(row.get("details"), dict)
                and "pwd" in str(row["details"].get("cmd", "")).lower()
                for row in rows
            ),
            timeout_sec=180,
            message=f"Missing session-scoped exec row containing pwd for session_id={session_id}",
        )
    finally:
        stop_result = codex_stack.stop_harness_tui_interactive(handle, wait_timeout_sec=30)

    after = _session_dirs(codex_stack.log_root)
    created = sorted(after - before)
    assert len(created) == 1, f"Expected exactly one new session directory; got {created}"
    session_id = created[0]
    session_dir = codex_stack.log_root / "sessions" / session_id
    assert stop_result is not None
    assert stop_result.returncode in (0, 130), (
        "Interactive harness TUI exited unexpectedly for pwd prompt.\n"
        f"driver_stdout={stop_result.stdout}\n"
        f"driver_stderr={stop_result.stderr}"
    )

    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    stdout_text = (session_dir / "stdout.log").read_text(encoding="utf-8", errors="replace")
    assert meta.get("mode") == "tui", f"Expected mode=tui in session meta: {meta}"
    assert isinstance(meta.get("root_pid"), int), f"Expected integer root_pid in session meta: {meta}"
    assert isinstance(meta.get("root_sid"), int), f"Expected integer root_sid in session meta: {meta}"
    assert stdout_text.strip(), f"Expected non-empty TUI stdout for session {session_id}"
    assert "pwd" in stdout_text.lower(), (
        "TUI stdout does not look prompt-related for pwd test.\n"
        f"stdout={stdout_text}\ndriver_stdout={stop_result.stdout}\ndriver_stderr={stop_result.stderr}"
    )
    assert "/work" in stdout_text, f"Expected pwd output path in TUI stdout for session {session_id}"
    assert not _contains_error_signature(stdout_text), f"Unexpected error signature in TUI stdout: {stdout_text}"
