#!/usr/bin/env python3
"""
Guardrail script that enforces test-delta hygiene for runtime changes.

The script compares a git diff range and fails when runtime-affecting files
change without corresponding `tests/` updates. It also enforces stronger
requirements for fixes (`tests/regression/` coverage) and validates that all
fixture stages are structurally valid so CI catches broken fixture definitions
early.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.fixture.conftest import discover_cases, validate_case_structure

STAGES = ["audit_filter", "ebpf_filter", "summary", "merge", "pipeline"]

RUNTIME_PREFIXES = [
    "lux/src/",
    "install_lux.sh",
    "collector/scripts/",
    "collector/config/",
    "collector/ebpf/",
    "harness/",
    "ui/server.py",
    "compose.yml",
    "compose.ui.yml",
    "tests/integration/compose.provider.codex.override.yml",
    "agent/Dockerfile",
    "collector/Dockerfile",
    "harness/Dockerfile",
    "ui/Dockerfile",
]

LIVE_STACK_TEST_DIRS = [
    ROOT_DIR / "tests" / "integration",
    ROOT_DIR / "tests" / "stress",
    ROOT_DIR / "tests" / "regression",
]

DISALLOWED_OFFLINE_REPLAY_PATTERNS = [
    r"\brun_collector_pipeline\s*\(",
    r"\bbuild_job_fs_sequence\s*\(",
    r"\bmake_net_send_event\s*\(",
]

REQUIRED_PROVIDER_TEST_FILES: list[tuple[Path, str]] = [
    (ROOT_DIR / "tests" / "integration" / "test_agent_codex_exec.py", "agent_codex"),
    (ROOT_DIR / "tests" / "integration" / "test_agent_codex_tui.py", "agent_codex"),
    (ROOT_DIR / "tests" / "integration" / "test_agent_claude_lane.py", "agent_claude"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify required test deltas for changed code.")
    parser.add_argument("--base-ref", default="origin/main", help="Base git ref for diff")
    parser.add_argument("--head-ref", default="HEAD", help="Head git ref for diff")
    parser.add_argument(
        "--change-kind",
        required=True,
        choices=["feature", "fix", "refactor"],
        help="Type of change being validated",
    )
    return parser.parse_args()


def git_changed_files(base_ref: str, head_ref: str) -> list[str]:
    diff_range = f"{base_ref}...{head_ref}"
    cmd = ["git", "diff", "--name-only", diff_range]
    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        fallback = subprocess.run(
            ["git", "diff", "--name-only", base_ref, head_ref],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if fallback.returncode != 0:
            raise SystemExit(
                "Failed to compute git diff.\n"
                f"Primary: {' '.join(cmd)}\n{result.stderr}\n"
                f"Fallback stderr:\n{fallback.stderr}"
            )
        result = fallback
    changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if untracked.returncode == 0:
        for line in untracked.stdout.splitlines():
            line = line.strip()
            if line:
                changed.add(line)

    return sorted(changed)


def starts_with_any(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def validate_fixture_schema() -> list[str]:
    failures: list[str] = []
    for stage in STAGES:
        cases = discover_cases(stage)
        if not cases:
            failures.append(f"Fixture stage {stage} has no cases.")
            continue
        for case in cases:
            try:
                validate_case_structure(case)
            except AssertionError as exc:
                failures.append(str(exc))
    return failures


def validate_live_stack_architecture_guards() -> list[str]:
    failures: list[str] = []

    compiled = [re.compile(pattern) for pattern in DISALLOWED_OFFLINE_REPLAY_PATTERNS]
    for test_dir in LIVE_STACK_TEST_DIRS:
        if not test_dir.exists():
            continue
        for path in sorted(test_dir.rglob("test_*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in compiled:
                if pattern.search(text):
                    rel = path.relative_to(ROOT_DIR)
                    failures.append(
                        f"{rel}: uses disallowed offline replay helper matching /{pattern.pattern}/"
                    )

    for path, marker in REQUIRED_PROVIDER_TEST_FILES:
        if not path.exists():
            rel = path.relative_to(ROOT_DIR)
            failures.append(f"Missing required provider-lane test file: {rel}")
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT_DIR)
        if marker not in text:
            failures.append(f"{rel}: missing pytest marker `{marker}`.")
        if "bash -lc {prompt}" in text:
            failures.append(f"{rel}: Codex lane must not use bash run-template fallback.")

    return failures


def main() -> int:
    """
    Run the full verification flow for pre-merge/local CI checks.

    Steps:
    1. Parse CLI arguments (`base-ref`, `head-ref`, `change-kind`).
    2. Collect changed and untracked files from git.
    3. Classify paths into runtime vs tests vs regression-test changes.
    4. Apply enforcement rules:
       - runtime changes require at least one `tests/` change,
       - `change-kind=fix` requires at least one `tests/regression/` change.
    5. Validate fixture case schemas across all declared stages.
    6. Print PASS/FAIL summary and return process exit code.
    """
    args = parse_args()
    changed = git_changed_files(args.base_ref, args.head_ref)

    failures: list[str] = []
    # Guardrail intent: require tests for runtime-affecting changes.
    # Documentation changes (even if colocated under runtime dirs like `harness/`)
    # should not trigger test-delta enforcement.
    runtime_changed = [
        path
        for path in changed
        if starts_with_any(path, RUNTIME_PREFIXES) and not path.endswith(".md")
    ]
    tests_changed = [path for path in changed if path.startswith("tests/")]
    regression_changed = [path for path in changed if path.startswith("tests/regression/")]

    if runtime_changed and not tests_changed:
        failures.append(
            "Runtime code changed without any tests/ changes.\n"
            f"Runtime paths: {runtime_changed}"
        )

    if args.change_kind == "fix" and not regression_changed:
        failures.append(
            "change-kind=fix requires at least one changed file under tests/regression/."
        )

    failures.extend(validate_fixture_schema())
    failures.extend(validate_live_stack_architecture_guards())

    if failures:
        print("verify_test_delta: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("verify_test_delta: PASS")
    if changed:
        print(f"- changed files: {len(changed)}")
    else:
        print("- no changed files detected in diff range")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
