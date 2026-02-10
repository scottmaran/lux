from __future__ import annotations

import json
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

    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    stdout_text = (session_dir / "stdout.log").read_text(encoding="utf-8", errors="replace")
    assert meta.get("mode") == "tui"
    assert meta.get("exit_code") == 0, f"Expected exit_code=0 in session meta: {meta}"
    assert isinstance(meta.get("root_pid"), int), f"Expected integer root_pid in session meta: {meta}"
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
