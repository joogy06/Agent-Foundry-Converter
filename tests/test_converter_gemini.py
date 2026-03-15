"""tests/test_converter_gemini.py — Tests for the Gemini converter."""

from pathlib import Path

from transfer_kit.converters.gemini import GeminiConverter
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


def test_gemini_skills_conversion():
    skill = Skill(
        name="deploy",
        path=Path("/tmp/deploy"),
        content="---\nname: deploy\n---\nUse Read to check files.",
        frontmatter={"name": "deploy"},
        source="custom",
    )
    conv = GeminiConverter(_empty_env(skills=[skill]))
    result = conv.convert_skills([skill])
    assert "gemini-skills/deploy.md" in result
    body = result["gemini-skills/deploy.md"]
    assert "read_file" in body
    assert "Read" not in body
    assert "GEMINI-skills-index.md" in result
    assert "@import gemini-skills/deploy.md" in result["GEMINI-skills-index.md"]


def test_gemini_project_config():
    config = ProjectConfig(
        project_path="/tmp",
        claude_md="---\ntitle: proj\n---\nUse Bash for commands.",
        settings=None,
    )
    conv = GeminiConverter(_empty_env())
    result = conv.convert_project_config(config)
    assert "GEMINI.md" in result
    assert "run_terminal_cmd" in result["GEMINI.md"]
    assert "Bash" not in result["GEMINI.md"]


def test_gemini_mcp_servers():
    srv = McpServer(name="sqlite", enabled=True, config={"command": "sqlite-mcp"})
    conv = GeminiConverter(_empty_env())
    result = conv.convert_mcp_servers([srv])
    assert "gemini-settings.json" in result
    data = result["gemini-settings.json"]
    assert "sqlite" in data["mcpServers"]


def test_gemini_env_vars():
    vars_ = [
        EnvVar(name="ANTHROPIC_API_KEY", value="sk-xxx", category="ai_cli", is_secret=True, source_file=Path("/tmp")),
        EnvVar(name="GOOGLE_API_KEY", value="gk-123", category="service_credential", is_secret=True, source_file=Path("/tmp")),
    ]
    conv = GeminiConverter(_empty_env())
    result = conv.convert_env_vars(vars_)
    content = result["gemini-env.sh"]
    assert "not needed for Gemini" in content
    assert 'export GOOGLE_API_KEY="gk-123"' in content
