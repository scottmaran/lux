from __future__ import annotations

import errno
import json
import os
import pty
import select
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from tests.support.integration_stack import find_free_port, run_cmd


pytestmark = [pytest.mark.integration, pytest.mark.agent_codex]

ROOT_DIR = Path(__file__).resolve().parents[2]
COMPOSE_BASE = ROOT_DIR / "compose.yml"
COMPOSE_TEST_OVERRIDE = ROOT_DIR / "tests" / "integration" / "compose.test.override.yml"
COMPOSE_CODEX = ROOT_DIR / "compose.codex.yml"


def _run_lasso(
    lasso_bin: Path,
    *,
    config_path: Path,
    compose_files: tuple[Path, ...],
    args: list[str],
    env: dict[str, str],
    timeout: float,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd: list[str] = [str(lasso_bin), "--config", str(config_path)]
    for compose_file in compose_files:
        cmd.extend(["--compose-file", str(compose_file)])
    cmd.extend(args)
    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            "lasso command failed.\n"
            f"cmd={' '.join(cmd)}\n"
            f"returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _write_cli_config(
    *,
    config_path: Path,
    log_root: Path,
    workspace_root: Path,
    project_name: str,
    api_port: int,
    api_token: str,
) -> None:
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                f"  log_root: {log_root}",
                f"  workspace_root: {workspace_root}",
                "release:",
                '  tag: "local"',
                "docker:",
                f"  project_name: {project_name}",
                "harness:",
                "  api_host: 127.0.0.1",
                f"  api_port: {api_port}",
                f'  api_token: "{api_token}"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _session_dirs(log_root: Path) -> set[str]:
    sessions_dir = log_root
    if not sessions_dir.exists():
        return set()
    return {entry.name for entry in sessions_dir.iterdir() if entry.is_dir()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _extract_run_id_from_up(result: subprocess.CompletedProcess[str]) -> str:
    payload = result.stdout or ""
    if not payload.strip():
        raise AssertionError("lasso up did not return payload with run_id")
    for raw_line in reversed(payload.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = parsed.get("run_id")
        if isinstance(run_id, str) and run_id:
            return run_id
    raise AssertionError(f"lasso up payload missing run_id: {payload}")


def _drain_pty(master_fd: int, chunks: list[str]) -> None:
    while True:
        ready, _, _ = select.select([master_fd], [], [], 0)
        if not ready:
            return
        try:
            payload = os.read(master_fd, 8192)
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF):
                return
            raise
        if not payload:
            return
        chunks.append(payload.decode("utf-8", errors="replace"))


def _read_tail(chunks: list[str], max_chars: int = 4000) -> str:
    text = "".join(chunks)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


@pytest.fixture(scope="session")
def lasso_cli_binary_for_codex() -> Path:
    run_cmd(["cargo", "build", "--bin", "lasso"], cwd=ROOT_DIR / "lasso", timeout=1800)
    bin_path = ROOT_DIR / "lasso" / "target" / "debug" / "lasso"
    if not bin_path.exists():
        raise AssertionError(f"Built lasso binary is missing at {bin_path}")
    return bin_path


def test_codex_tui_via_lasso_cli_produces_prompt_driven_session_evidence(
    tmp_path: Path,
    ensure_codex_credentials,
    build_local_images,
    lasso_cli_binary_for_codex: Path,
) -> None:
    """
    CLI-driven Codex TUI path should run with default harness TUI command,
    accept interactive input, and emit session/timeline evidence.
    """
    runtime_root = tmp_path / f"cli-codex-tui-{uuid.uuid4().hex[:8]}"
    log_root = runtime_root / "logs"
    workspace_root = runtime_root / "workspace"
    config_dir = runtime_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.yaml"
    env_file = config_dir / "compose.env"
    project_name = f"lasso-cli-codex-{uuid.uuid4().hex[:8]}"
    harness_port = find_free_port()
    api_token = f"token-{uuid.uuid4().hex}"
    compose_files = (COMPOSE_BASE, COMPOSE_TEST_OVERRIDE, COMPOSE_CODEX)
    _write_cli_config(
        config_path=config_path,
        log_root=log_root,
        workspace_root=workspace_root,
        project_name=project_name,
        api_port=harness_port,
        api_token=api_token,
    )

    env = os.environ.copy()
    env["LASSO_ENV_FILE"] = str(env_file)
    env["LASSO_BUNDLE_DIR"] = str(ROOT_DIR)

    # Ensure the strict default CLI behavior: no ambient TUI command override.
    env.pop("HARNESS_TUI_CMD", None)

    _run_lasso(
        lasso_cli_binary_for_codex,
        config_path=config_path,
        compose_files=compose_files,
        args=["config", "apply"],
        env=env,
        timeout=120,
    )

    master_fd: int | None = None
    slave_fd: int | None = None
    proc: subprocess.Popen[bytes] | None = None
    pty_chunks: list[str] = []
    created_session: str | None = None
    run_id: str | None = None
    run_root: Path | None = None
    sessions_root: Path | None = None
    try:
        up_result = _run_lasso(
            lasso_cli_binary_for_codex,
            config_path=config_path,
            compose_files=compose_files,
            args=["up", "--codex", "--wait", "--timeout-sec", "240"],
            env=env,
            timeout=600,
        )
        run_id = _extract_run_id_from_up(up_result)
        run_root = log_root / run_id
        sessions_root = run_root / "harness" / "sessions"
        before_sessions = _session_dirs(sessions_root)

        master_fd, slave_fd = pty.openpty()
        cmd: list[str] = [str(lasso_cli_binary_for_codex), "--config", str(config_path)]
        for compose_file in compose_files:
            cmd.extend(["--compose-file", str(compose_file)])
        cmd.extend(["tui", "--codex"])
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
        )
        os.close(slave_fd)
        slave_fd = None

        prompt = "Confirm you are running in /work and briefly describe what you can do."
        prompt_sent = False
        priming_payload = (
            b"\x1b[15;1R\x1b[?1;2c\x1b]10;rgb:0000/0000/0000\x07\x1b]11;rgb:ffff/ffff/ffff\x07"
        )

        deadline = time.time() + 360.0
        saw_codex_ui = False
        while time.time() < deadline:
            _drain_pty(master_fd, pty_chunks)

            assert sessions_root is not None
            after_sessions = _session_dirs(sessions_root)
            created = sorted(after_sessions - before_sessions)
            if len(created) == 1:
                created_session = created[0]

            if proc.poll() is not None and created_session is None:
                raise AssertionError(
                    "lasso tui --codex exited before session creation.\n"
                    f"returncode={proc.returncode}\npty_tail:\n{_read_tail(pty_chunks)}"
                )

            if created_session:
                assert run_root is not None
                session_stdout = run_root / "harness" / "sessions" / created_session / "stdout.log"
                if session_stdout.exists():
                    stdout_text = session_stdout.read_text(encoding="utf-8", errors="replace")
                    saw_codex_ui = ("OpenAI Codex" in stdout_text) or ("context left" in stdout_text.lower())
                    if saw_codex_ui and not prompt_sent:
                        os.write(master_fd, priming_payload)
                        os.write(master_fd, prompt.encode("utf-8") + b"\r")
                        prompt_sent = True
                    if saw_codex_ui and prompt_sent:
                        break

            if proc.poll() is None:
                os.write(master_fd, priming_payload)
            time.sleep(0.2)
        else:
            raise AssertionError(
                "Timed out waiting for Codex UI startup and prompt injection via CLI.\n"
                f"session={created_session}\npty_tail:\n{_read_tail(pty_chunks)}"
            )
    finally:
        if master_fd is not None and proc is not None and proc.poll() is None:
            for _ in range(3):
                try:
                    os.write(master_fd, b"\x03")
                except OSError:
                    break
                time.sleep(0.5)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

        if master_fd is not None:
            _drain_pty(master_fd, pty_chunks)
            try:
                os.close(master_fd)
            except OSError:
                pass
        if slave_fd is not None:
            try:
                os.close(slave_fd)
            except OSError:
                pass

        _run_lasso(
            lasso_cli_binary_for_codex,
            config_path=config_path,
            compose_files=compose_files,
            args=["down", "--codex", "--volumes", "--remove-orphans"],
            env=env,
            timeout=240,
            check=False,
        )

    assert created_session, f"Expected exactly one created session.\npty_tail:\n{_read_tail(pty_chunks)}"
    assert run_root is not None, "Expected run root from lasso up output."

    session_dir = run_root / "harness" / "sessions" / created_session
    meta_path = session_dir / "meta.json"
    stdin_path = session_dir / "stdin.log"
    stdout_path = session_dir / "stdout.log"
    assert meta_path.exists(), f"Missing session meta.json: {meta_path}"
    assert stdin_path.exists(), f"Missing session stdin.log: {stdin_path}"
    assert stdout_path.exists(), f"Missing session stdout.log: {stdout_path}"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stdin_text = stdin_path.read_text(encoding="utf-8", errors="replace")
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    assert meta.get("mode") == "tui", f"Unexpected session mode: {meta}"
    assert isinstance(meta.get("root_pid"), int), f"Expected integer root_pid in session meta: {meta}"
    assert isinstance(meta.get("root_sid"), int), f"Expected integer root_sid in session meta: {meta}"
    assert "codex -C /work -s danger-full-access" in str(meta.get("command", "")), (
        "Expected default harness TUI command in session meta.\n"
        f"meta={meta}"
    )
    assert "confirm you are running in /work" in stdin_text.lower(), (
        f"Expected typed prompt input in stdin.log.\nstdin={stdin_text}"
    )
    assert stdout_text.strip(), f"Expected non-empty stdout in {stdout_path}"
    assert ("OpenAI Codex" in stdout_text) or ("context left" in stdout_text.lower()), (
        "Expected Codex interactive UI output in TUI stdout.\n"
        f"stdout_tail={stdout_text[-2000:]}\npty_tail={_read_tail(pty_chunks)}"
    )

    timeline_path = run_root / "collector" / "filtered" / "filtered_timeline.jsonl"
    deadline = time.time() + 180.0
    found_session_rows = False
    while time.time() < deadline:
        rows = _read_jsonl(timeline_path)
        found_session_rows = any(row.get("session_id") == created_session for row in rows)
        if found_session_rows:
            break
        time.sleep(1.0)
    assert found_session_rows, (
        "Expected session-owned timeline evidence for CLI Codex TUI session.\n"
        f"session={created_session}\npty_tail:\n{_read_tail(pty_chunks)}"
    )

    session_rows = [row for row in _read_jsonl(timeline_path) if row.get("session_id") == created_session]
    assert session_rows, f"Expected non-empty session-scoped timeline rows for {created_session}"
