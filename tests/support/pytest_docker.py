from __future__ import annotations

"""
Pytest fixtures for docker-backed integration/regression/stress execution.

This module provides:
- one-time docker availability and local image builds,
- a per-test isolated default stack for CI-safe live behavior tests,
- a per-test isolated Codex stack for local credentialed agent-e2e tests.
"""

import os
import re
from pathlib import Path

import pytest

from tests.support.integration_stack import (
    DEFAULT_CODEX_EXEC_TEMPLATE,
    ComposeFiles,
    ComposeStack,
    run_cmd,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
COMPOSE_BASE = ROOT_DIR / "tests" / "integration" / "compose.stack.yml"
COMPOSE_CODEX = ROOT_DIR / "compose.codex.yml"
TEST_PROJECT_PREFIX = "lasso-test-"


def _slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return clean[:40] or "test"


def _codex_auth_path() -> Path:
    return Path.home() / ".codex" / "auth.json"


def _codex_skills_path() -> Path:
    return Path.home() / ".codex" / "skills"


def _discover_test_projects() -> list[str]:
    result = run_cmd(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=com.docker.compose.project",
            "--format",
            "{{.Label \"com.docker.compose.project\"}}",
        ],
        cwd=ROOT_DIR,
        check=False,
        timeout=30,
    )
    projects = {
        line.strip()
        for line in (result.stdout or "").splitlines()
        if line.strip().startswith(TEST_PROJECT_PREFIX)
    }
    return sorted(projects)


def _cleanup_stale_test_projects() -> None:
    for project in _discover_test_projects():
        run_cmd(
            [
                "docker",
                "compose",
                "-p",
                project,
                "-f",
                str(COMPOSE_BASE),
                "-f",
                str(COMPOSE_CODEX),
                "down",
                "-v",
                "--remove-orphans",
            ],
            cwd=ROOT_DIR,
            check=False,
            timeout=180,
        )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(scope="session")
def compose_files() -> ComposeFiles:
    return ComposeFiles(base=COMPOSE_BASE)


@pytest.fixture(scope="session")
def compose_files_codex() -> ComposeFiles:
    return ComposeFiles(base=COMPOSE_BASE, overrides=(COMPOSE_CODEX,))


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_available() -> None:
    run_cmd(["docker", "version"], cwd=ROOT_DIR, check=True)


@pytest.fixture(scope="session", autouse=True)
def cleanup_stale_test_stacks(ensure_docker_available):
    """Prevent stale lasso-test compose projects from breaking host-pid collector startup."""
    _cleanup_stale_test_projects()
    yield
    _cleanup_stale_test_projects()


@pytest.fixture(scope="session")
def build_local_images(compose_files: ComposeFiles) -> None:
    """Build local images once so docker-backed tests run branch code."""
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_files.base),
        "build",
        "collector",
        "agent",
        "harness",
    ]
    run_cmd(cmd, cwd=ROOT_DIR, check=True, timeout=1800)


@pytest.fixture(scope="session")
def ensure_codex_credentials() -> None:
    auth_path = _codex_auth_path()
    skills_path = _codex_skills_path()
    if not auth_path.is_file() or not skills_path.is_dir():
        pytest.skip(
            "Codex credentials not available at ~/.codex/auth.json and ~/.codex/skills; "
            "skipping local agent-codex tests."
        )


def _finalize_stack(stack: ComposeStack, tmp_path: Path, request) -> None:
    failed = bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)
    if failed:
        logs = stack.capture_compose_logs()
        (tmp_path / "compose_failure.log").write_text(logs, encoding="utf-8")
    stack.down()


def _bring_up_stack(stack: ComposeStack, tmp_path: Path) -> None:
    try:
        stack.up()
    except Exception:
        logs = stack.capture_compose_logs()
        (tmp_path / "compose_setup_failure.log").write_text(logs, encoding="utf-8")
        stack.down()
        raise


@pytest.fixture
def docker_stack(tmp_path, request, compose_files: ComposeFiles, build_local_images) -> ComposeStack:
    _cleanup_stale_test_projects()
    stack = ComposeStack(
        root_dir=ROOT_DIR,
        temp_root=tmp_path,
        test_slug=_slugify(request.node.name),
        compose_files=compose_files,
    )
    _bring_up_stack(stack, tmp_path)
    yield stack
    _finalize_stack(stack, tmp_path, request)


@pytest.fixture
def codex_stack(
    tmp_path,
    request,
    compose_files_codex: ComposeFiles,
    build_local_images,
    ensure_codex_credentials,
) -> ComposeStack:
    # Keep Codex command template aligned with legacy codex integration behavior.
    _cleanup_stale_test_projects()
    env_overrides = {
        "HARNESS_RUN_CMD_TEMPLATE": DEFAULT_CODEX_EXEC_TEMPLATE,
        "HOME": os.environ.get("HOME", str(Path.home())),
    }
    stack = ComposeStack(
        root_dir=ROOT_DIR,
        temp_root=tmp_path,
        test_slug=_slugify(request.node.name),
        compose_files=compose_files_codex,
        env_overrides=env_overrides,
    )
    _bring_up_stack(stack, tmp_path)
    yield stack
    _finalize_stack(stack, tmp_path, request)
