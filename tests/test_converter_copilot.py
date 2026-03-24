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
        content="---\nname: lint\ndescription: Run linter\n---\nUse the `Grep` tool to search.",
        frontmatter={"name": "lint", "description": "Run linter"},
        source="custom",
    )
    conv = CopilotConverter(empty_env)
    result = conv.convert_skills([skill])
    key = ".github/instructions/lint.instructions.md"
    assert key in result
    body = result[key]
    assert "applyTo: '**'" in body
    assert "`textSearch`" in body


def test_copilot_project_config(empty_env):
    config = ProjectConfig(
        project_path="/tmp",
        claude_md="---\ntitle: proj\n---\nUse the `Edit` tool to modify files.",
        settings=None,
    )
    conv = CopilotConverter(empty_env)
    result = conv.convert_project_config(config)
    assert ".github/copilot-instructions.md" in result
    assert "`editFiles`" in result[".github/copilot-instructions.md"]


def test_copilot_mcp_servers(empty_env):
    srv = McpServer(name="pg", enabled=True, config={"command": "pg-mcp", "args": ["--db", "test"]})
    conv = CopilotConverter(empty_env)
    result = conv.convert_mcp_servers([srv])
    data = result[".vscode/mcp.json"]
    assert "pg" in data["servers"]
    assert data["servers"]["pg"]["type"] == "stdio"


def test_copilot_mcp_has_inputs_for_secrets(empty_env):
    from transfer_kit.models import EnvVar
    empty_env.mcp_servers = [McpServer(name="test-mcp", enabled=True,
                                        config={"command": "node", "args": ["server.js"]})]
    empty_env.env_vars = [EnvVar(name="TEST_API_KEY", value="secret", category="ai_cli",
                                  is_secret=True, source_file=Path("/fake"))]
    conv = CopilotConverter(empty_env)
    results = conv.convert_all()
    mcp_data = results.get(".vscode/mcp.json", {})
    assert "inputs" in mcp_data
    assert "servers" in mcp_data
    assert len(mcp_data["inputs"]) >= 1


def test_copilot_multi_project_no_overwrite(empty_env):
    empty_env.projects = [
        ProjectConfig(project_path="proj-a", claude_md="# Project A", settings=None),
        ProjectConfig(project_path="proj-b", claude_md="# Project B", settings=None),
    ]
    conv = CopilotConverter(empty_env)
    results = conv.convert_all()
    copilot_instructions = results.get(".github/copilot-instructions.md", "")
    assert "Project A" in copilot_instructions
    assert "Project B" in copilot_instructions
