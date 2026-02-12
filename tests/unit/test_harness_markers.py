from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


ROOT_DIR = Path(__file__).resolve().parents[2]
HARNESS_PATH = ROOT_DIR / "harness" / "harness.py"


def _load_harness_module():
    spec = importlib.util.spec_from_file_location("harness_module_for_tests", HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load harness module from {HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_pid_path_is_stable_and_run_scoped() -> None:
    """Run marker file path should be stable and include the run id."""
    harness = _load_harness_module()
    run_id = "session_20260212_123456_abcd"
    assert harness.root_pid_path(run_id) == f"/tmp/lasso_root_pid_{run_id}.txt"


def test_root_sid_path_is_stable_and_run_scoped() -> None:
    """SID marker file path should be stable and include the run id."""
    harness = _load_harness_module()
    run_id = "session_20260212_123456_abcd"
    assert harness.root_sid_path(run_id) == f"/tmp/lasso_root_sid_{run_id}.txt"


def test_root_marker_prefix_collects_namespace_pid_and_sid_with_fallbacks() -> None:
    """Marker prefix should capture both NSpid and NSsid with robust fallbacks."""
    harness = _load_harness_module()
    prefix = harness.root_marker_prefix(
        "/tmp/lasso_root_pid_test.txt",
        "/tmp/lasso_root_sid_test.txt",
    )
    assert "awk '/^NSpid:/ {print $NF}' /proc/$$/status" in prefix
    assert "if [ -z \"$ROOT_PID\" ]; then ROOT_PID=$$; fi;" in prefix
    assert "awk '/^NSsid:/ {print $NF}' /proc/$$/status" in prefix
    assert "if [ -z \"$ROOT_SID\" ]; then ROOT_SID=$ROOT_PID; fi;" in prefix
    assert "printf '%s\\n' \"$ROOT_PID\" > /tmp/lasso_root_pid_test.txt;" in prefix
    assert "printf '%s\\n' \"$ROOT_SID\" > /tmp/lasso_root_sid_test.txt;" in prefix


def test_wrap_with_setsid_uses_ctty_mode_for_tui() -> None:
    """TUI launches should attempt `setsid -c` and keep a fallback path."""
    harness = _load_harness_module()
    wrapped = harness.wrap_with_setsid("cd /work && exec codex", with_ctty=True)
    assert "setsid -c" in wrapped
    assert "exec setsid -c bash -lc" in wrapped
    assert "exec setsid bash -lc" in wrapped


def test_build_remote_command_includes_marker_prefix_when_paths_are_set() -> None:
    """Job remote command should include PID/SID markers and setsid wrapper."""
    harness = _load_harness_module()
    original_template = harness.RUN_CMD_TEMPLATE
    try:
        harness.RUN_CMD_TEMPLATE = "echo {prompt}"
        cmd = harness.build_remote_command(
            prompt="hello world",
            cwd="/work",
            env={},
            timeout=None,
            pid_path="/tmp/lasso_root_pid_test.txt",
            sid_path="/tmp/lasso_root_sid_test.txt",
        )
    finally:
        harness.RUN_CMD_TEMPLATE = original_template

    assert cmd.startswith("exec setsid bash -lc ")
    assert "NSpid:" in cmd
    assert "NSsid:" in cmd
    assert "/tmp/lasso_root_pid_test.txt" in cmd
    assert "/tmp/lasso_root_sid_test.txt" in cmd
    assert "cd /work" in cmd
    assert "hello world" in cmd


def test_build_remote_command_omits_marker_prefix_without_pid_path() -> None:
    """Remote command keeps setsid wrapper but omits marker prelude when marker paths are absent."""
    harness = _load_harness_module()
    original_template = harness.RUN_CMD_TEMPLATE
    try:
        harness.RUN_CMD_TEMPLATE = "echo {prompt}"
        cmd = harness.build_remote_command(
            prompt="hello world",
            cwd="/work",
            env={},
            timeout=None,
            pid_path=None,
        )
    finally:
        harness.RUN_CMD_TEMPLATE = original_template

    assert cmd.startswith("exec setsid bash -lc ")
    assert "ROOT_PID=" not in cmd
    assert "ROOT_SID=" not in cmd
    assert "cd /work" in cmd
    assert "hello world" in cmd
