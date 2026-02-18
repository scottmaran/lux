from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


ROOT_DIR = Path(__file__).resolve().parents[2]
HARNESS_PATH = ROOT_DIR / "harness" / "harness.py"


def _load_harness_module():
    spec = importlib.util.spec_from_file_location("harness_module_for_cwd_tests", HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load harness module from {HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_handle_run_rejects_relative_cwd() -> None:
    harness = _load_harness_module()
    payload = {"prompt": "hello", "cwd": "work"}
    response, status = harness.handle_run(payload)
    assert status == 400
    assert "cwd" in str(response.get("error", "")).lower()


def test_handle_run_rejects_cwd_outside_agent_workdir() -> None:
    harness = _load_harness_module()
    payload = {"prompt": "hello", "cwd": "/tmp"}
    response, status = harness.handle_run(payload)
    assert status == 400
    assert "cwd" in str(response.get("error", "")).lower()


def test_handle_run_rejects_non_string_cwd() -> None:
    harness = _load_harness_module()
    payload = {"prompt": "hello", "cwd": 123}
    response, status = harness.handle_run(payload)
    assert status == 400
    assert "cwd" in str(response.get("error", "")).lower()
