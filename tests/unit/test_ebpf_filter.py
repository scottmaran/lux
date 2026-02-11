from __future__ import annotations

import pytest

from collector.tests.test_ebpf_filter import EbpfFilterTests


pytestmark = pytest.mark.unit


class TestEbpfFilterBridge(EbpfFilterTests):
    """Collector eBPF filter unit behaviors remain covered under top-level pytest."""

