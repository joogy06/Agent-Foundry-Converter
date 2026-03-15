"""tests/test_converter_windsurf.py — Tests for the Windsurf converter."""

from pathlib import Path

from transfer_kit.converters.windsurf import (
    WORKSPACE_CHAR_LIMIT,
    WindsurfConverter,
    _enforce_char_limit,
)
from transfer_kit.models import (
    ClaudeEnvironment,
    EnvVar,
    McpServer,
    ProjectConfig,
    Skill,
)


def _empty_env(**overrides):
    defaults = dict(
        skills=[], plugins=[], mcp_servers=[], projects=[],
        global_settings={}, local_settings={},
        env_vars=[], plans=[], teams=[], keybindings=None,
    )
    defaults.update(overrides)
    return ClaudeEnvironment(**defaults)


def test_windsurf_skills_conversion():
    skill = Skill(
        name="test-skill",
        path=Path("/tmp/test"),
        content="---\nname: test\n---\nUse Glob to find files.",
        frontmatter={"name": "test"},
        source="custom",
    )
    conv = WindsurfConverter(_empty_env())
    result = conv.convert_skills([skill])
    key = ".windsurf/rules/test-skill.md"
    assert key in result
    body = result[key]
    assert "trigger: model_decision" in body
    assert "find_files" in body
    assert "Glob" not in body.split("---", 2)[-1]


def test_windsurf_project_config():
    config = ProjectConfig(
        project_path="/tmp",
        claude_md="---\ntitle: proj\n---\nUse Write to create files.",
        settings=None,
    )
    conv = WindsurfConverter(_empty_env())
    result = conv.convert_project_config(config)
    key = ".windsurf/rules/project.md"
    assert key in result
    assert "trigger: always_on" in result[key]
    assert "create_file" in result[key]


def test_windsurf_mcp_servers():
    srv = McpServer(name="redis", enabled=True, config={"command": "redis-mcp"})
    conv = WindsurfConverter(_empty_env())
    result = conv.convert_mcp_servers([srv])
    data = result["mcp_config.json"]
    assert "redis" in data["mcpServers"]


def test_windsurf_env_vars():
    vars_ = [
        EnvVar(name="SECRET_KEY", value="xxx", category="other", is_secret=True, source_file=Path("/tmp")),
        EnvVar(name="DEBUG", value="1", category="other", is_secret=False, source_file=Path("/tmp")),
    ]
    conv = WindsurfConverter(_empty_env())
    result = conv.convert_env_vars(vars_)
    assert ".env" in result
    assert "README_env.md" in result
    assert "# SECRET_KEY=<set manually>" in result[".env"]
    assert "DEBUG=1" in result[".env"]
    assert "set in your shell" in result["README_env.md"]


def test_windsurf_char_limit_enforcement():
    """Content exceeding 12 000 chars is truncated with a notice."""
    long_content = "x" * (WORKSPACE_CHAR_LIMIT + 500)
    result = _enforce_char_limit(long_content)
    assert len(result) <= WORKSPACE_CHAR_LIMIT
    assert "truncated" in result.lower()

    # Short content passes through unchanged
    short = "hello"
    assert _enforce_char_limit(short) == short
