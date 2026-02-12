from __future__ import annotations

from collections import Counter
import json
import shlex
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from tests.support.integration_stack import is_heartbeat_like_signal_row


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


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AssertionError(f"Expected non-empty ISO timestamp string, got: {value!r}")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_fs_path(row: dict[str, Any]) -> str | None:
    details = row.get("details")
    if isinstance(details, dict):
        path = details.get("path")
        if isinstance(path, str):
            return path
    top_level_path = row.get("path")
    if isinstance(top_level_path, str):
        return top_level_path
    return None


def _session_metrics(rows: list[dict[str, Any]], session_id: str) -> dict[str, Any]:
    scoped = [row for row in rows if row.get("session_id") == session_id]
    fs_rows = [
        row
        for row in scoped
        if isinstance(row.get("event_type"), str) and str(row["event_type"]).startswith("fs_")
    ]
    fs_paths = [path for row in fs_rows if (path := _extract_fs_path(row))]
    fs_type_counts = Counter(str(row["event_type"]) for row in fs_rows)

    exec_count = sum(1 for row in scoped if row.get("event_type") == "exec")
    meaningful_net_count = sum(
        1
        for row in scoped
        if row.get("source") == "ebpf"
        and row.get("event_type") == "net_summary"
        and not is_heartbeat_like_signal_row(row)
    )
    unique_pids = {
        int(row["pid"])
        for row in scoped
        if isinstance(row.get("pid"), int)
    }

    return {
        "session_row_count": len(scoped),
        "exec_count": exec_count,
        "fs_event_count": len(fs_rows),
        "fs_paths": fs_paths,
        "fs_type_counts": dict(fs_type_counts),
        "meaningful_net_count": meaningful_net_count,
        "unique_pid_count": len(unique_pids),
    }


def _session_meets_thresholds(
    rows: list[dict[str, Any]],
    *,
    session_id: str,
    expected_path: str | None = None,
) -> bool:
    metrics = _session_metrics(rows, session_id)
    meets_base = (
        metrics["exec_count"] >= 3
        and metrics["fs_event_count"] >= 1
        and metrics["meaningful_net_count"] >= 1
        and metrics["unique_pid_count"] >= 3
    )
    if not meets_base:
        return False
    if expected_path is not None:
        return expected_path in metrics["fs_paths"]
    return True


def _tail(text: str, *, max_chars: int = 4000) -> str:
    return text if len(text) <= max_chars else text[-max_chars:]


