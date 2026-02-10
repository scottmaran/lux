from __future__ import annotations

import pytest

from tests.support.integration_stack import is_heartbeat_like_signal_row, timeline_row_epoch_seconds


pytestmark = pytest.mark.unit


def test_heartbeat_filter_marks_small_idle_net_summary_as_heartbeat() -> None:
    """Low-volume net_summary keepalives are excluded from the signal clock."""
    row = {
        "ts": "2026-02-10T21:52:00.719Z",
        "source": "ebpf",
        "event_type": "net_summary",
        "details": {
            "connect_count": 0,
            "send_count": 4,
            "bytes_sent_total": 3763,
        },
    }
    assert is_heartbeat_like_signal_row(row)


def test_heartbeat_filter_keeps_meaningful_net_summary_as_signal() -> None:
    """Rows with a fresh connect or larger transfer stay in the signal clock."""
    connected_row = {
        "ts": "2026-02-10T21:41:20.895Z",
        "source": "ebpf",
        "event_type": "net_summary",
        "details": {
            "connect_count": 1,
            "send_count": 8,
            "bytes_sent_total": 28570,
        },
    }
    large_burst_row = {
        "ts": "2026-02-10T21:41:58.857Z",
        "source": "ebpf",
        "event_type": "net_summary",
        "details": {
            "connect_count": 0,
            "send_count": 11,
            "bytes_sent_total": 86109,
        },
    }
    assert not is_heartbeat_like_signal_row(connected_row)
    assert not is_heartbeat_like_signal_row(large_burst_row)


def test_timeline_row_epoch_seconds_parses_iso_timestamps() -> None:
    """ISO timestamps with Z suffix normalize into epoch seconds."""
    row = {"ts": "2026-02-10T21:53:08.005Z"}
    parsed = timeline_row_epoch_seconds(row)
    assert isinstance(parsed, float)
    assert parsed > 0


def test_timeline_row_epoch_seconds_returns_none_for_invalid_timestamp() -> None:
    """Invalid timeline timestamp strings are ignored by activity clocks."""
    assert timeline_row_epoch_seconds({"ts": "not-a-timestamp"}) is None
