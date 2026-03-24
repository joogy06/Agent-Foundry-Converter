"""tests/test_converter_gemini.py — Tests for the Gemini converter."""

from pathlib import Path

from transfer_kit.converters.gemini import GeminiConverter
from transfer_kit.models import (
    EnvVar,
    McpServer,
    ProjectConfig,
    Skill,
)


def test_gemini_skills_conversion(empty_env):
    skill = Skill(
        name="deploy",
        path=Path("/tmp/deploy"),
        content="---\nname: deploy\n---\nUse the `Read` tool to check files.",
        frontmatter={"name": "deploy"},
        source="custom",
    )
    empty_env.skills = [skill]
    conv = GeminiConverter(empty_env)
    result = conv.convert_skills([skill])
    assert ".gemini/skills/deploy/SKILL.md" in result
    body = result[".gemini/skills/deploy/SKILL.md"]
    assert "`read_file`" in body
    # No legacy paths or index
    assert not any(k.startswith("gemini-skills/") for k in result)
    assert not any("index" in k.lower() for k in result)


def test_gemini_project_config(empty_env):
    config = ProjectConfig(
        project_path="/tmp",
        claude_md="---\ntitle: proj\n---\nUse the `Bash` tool for commands.",
        settings=None,
    )
    conv = GeminiConverter(empty_env)
    result = conv.convert_project_config(config)
    assert "GEMINI.md" in result
    assert "`run_shell_command`" in result["GEMINI.md"]


def test_gemini_mcp_servers(empty_env):
    srv = McpServer(name="sqlite", enabled=True, config={"command": "sqlite-mcp"})
    conv = GeminiConverter(empty_env)
    result = conv.convert_mcp_servers([srv])
    assert ".gemini/settings.json" in result
    data = result[".gemini/settings.json"]
    assert "sqlite" in data["mcpServers"]


def test_gemini_env_vars(empty_env):
    vars_ = [
        EnvVar(name="ANTHROPIC_API_KEY", value="sk-xxx", category="ai_cli", is_secret=True, source_file=Path("/tmp")),
        EnvVar(name="GOOGLE_API_KEY", value="gk-123", category="service_credential", is_secret=True, source_file=Path("/tmp")),
    ]
    conv = GeminiConverter(empty_env)
    result = conv.convert_env_vars(vars_)
    content = result["gemini-env.sh"]
    assert "not needed for Gemini" in content
    assert "GOOGLE_API_KEY=<set manually>" in content
