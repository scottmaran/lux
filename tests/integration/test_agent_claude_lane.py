from __future__ import annotations

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.agent_claude]


def test_agent_claude_lane_placeholder() -> None:
    pytest.skip(
        "agent_claude lane scaffold: add live Claude provider tests with local prerequisites."
    )
