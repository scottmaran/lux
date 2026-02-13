from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.integration_stack import run_cmd


ROOT_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def lasso_cli_binary() -> Path:
    """Build the local `lasso` CLI binary once for integration tests that shell out to it."""
    run_cmd(["cargo", "build", "--bin", "lasso"], cwd=ROOT_DIR / "lasso", timeout=1800)
    bin_path = ROOT_DIR / "lasso" / "target" / "debug" / "lasso"
    if not bin_path.exists():
        raise AssertionError(f"Built lasso binary is missing at {bin_path}")
    return bin_path


@pytest.fixture
def integration_stack(docker_stack):
    """Alias to the shared isolated compose stack fixture for integration tests."""
    return docker_stack
