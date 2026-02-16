from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.regression


ROOT_DIR = Path(__file__).resolve().parents[2]
AUDIT_FILTER_SCRIPT = ROOT_DIR / "collector" / "scripts" / "filter_audit_logs.py"
EBPF_FILTER_SCRIPT = ROOT_DIR / "collector" / "scripts" / "filter_ebpf_logs.py"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_job_root(jobs_dir: Path, job_id: str, root_pid: int, root_sid: int) -> None:
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job_id,
        "root_pid": root_pid,
        "root_sid": root_sid,
    }
    (job_dir / "input.json").write_text(json.dumps(payload), encoding="utf-8")
    (job_dir / "status.json").write_text(json.dumps(payload), encoding="utf-8")


def _assert_precedence(module, state) -> None:
    jobs_dir = Path(state["jobs_dir"])
    sessions_dir = Path(state["sessions_dir"])
    old_job = "job_old"
    new_job = "job_new"

    _write_job_root(jobs_dir, old_job, root_pid=111, root_sid=111)
    _write_job_root(jobs_dir, new_job, root_pid=222, root_sid=222)

    run_index = module.RunIndex(str(sessions_dir), str(jobs_dir), refresh_sec=0.0)
    run_index.force_refresh()

    stale_parent_pid = 4100
    stale_root_pid = 222

    state_obj = state["state_obj"]
    state_obj.pid_to_session[stale_parent_pid] = None
    state_obj.pid_to_job[stale_parent_pid] = old_job
    state_obj.pid_to_session[stale_root_pid] = None
    state_obj.pid_to_job[stale_root_pid] = old_job

    session_id, job_id = state_obj.assign_run(
        pid=stale_root_pid,
        ppid=stale_parent_pid,
        sid=222,
        run_index=run_index,
    )
    assert session_id is None
    assert job_id == new_job
    assert state_obj.pid_to_job[stale_root_pid] == new_job

    sid_only_pid = 333
    session_id, job_id = state_obj.assign_run(
        pid=sid_only_pid,
        ppid=stale_parent_pid,
        sid=222,
        run_index=run_index,
    )
    assert session_id is None
    assert job_id == new_job
    assert state_obj.pid_to_job[sid_only_pid] == new_job


def test_audit_assign_run_prefers_pid_and_sid_roots_over_stale_parent_cache(tmp_path: Path) -> None:
    module = _load_module(AUDIT_FILTER_SCRIPT, "filter_audit_logs_regression")
    sessions_dir = tmp_path / "sessions"
    jobs_dir = tmp_path / "jobs"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    _assert_precedence(
        module,
        {
            "sessions_dir": sessions_dir,
            "jobs_dir": jobs_dir,
            "state_obj": module.FilterState(),
        },
    )


def test_ebpf_assign_run_prefers_pid_and_sid_roots_over_stale_parent_cache(tmp_path: Path) -> None:
    module = _load_module(EBPF_FILTER_SCRIPT, "filter_ebpf_logs_regression")
    sessions_dir = tmp_path / "sessions"
    jobs_dir = tmp_path / "jobs"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    _assert_precedence(
        module,
        {
            "sessions_dir": sessions_dir,
            "jobs_dir": jobs_dir,
            "state_obj": module.OwnershipState(),
        },
    )