def test_codex_tui_concurrent_kalshi_and_nhl_lanes(
    codex_stack,
    timeline_validator,
) -> None:
    """
    Two real Codex TUI sessions run concurrently, each with one prompt.
    Each lane must show prompt-related output and meet conservative timeline behavior minimums.
    """
    run_id = uuid.uuid4().hex[:8]
    kalshi_file = f"kalshi_markets_{run_id}.py"
    nhl_file = f"nhl_scores_{run_id}.py"
    kalshi_token = f"KALSHI_DONE_{run_id}"
    nhl_token = f"NHL_DONE_{run_id}"

    kalshi_tui_name = f"tui-kalshi-{uuid.uuid4().hex[:8]}"
    nhl_tui_name = f"tui-nhl-{uuid.uuid4().hex[:8]}"

    kalshi_prompt = (
        f"Create a Python script at /work/{kalshi_file} that builds a small Kalshi-market example payload. "
        f"Do not ask follow-up questions; make reasonable assumptions and proceed. "
        f"When complete, reply with exactly {kalshi_token}."
    )
    nhl_prompt = (
        f"Create a Python script at /work/{nhl_file} that builds a small NHL-score example payload. "
        f"Do not ask follow-up questions; make reasonable assumptions and proceed. "
        f"When complete, reply with exactly {nhl_token}."
    )

    kalshi_tui_cmd = f"codex -C /work -s danger-full-access {shlex.quote(kalshi_prompt)}"
    nhl_tui_cmd = f"codex -C /work -s danger-full-access {shlex.quote(nhl_prompt)}"
    kalshi_handle = codex_stack.start_harness_tui_interactive(
        tui_name=kalshi_tui_name,
        tui_cmd=kalshi_tui_cmd,
    )
    nhl_handle = codex_stack.start_harness_tui_interactive(
        tui_name=nhl_tui_name,
        tui_cmd=nhl_tui_cmd,
    )
    codex_stack.prime_tui_terminal(kalshi_handle)
    codex_stack.prime_tui_terminal(nhl_handle)
    stop_results: dict[str, Any] = {}

    try:
        kalshi_session_id = codex_stack.wait_for_session_id_for_tui_name(kalshi_tui_name, timeout_sec=90)
        nhl_session_id = codex_stack.wait_for_session_id_for_tui_name(nhl_tui_name, timeout_sec=90)
        assert kalshi_session_id != nhl_session_id, "Concurrent lanes unexpectedly mapped to the same session id."

        codex_stack.prime_tui_terminal(kalshi_handle, attempts=20, interval_sec=0.1)
        codex_stack.prime_tui_terminal(nhl_handle, attempts=20, interval_sec=0.1)

        codex_stack.wait_for_session_quiescence(
            kalshi_session_id,
            timeout_sec=420,
            stdout_idle_sec=12.0,
            signal_idle_sec=12.0,
            stable_polls=2,
        )
        codex_stack.wait_for_session_quiescence(
            nhl_session_id,
            timeout_sec=420,
            stdout_idle_sec=12.0,
            signal_idle_sec=12.0,
            stable_polls=2,
        )

        expected_kalshi_path = f"/work/{kalshi_file}"
        expected_nhl_path = f"/work/{nhl_file}"
        timeline_rows = codex_stack.wait_for_timeline_rows(
            lambda rows: any(row.get("session_id") == kalshi_session_id for row in rows)
            and any(row.get("session_id") == nhl_session_id for row in rows),
            timeout_sec=120,
            message=(
                "Concurrent TUI lanes did not appear in timeline output "
                f"for sessions {kalshi_session_id} and {nhl_session_id}"
            ),
        )
    finally:
        stop_results[kalshi_tui_name] = codex_stack.stop_harness_tui_interactive(kalshi_handle, wait_timeout_sec=30)
        stop_results[nhl_tui_name] = codex_stack.stop_harness_tui_interactive(nhl_handle, wait_timeout_sec=30)

    kalshi_session_dir = codex_stack.session_dir(kalshi_session_id)
    nhl_session_dir = codex_stack.session_dir(nhl_session_id)
    kalshi_meta = json.loads((kalshi_session_dir / "meta.json").read_text(encoding="utf-8"))
    nhl_meta = json.loads((nhl_session_dir / "meta.json").read_text(encoding="utf-8"))
    kalshi_stdout = (kalshi_session_dir / "stdout.log").read_text(encoding="utf-8", errors="replace")
    nhl_stdout = (nhl_session_dir / "stdout.log").read_text(encoding="utf-8", errors="replace")

    kalshi_driver = stop_results[kalshi_tui_name]
    nhl_driver = stop_results[nhl_tui_name]

    assert kalshi_meta.get("mode") == "tui", f"Unexpected mode for kalshi lane: {kalshi_meta}"
    assert nhl_meta.get("mode") == "tui", f"Unexpected mode for nhl lane: {nhl_meta}"
    assert isinstance(kalshi_meta.get("root_pid"), int), f"Missing root_pid for kalshi lane: {kalshi_meta}"
    assert isinstance(nhl_meta.get("root_pid"), int), f"Missing root_pid for nhl lane: {nhl_meta}"
    assert isinstance(kalshi_meta.get("root_sid"), int), f"Missing root_sid for kalshi lane: {kalshi_meta}"
    assert isinstance(nhl_meta.get("root_sid"), int), f"Missing root_sid for nhl lane: {nhl_meta}"
    assert kalshi_meta.get("ended_at"), f"Missing ended_at for kalshi lane: {kalshi_meta}"
    assert nhl_meta.get("ended_at"), f"Missing ended_at for nhl lane: {nhl_meta}"

    kalshi_start = _parse_iso(kalshi_meta.get("started_at"))
    kalshi_end = _parse_iso(kalshi_meta.get("ended_at"))
    nhl_start = _parse_iso(nhl_meta.get("started_at"))
    nhl_end = _parse_iso(nhl_meta.get("ended_at"))
    assert kalshi_start < nhl_end and nhl_start < kalshi_end, (
        "Expected overlapping session windows for concurrent TUI lanes.\n"
        f"kalshi_window=({kalshi_start.isoformat()}, {kalshi_end.isoformat()})\n"
        f"nhl_window=({nhl_start.isoformat()}, {nhl_end.isoformat()})"
    )

    assert kalshi_stdout.strip(), "Kalshi TUI stdout is empty."
    assert nhl_stdout.strip(), "NHL TUI stdout is empty."
    assert "connection to agent closed." in kalshi_stdout.lower(), (
        "Kalshi TUI session did not close cleanly.\n"
        f"driver_stdout_tail:\n{kalshi_driver.stdout}\n"
        f"driver_stderr_tail:\n{kalshi_driver.stderr}\n"
        f"session_stdout_tail:\n{_tail(kalshi_stdout)}"
    )
    assert "connection to agent closed." in nhl_stdout.lower(), (
        "NHL TUI session did not close cleanly.\n"
        f"driver_stdout_tail:\n{nhl_driver.stdout}\n"
        f"driver_stderr_tail:\n{nhl_driver.stderr}\n"
        f"session_stdout_tail:\n{_tail(nhl_stdout)}"
    )
    assert kalshi_token in kalshi_stdout or kalshi_file in kalshi_stdout, (
        "Kalshi TUI stdout does not appear prompt-related.\n"
        f"token={kalshi_token} file={kalshi_file}\n"
        f"session_stdout_tail:\n{_tail(kalshi_stdout)}"
    )
    assert nhl_token in nhl_stdout or nhl_file in nhl_stdout, (
        "NHL TUI stdout does not appear prompt-related.\n"
        f"token={nhl_token} file={nhl_file}\n"
        f"session_stdout_tail:\n{_tail(nhl_stdout)}"
    )
    assert not _contains_error_signature(kalshi_stdout), (
        "Unexpected error signature in kalshi session stdout.\n"
        f"session_stdout_tail:\n{_tail(kalshi_stdout)}"
    )
    assert not _contains_error_signature(nhl_stdout), (
        "Unexpected error signature in nhl session stdout.\n"
        f"session_stdout_tail:\n{_tail(nhl_stdout)}"
    )

    kalshi_host_file = codex_stack.workspace_root / kalshi_file
    nhl_host_file = codex_stack.workspace_root / nhl_file
    assert kalshi_host_file.exists(), f"Expected kalshi output file to exist: {kalshi_host_file}"
    assert nhl_host_file.exists(), f"Expected nhl output file to exist: {nhl_host_file}"
    assert kalshi_host_file.stat().st_size > 0, f"Kalshi output file is empty: {kalshi_host_file}"
    assert nhl_host_file.stat().st_size > 0, f"NHL output file is empty: {nhl_host_file}"

    kalshi_metrics = _session_metrics(timeline_rows, kalshi_session_id)
    nhl_metrics = _session_metrics(timeline_rows, nhl_session_id)
    assert kalshi_metrics["exec_count"] >= 3, f"Kalshi lane exec threshold not met: {kalshi_metrics}"
    assert nhl_metrics["exec_count"] >= 3, f"NHL lane exec threshold not met: {nhl_metrics}"
    assert kalshi_metrics["fs_event_count"] >= 1, f"Kalshi lane fs threshold not met: {kalshi_metrics}"
    assert nhl_metrics["fs_event_count"] >= 1, f"NHL lane fs threshold not met: {nhl_metrics}"
    assert kalshi_metrics["meaningful_net_count"] >= 1, (
        "Kalshi lane meaningful network threshold not met.\n"
        f"metrics={kalshi_metrics}"
    )
    assert nhl_metrics["meaningful_net_count"] >= 1, (
        "NHL lane meaningful network threshold not met.\n"
        f"metrics={nhl_metrics}"
    )
    assert kalshi_metrics["unique_pid_count"] >= 3, f"Kalshi lane PID threshold not met: {kalshi_metrics}"
    assert nhl_metrics["unique_pid_count"] >= 3, f"NHL lane PID threshold not met: {nhl_metrics}"
    assert f"/work/{kalshi_file}" in kalshi_metrics["fs_paths"], (
        "Kalshi expected fs path missing.\n"
        f"metrics={kalshi_metrics}"
    )
    assert f"/work/{nhl_file}" in nhl_metrics["fs_paths"], (
        "NHL expected fs path missing.\n"
        f"metrics={nhl_metrics}"
    )

    timeline_validator(log_root=codex_stack.run_root)
