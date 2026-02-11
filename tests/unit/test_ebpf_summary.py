from __future__ import annotations

import pytest

from collector.tests.test_ebpf_summary import EbpfSummaryTests


pytestmark = pytest.mark.unit


class TestEbpfSummaryBridge(EbpfSummaryTests):
    """Collector eBPF summary unit behaviors remain covered under top-level pytest."""

