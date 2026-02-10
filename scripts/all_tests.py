#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Step:
    name: str
    cmd: list[str]
    env: dict[str, str] | None = None


def run_step(step: Step) -> tuple[str, int]:
    env = dict(os.environ)
    if step.env:
        env.update(step.env)
    print(f"\n==> {step.name}")
    print("$ " + " ".join(step.cmd))
    completed = subprocess.run(step.cmd, env=env, check=False)
    return step.name, completed.returncode


def pytest_step(name: str, selection: list[str], env: dict[str, str] | None = None) -> Step:
    return Step(name=name, cmd=["uv", "run", "pytest", *selection, "-q"], env=env)


def lane_steps(lane: str, *, real_codex: bool) -> list[Step]:
    codex_env = {"LASSO_REQUIRE_REAL_CODEX": "1"} if real_codex else {"LASSO_REQUIRE_REAL_CODEX": "0"}

    unit = pytest_step("unit", ["tests/unit", "-m", "unit"])
    fixture = pytest_step("fixture", ["tests/fixture", "-m", "fixture"])
    regression = pytest_step("regression", ["tests/regression", "-m", "regression"])
    integration = pytest_step(
        "integration",
        ["tests/integration", "-m", "integration and not agent_codex_exec and not agent_codex_tui"],
    )
    stress_smoke = pytest_step("stress-smoke", ["tests/stress", "-m", "stress_smoke"])
    stress_full = pytest_step(
        "stress-full",
        ["tests/stress", "-m", "stress_full"],
        env={"LASSO_ENABLE_STRESS_FULL": "1"},
    )
    codex_exec = pytest_step(
        "agent-codex-exec",
        ["tests/integration", "-m", "agent_codex_exec"],
        env=codex_env,
    )
    codex_tui = pytest_step(
        "agent-codex-tui",
        ["tests/integration", "-m", "agent_codex_tui"],
        env=codex_env,
    )

    lanes: dict[str, list[Step]] = {
        "unit": [unit],
        "fixture": [fixture],
        "regression": [regression],
        "integration": [integration],
        "stress-smoke": [stress_smoke],
        "stress-full": [stress_full],
        "agent-codex-exec": [codex_exec],
        "agent-codex-tui": [codex_tui],
        "fast": [unit, fixture, regression],
        "pr": [unit, fixture, regression, integration, stress_smoke, codex_exec, codex_tui],
        "full": [unit, fixture, regression, integration, stress_smoke, codex_exec, codex_tui, stress_full],
    }
    return lanes[lane]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical Lasso test lane runner")
    parser.add_argument(
        "lane",
        choices=[
            "unit",
            "fixture",
            "integration",
            "regression",
            "stress-smoke",
            "stress-full",
            "agent-codex-exec",
            "agent-codex-tui",
            "fast",
            "pr",
            "full",
        ],
    )
    parser.add_argument(
        "--real-codex",
        action="store_true",
        help="Require credentialed codex lanes for agent-codex-exec and agent-codex-tui",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = lane_steps(args.lane, real_codex=args.real_codex)

    results: list[tuple[str, int]] = []
    for step in steps:
        name, code = run_step(step)
        results.append((name, code))
        if code != 0:
            break

    print("\n==> Summary")
    for name, code in results:
        status = "PASS" if code == 0 else "FAIL"
        print(f"- {name}: {status}")

    first_failure = next((code for _name, code in results if code != 0), 0)
    return first_failure


if __name__ == "__main__":
    raise SystemExit(main())
