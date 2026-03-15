import pytest
from pathlib import Path
from transfer_kit.models import ClaudeEnvironment

@pytest.fixture
def empty_env():
    return ClaudeEnvironment(
        skills=[], plugins=[], mcp_servers=[], projects=[],
        global_settings={}, local_settings={},
        env_vars=[], plans=[], teams=[], keybindings=None,
    )
