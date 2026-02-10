from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.integration


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return None
    return details.get("path")


def test_live_filter_and_merge_capture_fs_and_network_behavior(
    integration_stack,
) -> None:
    """Live submitted job produces owned fs and network artifacts in filtered outputs."""
    run_token = uuid.uuid4().hex[:8]
    target_path = f"/work/filter_merge_{run_token}.txt"
    prompt = (
        "set -euo pipefail; "
        f"printf data > {target_path}; "
        f"curl -sS -o /dev/null -w 'HTTP:%{{http_code}}' http://harness:8081/jobs/_?run={run_token} || true; "
        "sleep 3"
    )

    job_id, status = integration_stack.submit_and_wait(prompt, timeout_sec=180)
    assert status["status"] == "complete", f"job did not complete: {status}"
    assert status.get("exit_code") == 0, f"job exit code was not zero: {status}"

    timeline_rows = integration_stack.wait_for_timeline_rows(
        lambda rows: any(_details_path(row) == target_path for row in rows),
        timeout_sec=120,
        message=f"missing timeline fs row for {target_path}",
    )

    ebpf_rows = integration_stack.wait_for_jsonl_rows(
        integration_stack.filtered_ebpf_path,
        lambda rows: any(
            row.get("source") == "ebpf"
            and row.get("event_type") in {"net_connect", "net_send", "dns_query", "dns_response"}
            and run_token in str(row.get("cmd") or "")
            for row in rows
        ),
        timeout_sec=120,
        message=f"missing filtered_ebpf rows for run_token={run_token}",
    )

    observed_net_pids = {
        row.get("pid")
        for row in ebpf_rows
        if row.get("event_type") in {"net_connect", "net_send", "dns_query", "dns_response"}
        and run_token in str(row.get("cmd") or "")
    }
    observed_net_pids.discard(None)
    assert observed_net_pids, f"no observed eBPF net PID for run_token={run_token}"

    integration_stack.wait_for_timeline_rows(
        lambda rows: any(
            row.get("source") == "ebpf"
            and row.get("event_type") == "net_summary"
            and row.get("pid") in observed_net_pids
            for row in rows
        ),
        timeout_sec=120,
        message=f"missing merged net_summary row for run_token={run_token}",
    )

    assert any(
        _details_path(row) == target_path for row in timeline_rows
    ), f"timeline does not include expected fs path row for run_token={run_token}"
    assert any(
        run_token in str(row.get("cmd") or "") for row in ebpf_rows
    ), f"filtered_ebpf does not include rows for run_token={run_token}"

    # Keep this assertion focused on fs+network signal capture. Job/session ownership
    # for short-lived wrapper execs is validated more strictly in dedicated attribution tests.
