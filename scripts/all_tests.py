#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical Lasso test runner.")
    parser.add_argument(
        "--lane",
        choices=["fast", "pr", "full"],
        default="fast",
        help="Test lane to execute",
    )
    parser.add_argument(
        "--change-kind",
        choices=["feature", "fix", "refactor"],
        default="refactor",
        help="Change kind for contract enforcement checks",
    )
    parser.add_argument("--base-ref", default="origin/main", help="Base git ref for verify_test_delta")
    parser.add_argument("--head-ref", default="HEAD", help="Head git ref for verify_test_delta")
    parser.add_argument("--smoke-trials", type=int, default=3, help="Stress smoke trial count")
    parser.add_argument("--full-trials", type=int, default=15, help="Stress full trial count")
    parser.add_argument(
        "--skip-contract",
        action="store_true",
        help="Skip contract/delta verification step",
    )
    return parser.parse_args()


def run_step(cmd: list[str], *, env_overrides: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    print(f"==> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def lane_steps(args: argparse.Namespace) -> list[tuple[list[str], dict[str, str] | None]]:
    fast_steps: list[tuple[list[str], dict[str, str] | None]] = [
        (["uv", "run", "pytest", "tests/unit", "tests/fixture", "-q"], None),
        (["uv", "run", "pytest", "tests/regression", "-q"], None),
    ]
    integration_steps: list[tuple[list[str], dict[str, str] | None]] = [
        (["uv", "run", "pytest", "tests/integration", "-q"], None),
    ]
    smoke_steps: list[tuple[list[str], dict[str, str] | None]] = [
        (
            ["uv", "run", "pytest", "tests/stress", "-q"],
            {"LASSO_STRESS_TRIALS": str(args.smoke_trials)},
        ),
    ]
    full_steps: list[tuple[list[str], dict[str, str] | None]] = [
        (
            ["uv", "run", "pytest", "tests/stress", "-q"],
            {"LASSO_STRESS_TRIALS": str(args.full_trials)},
        ),
    ]

    if args.lane == "fast":
        return fast_steps
    if args.lane == "pr":
        return fast_steps + integration_steps + smoke_steps
    return fast_steps + integration_steps + smoke_steps + full_steps


def main() -> int:
    args = parse_args()
    if args.smoke_trials < 1 or args.full_trials < 1:
        raise SystemExit("smoke-trials and full-trials must be >= 1")

    run_step(["uv", "sync", "--frozen"])

    if not args.skip_contract:
        run_step(
            [
                "uv",
                "run",
                "python",
                "scripts/verify_test_delta.py",
                "--base-ref",
                args.base_ref,
                "--head-ref",
                args.head_ref,
                "--change-kind",
                args.change_kind,
            ]
        )

    for cmd, env in lane_steps(args):
        run_step(cmd, env_overrides=env)

    print(f"all_tests: PASS lane={args.lane}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

