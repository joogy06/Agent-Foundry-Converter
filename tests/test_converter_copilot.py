"""tests/test_converter_copilot.py — Tests for the Copilot converter."""

from pathlib import Path

from transfer_kit.converters.copilot import CopilotConverter
from transfer_kit.models import (
    EnvVar,
    McpServer,
    ProjectConfig,
    Skill,
)


def test_copilot_skills_conversion(empty_env):
    skill = Skill(
        name="lint",
        path=Path("/tmp/lint"),
        content="---\nname: lint\ndescription: Run linter\n---\nUse Grep to search.",
        frontmatter={"name": "lint", "description": "Run linter"},
        source="custom",
    )
    conv = CopilotConverter(empty_env)
    result = conv.convert_skills([skill])
    key = ".github/instructions/lint.instructions.md"
    assert key in result
    body = result[key]
    assert "applyTo: '**'" in body
    assert "Search" in body
    assert "Grep" not in body.split("---", 2)[-1]  # after frontmatter


def test_copilot_project_config(empty_env):
    config = ProjectConfig(
        project_path="/tmp",
        claude_md="---\ntitle: proj\n---\nUse Edit to modify files.",
        settings=None,
    )
    conv = CopilotConverter(empty_env)
    result = conv.convert_project_config(config)
    assert ".github/copilot-instructions.md" in result
    assert "EditFile" in result[".github/copilot-instructions.md"]


def test_copilot_mcp_servers(empty_env):
    srv = McpServer(name="pg", enabled=True, config={"command": "pg-mcp", "args": ["--db", "test"]})
    conv = CopilotConverter(empty_env)
    result = conv.convert_mcp_servers([srv])
    data = result[".vscode/mcp.json"]
    assert "pg" in data["servers"]
    assert data["servers"]["pg"]["type"] == "stdio"
