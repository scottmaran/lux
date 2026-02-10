from __future__ import annotations

import pytest

@pytest.fixture
def integration_stack(docker_stack):
    """Alias to the shared isolated compose stack fixture for integration tests."""
    return docker_stack
