from __future__ import annotations

import pytest

from collector.tests.test_filter import AuditFilterTests


pytestmark = pytest.mark.unit


class TestAuditFilterBridge(AuditFilterTests):
    """Collector audit filter unit behaviors remain covered under top-level pytest."""

