"""tests/test_models.py"""
from pathlib import Path
from transfer_kit.models import (
    Skill, Plugin, McpServer, ProjectConfig, EnvVar,
    Plan, TeamConfig, ClaudeEnvironment,
)


def test_skill_creation():
    s = Skill(
        name="forge",
        path=Path("/home/user/.claude/skills/forge"),
        content="# Forge skill",
        frontmatter={"name": "forge", "description": "Build things"},
        source="custom",
    )
    assert s.name == "forge"
    assert s.source == "custom"


def test_env_var_secret_detection():
    v = EnvVar(
        name="ANTHROPIC_API_KEY",
        value="sk-ant-xxx",
        category="ai_cli",
        is_secret=True,
        source_file=Path("/home/user/.bashrc"),
    )
    assert v.is_secret is True
    assert v.category == "ai_cli"


def test_claude_environment_creation():
    env = ClaudeEnvironment(
        skills=[], plugins=[], mcp_servers=[], projects=[],
        global_settings={}, local_settings={},
        env_vars=[], plans=[], teams=[], keybindings=None,
    )
    assert env.skills == []
    assert env.keybindings is None


def test_project_config_defaults():
    p = ProjectConfig(project_path="test", claude_md=None, settings=None)
    assert p.memory_files == []


def test_all_model_types():
    """Verify all model types are importable and constructable."""
    plugin = Plugin(name="test", marketplace="mp", version="1.0", install_path=Path("/tmp"), enabled=True)
    mcp = McpServer(name="test", enabled=True, config={})
    plan = Plan(name="test", path=Path("/tmp"), content="# Plan")
    team = TeamConfig(name="test", config={})
    assert plugin.enabled is True
    assert mcp.enabled is True
    assert plan.name == "test"
    assert team.name == "test"
