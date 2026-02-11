from __future__ import annotations

import pytest

@pytest.fixture
def regression_stack(docker_stack):
    """Alias to the shared isolated compose stack fixture for regression tests."""
    return docker_stack
