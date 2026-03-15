"""Tests for transfer_kit.core.scanner."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from transfer_kit.core.scanner import Scanner
from transfer_kit.models import ClaudeEnvironment

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude_home"


# ------------------------------------------------------------------
# Fixture: a Scanner pointing at the test fixtures
# ------------------------------------------------------------------


@pytest.fixture
def scanner(tmp_path: Path) -> Scanner:
    """Return a Scanner using the test fixtures and a synthetic shell profile."""
    profile = tmp_path / ".bashrc"
    profile.write_text(
        textwrap.dedent("""\
            export PATH="/usr/bin"
            export LANG="en_US.UTF-8"
            export ANTHROPIC_API_KEY="sk-ant-test-key"
            export OPENAI_API_KEY="sk-openai-test"
            export CLAUDE_CODE_EXPERIMENTAL_FANCY="1"
            export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI"
            export MY_CUSTOM_VAR="hello"
            export GITHUB_TOKEN="ghp_abc123"
        """),
        encoding="utf-8",
    )
    return Scanner(claude_home=FIXTURES, shell_profiles=[profile])


@pytest.fixture
def env(scanner: Scanner) -> ClaudeEnvironment:
    return scanner.scan()


# ------------------------------------------------------------------
# Full scan produces a ClaudeEnvironment
# ------------------------------------------------------------------


class TestScanReturnsClaudeEnvironment:
    def test_returns_claude_environment(self, env: ClaudeEnvironment) -> None:
        assert isinstance(env, ClaudeEnvironment)


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------


class TestSettings:
    def test_global_settings_loaded(self, env: ClaudeEnvironment) -> None:
        assert "enabledPlugins" in env.global_settings

    def test_local_settings_loaded(self, env: ClaudeEnvironment) -> None:
        assert "permissions" in env.local_settings
        assert "enabledMcpjsonServers" in env.local_settings

    def test_keybindings_is_none_when_missing(self, env: ClaudeEnvironment) -> None:
        assert env.keybindings is None


# ------------------------------------------------------------------
# Skills
# ------------------------------------------------------------------


class TestSkills:
    def test_finds_custom_skill(self, env: ClaudeEnvironment) -> None:
        assert len(env.skills) == 1
        skill = env.skills[0]
        assert skill.name == "test-skill"
        assert skill.source == "custom"

    def test_skill_frontmatter_parsed(self, env: ClaudeEnvironment) -> None:
        skill = env.skills[0]
        assert skill.frontmatter["description"] == "A test skill for unit tests"

    def test_skill_content_includes_body(self, env: ClaudeEnvironment) -> None:
        assert "Use Read to view files" in env.skills[0].content


# ------------------------------------------------------------------
# Plugins
# ------------------------------------------------------------------


class TestPlugins:
    def test_finds_installed_plugin(self, env: ClaudeEnvironment) -> None:
        assert len(env.plugins) == 1
        plugin = env.plugins[0]
        assert plugin.name == "test-plugin"
        assert plugin.marketplace == "test-marketplace"
        assert plugin.version == "1.0.0"

    def test_plugin_enabled_from_settings(self, env: ClaudeEnvironment) -> None:
        assert env.plugins[0].enabled is True


# ------------------------------------------------------------------
# MCP servers
# ------------------------------------------------------------------


class TestMcpServers:
    def test_finds_enabled_mcp_server(self, env: ClaudeEnvironment) -> None:
        assert len(env.mcp_servers) == 1
        server = env.mcp_servers[0]
        assert server.name == "test-mcp"
        assert server.enabled is True


# ------------------------------------------------------------------
# Projects
# ------------------------------------------------------------------


class TestProjects:
    def test_finds_project(self, env: ClaudeEnvironment) -> None:
        assert len(env.projects) == 1
        proj = env.projects[0]
        assert proj.project_path == "-test-project"

    def test_project_claude_md_loaded(self, env: ClaudeEnvironment) -> None:
        assert "Test Project" in env.projects[0].claude_md

    def test_project_settings_loaded(self, env: ClaudeEnvironment) -> None:
        assert env.projects[0].settings == {}


# ------------------------------------------------------------------
# Plans
# ------------------------------------------------------------------


class TestPlans:
    def test_finds_plan(self, env: ClaudeEnvironment) -> None:
        assert len(env.plans) == 1
        plan = env.plans[0]
        assert plan.name == "test-plan"
        assert "Step 1" in plan.content


# ------------------------------------------------------------------
# Teams
# ------------------------------------------------------------------


class TestTeams:
    def test_finds_team(self, env: ClaudeEnvironment) -> None:
        assert len(env.teams) == 1
        team = env.teams[0]
        assert team.name == "test-team"
        assert team.config == {"name": "test-team"}


# ------------------------------------------------------------------
# Environment variables
# ------------------------------------------------------------------


class TestEnvVars:
    def test_standard_vars_filtered(self, env: ClaudeEnvironment) -> None:
        names = {v.name for v in env.env_vars}
        assert "PATH" not in names
        assert "LANG" not in names

    def test_ai_cli_category(self, env: ClaudeEnvironment) -> None:
        anthropic = next(v for v in env.env_vars if v.name == "ANTHROPIC_API_KEY")
        assert anthropic.category == "ai_cli"
        openai_var = next(v for v in env.env_vars if v.name == "OPENAI_API_KEY")
        assert openai_var.category == "ai_cli"

    def test_experimental_category(self, env: ClaudeEnvironment) -> None:
        var = next(v for v in env.env_vars if v.name == "CLAUDE_CODE_EXPERIMENTAL_FANCY")
        assert var.category == "experimental"

    def test_service_credential_category(self, env: ClaudeEnvironment) -> None:
        var = next(v for v in env.env_vars if v.name == "AWS_SECRET_ACCESS_KEY")
        assert var.category == "service_credential"

    def test_other_category(self, env: ClaudeEnvironment) -> None:
        var = next(v for v in env.env_vars if v.name == "MY_CUSTOM_VAR")
        assert var.category == "other"

    def test_secret_detection(self, env: ClaudeEnvironment) -> None:
        anthropic = next(v for v in env.env_vars if v.name == "ANTHROPIC_API_KEY")
        assert anthropic.is_secret is True
        custom = next(v for v in env.env_vars if v.name == "MY_CUSTOM_VAR")
        assert custom.is_secret is False

    def test_github_token_is_credential_and_secret(self, env: ClaudeEnvironment) -> None:
        var = next(v for v in env.env_vars if v.name == "GITHUB_TOKEN")
        assert var.category == "service_credential"
        assert var.is_secret is True


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_claude_home(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty_claude"
        empty.mkdir()
        s = Scanner(claude_home=empty, shell_profiles=[])
        env = s.scan()
        assert env.skills == []
        assert env.plugins == []
        assert env.projects == []
        assert env.plans == []
        assert env.teams == []
        assert env.env_vars == []
        assert env.global_settings == {}
        assert env.local_settings == {}

    def test_no_shell_profiles(self) -> None:
        s = Scanner(claude_home=FIXTURES, shell_profiles=[])
        env = s.scan()
        assert env.env_vars == []

    def test_malformed_frontmatter_returns_empty(self) -> None:
        s = Scanner(claude_home=FIXTURES, shell_profiles=[])
        assert s._parse_frontmatter("no frontmatter here") == {}
        assert s._parse_frontmatter("---\n: [bad yaml\n---\n") == {}
