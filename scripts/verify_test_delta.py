#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fixture.schema_validation import validate_fixture_tree


RUNTIME_PATTERNS = [
    "collector/scripts/*.py",
    "collector/config/*.yaml",
    "collector/ebpf/**",
    "harness/**",
    "agent/**",
    "compose*.yml",
    "ui/server.py",
]

TEST_PATTERNS = [
    "tests/**",
    "collector/tests/**",
]

OFFLINE_REPLAY_GUARDS = [
    "tests.fixture.helpers",
    "collector/scripts/filter_audit_logs.py",
    "collector/scripts/filter_ebpf_logs.py",
    "collector/scripts/summarize_ebpf_logs.py",
    "collector/scripts/merge_filtered_logs.py",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify test delta and architecture guardrails")
    parser.add_argument("--change-kind", choices=["feature", "fix", "refactor"], required=True)
    parser.add_argument("--base-ref", default="HEAD~1")
    parser.add_argument("--head-ref", default="HEAD")
    return parser.parse_args()


def git_changed_files(base_ref: str, head_ref: str) -> list[str]:
    candidates = [
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        ["git", "diff", "--name-only", f"{base_ref}", head_ref],
        ["git", "diff", "--name-only", head_ref],
    ]
    for cmd in candidates:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    raise RuntimeError("unable to read changed files from git diff")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    args = parse_args()
    root = ROOT
    changed = git_changed_files(args.base_ref, args.head_ref)

    failures: list[str] = []

    runtime_changed = [path for path in changed if matches_any(path, RUNTIME_PATTERNS)]
    tests_changed = [path for path in changed if matches_any(path, TEST_PATTERNS)]

    if runtime_changed and not tests_changed:
        failures.append(
            "runtime files changed without matching test updates: " + ", ".join(sorted(runtime_changed))
        )

    fixture_errors = validate_fixture_tree(root / "tests" / "fixture", root / "tests" / "fixture" / "schemas" / "case_schema.yaml")
    if fixture_errors:
        failures.extend(f"fixture schema: {error}" for error in fixture_errors)

    if args.change_kind == "fix":
        has_regression_change = any(path.startswith("tests/regression/") for path in changed)
        if not has_regression_change:
            failures.append(
                "change-kind=fix requires at least one changed file under tests/regression/"
            )

    live_test_roots = [root / "tests" / "integration", root / "tests" / "stress", root / "tests" / "regression"]
    for live_root in live_test_roots:
        if not live_root.exists():
            continue
        for path in sorted(live_root.rglob("*.py")):
            text = read_text(path)
            for guard in OFFLINE_REPLAY_GUARDS:
                if guard in text:
                    failures.append(
                        f"architecture guard: offline replay helper reference '{guard}' found in {path.relative_to(root)}"
                    )

    codex_test_files = sorted((root / "tests" / "integration").glob("*codex*.py"))
    for path in codex_test_files:
        text = read_text(path)
        if "bash -lc {prompt}" in text and "agent_codex" in text:
            failures.append(
                f"codex guard: disallowed HARNESS_RUN_CMD_TEMPLATE=bash -lc {{prompt}} usage in {path.relative_to(root)}"
            )

    integration_text = "\n".join(read_text(path) for path in sorted((root / "tests" / "integration").glob("*.py")))
    if "@pytest.mark.agent_codex_exec" not in integration_text:
        failures.append("required codex lane marker missing: @pytest.mark.agent_codex_exec")
    if "@pytest.mark.agent_codex_tui" not in integration_text:
        failures.append("required codex lane marker missing: @pytest.mark.agent_codex_tui")

    all_tests_runner = read_text(root / "scripts" / "all_tests.py")
    if "agent-codex-exec" not in all_tests_runner:
        failures.append("scripts/all_tests.py missing required lane 'agent-codex-exec'")
    if "agent-codex-tui" not in all_tests_runner:
        failures.append("scripts/all_tests.py missing required lane 'agent-codex-tui'")

    if failures:
        print("test delta verification failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("test delta verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
