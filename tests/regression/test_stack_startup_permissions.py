from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.support.integration_stack import ComposeFiles, ComposeStack, run_cmd


pytestmark = pytest.mark.regression


def _chmod_logs_non_writable(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    # Remove write bits for owner/group/other to force unwritable bind-mount behavior.
    path.chmod(0o555)


def _uid_1002_can_write_logs(path: Path, root_dir: Path) -> bool:
    probe = run_cmd(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "1002:1002",
            "-v",
            f"{path}:/logs:rw",
            "alpine",
            "sh",
            "-lc",
            "touch /logs/.perm_probe",
        ],
        cwd=root_dir,
        check=False,
        timeout=30,
    )
    if probe.returncode != 0:
        return False
    try:
        (path / ".perm_probe").unlink(missing_ok=True)
    except OSError:
        pass
    return True


def _write_collector_failure_override(path: Path) -> Path:
    override = path / "compose.collector.fail.override.yml"
    override.write_text(
        (
            "services:\n"
            "  collector:\n"
            "    entrypoint: [\"/bin/sh\", \"-lc\", "
            "\"echo forced-collector-startup-failure >&2; exit 13\"]\n"
        ),
        encoding="utf-8",
    )
    return override


def test_regression_startup_fails_fast_when_harness_exits_due_to_logs_permissions(
    tmp_path: Path,
    compose_files,
    build_local_images,
) -> None:
    """
    Regression guard:
    when required service startup fails (e.g., harness exits on unwritable /logs),
    stack setup should fail immediately instead of timing out waiting for "running".
    """
    root_dir = compose_files.base.parent
    stack = ComposeStack(
        root_dir=root_dir,
        temp_root=tmp_path,
        test_slug="startup-permissions-regression",
        compose_files=compose_files,
    )

    _chmod_logs_non_writable(stack.log_root)

    if _uid_1002_can_write_logs(stack.log_root, root_dir):
        pytest.skip(
            "Host bind-mount permissions do not reproduce uid-based /logs write denial in this environment."
        )

    start = time.monotonic()
    try:
        with pytest.raises(AssertionError) as exc_info:
            stack.up()
        elapsed = time.monotonic() - start
    finally:
        # Ensure tmp_path cleanup can remove the test logs directory.
        stack.log_root.chmod(0o755)
        stack.down()

    message = str(exc_info.value)
    assert elapsed < 60.0, f"Startup failure was not fail-fast (elapsed={elapsed:.1f}s)"
    assert "terminal state" in message.lower()
    assert "harness" in message
    assert "exited" in message.lower()
    assert "startup service logs:" in message.lower()
    assert "[harness]" in message
    assert (
        "/logs is not writable" in message
        or "permission denied" in message.lower()
    )


def test_regression_startup_includes_failed_collector_log_tails(
    tmp_path: Path,
    compose_files,
    build_local_images,
) -> None:
    """
    Regression guard:
    when collector fails during startup, stack diagnostics should include
    collector log tails explicitly.
    """
    root_dir = compose_files.base.parent
    collector_fail_override = _write_collector_failure_override(tmp_path)
    compose_with_failure = ComposeFiles(
        base=compose_files.base,
        overrides=compose_files.overrides + (collector_fail_override,),
    )
    stack = ComposeStack(
        root_dir=root_dir,
        temp_root=tmp_path,
        test_slug="startup-collector-logs-regression",
        compose_files=compose_with_failure,
    )

    start = time.monotonic()
    try:
        with pytest.raises(AssertionError) as exc_info:
            stack.up()
        elapsed = time.monotonic() - start
    finally:
        stack.down()

    message = str(exc_info.value)
    assert elapsed < 60.0, f"Startup failure was not fail-fast (elapsed={elapsed:.1f}s)"
    assert "terminal state" in message.lower()
    assert "collector" in message
    assert "startup service logs:" in message.lower()
    assert "[collector]" in message
    assert (
        "forced-collector-startup-failure" in message
        or "exit 13" in message.lower()
    )
