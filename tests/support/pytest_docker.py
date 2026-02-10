from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.support.integration_stack import ComposeFiles, ComposeStack, run_cmd


ROOT_DIR = Path(__file__).resolve().parents[2]
COMPOSE_BASE = ROOT_DIR / "tests" / "integration" / "compose.stack.yml"


def _slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return clean[:40] or "test"


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(scope="session")
def compose_files() -> ComposeFiles:
    return ComposeFiles(base=COMPOSE_BASE)


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_available() -> None:
    run_cmd(["docker", "version"], cwd=ROOT_DIR, check=True)


@pytest.fixture(scope="session")
def build_local_images(compose_files: ComposeFiles) -> None:
    """Build local images once so integration tests run against branch code."""
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


@pytest.fixture
def docker_stack(tmp_path, request, compose_files: ComposeFiles, build_local_images) -> ComposeStack:
    stack = ComposeStack(
        root_dir=ROOT_DIR,
        temp_root=tmp_path,
        test_slug=_slugify(request.node.name),
        compose_files=compose_files,
    )
    stack.up()
    yield stack

    failed = bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)
    if failed:
        logs = stack.capture_compose_logs()
        (tmp_path / "compose_failure.log").write_text(logs, encoding="utf-8")
    stack.down()
