from __future__ import annotations

import pytest

@pytest.fixture
def stress_stack(docker_stack):
    """Alias to the shared isolated compose stack fixture for stress tests."""
    return docker_stack
