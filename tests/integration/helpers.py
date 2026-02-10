from __future__ import annotations

import os
from pathlib import Path


def codex_credentials_available() -> bool:
    auth = Path.home() / ".codex" / "auth.json"
    skills = Path.home() / ".codex" / "skills"
    return auth.is_file() and skills.is_dir()


def resolve_codex_mode() -> str:
    require_real = os.getenv("LASSO_REQUIRE_REAL_CODEX") == "1"
    available = codex_credentials_available()
    if require_real and not available:
        raise AssertionError(
            "LASSO_REQUIRE_REAL_CODEX=1 but ~/.codex/auth.json or ~/.codex/skills is missing"
        )
    if available and os.getenv("LASSO_FORCE_STUB_CODEX") != "1":
        return "real"
    return "stub"


def codex_exec_success_template(mode: str) -> str:
    if mode == "real":
        return "codex exec --skip-git-repo-check {prompt}"
    return "echo codex-exec-stub-success"


def codex_exec_failure_template(mode: str) -> str:
    if mode == "real":
        return "codex exec --skip-git-repo-check --model definitely-not-a-real-model {prompt}"
    return "sh -lc 'echo codex-exec-stub-failure >&2; exit 12'"


def codex_tui_success_command(mode: str, output_path: str) -> str:
    if mode == "real":
        return (
            "codex exec --skip-git-repo-check "
            f"'Create the file {output_path} with the text codex-tui-success and then print DONE.'"
        )
    return f"bash -lc \"printf 'codex-tui-success' > {output_path}; echo codex-tui-stub-success\""


def codex_tui_failure_command(mode: str) -> str:
    if mode == "real":
        return "codex --definitely-invalid-flag"
    return "bash -lc 'echo codex-tui-stub-failure >&2; exit 9'"
