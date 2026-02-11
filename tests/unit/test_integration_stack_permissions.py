from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.integration_stack import ComposeFiles, ComposeStack


pytestmark = pytest.mark.unit


def test_compose_stack_creates_world_writable_bind_mount_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tests.support.integration_stack.find_free_port", lambda: 18081)

    compose_base = tmp_path / "compose.yml"
    compose_base.write_text("services: {}\n", encoding="utf-8")

    stack = ComposeStack(
        root_dir=tmp_path,
        temp_root=tmp_path / "runtime",
        test_slug="perm-contract",
        compose_files=ComposeFiles(base=compose_base),
    )

    assert (stack.log_root.stat().st_mode & 0o777) == 0o777
    assert (stack.workspace_root.stat().st_mode & 0o777) == 0o777
