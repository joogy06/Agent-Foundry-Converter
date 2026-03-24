"""transfer_kit/converters/windsurf.py — Convert Claude Code config → Windsurf."""

from __future__ import annotations

from typing import Any

from transfer_kit.converters.base import (
    BaseConverter,
    rewrite_tool_references,
    strip_frontmatter,
)
from transfer_kit.models import EnvVar, McpServer, ProjectConfig, Skill

WORKSPACE_CHAR_LIMIT = 12000
TRUNCATION_COMMENT = "\n\n<!-- Content truncated to fit Windsurf workspace character limit -->\n"


def _enforce_char_limit(content: str, limit: int = WORKSPACE_CHAR_LIMIT) -> str:
    """Truncate *content* to *limit* characters, appending a notice if cut."""
    if len(content) <= limit:
        return content
    cut = limit - len(TRUNCATION_COMMENT)
    return content[:cut] + TRUNCATION_COMMENT


class WindsurfConverter(BaseConverter):
    target_name = "windsurf"

    # -- skills -------------------------------------------------------------

    def convert_skills(self, skills: list[Skill]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for skill in skills:
            body = strip_frontmatter(skill.content)
            body = rewrite_tool_references(body, self.target_name)
            frontmatter = (
                "---\n"
                "trigger: model_decision\n"
                "---\n"
            )
            full = frontmatter + body
            full = _enforce_char_limit(full)
            rel = f".windsurf/rules/{skill.name}.md"
            results[rel] = full
        return results

    # -- project config (CLAUDE.md → .windsurf/rules/project.md) -----------

    def convert_project_config(self, config: ProjectConfig) -> dict[str, Any]:
        if not config.claude_md:
            return {}
        body = strip_frontmatter(config.claude_md)
        body = rewrite_tool_references(body, self.target_name)
        frontmatter = (
            "---\n"
            "trigger: always_on\n"
            "---\n"
        )
        full = frontmatter + body
        full = _enforce_char_limit(full)
        return {".windsurf/rules/project.md": full}

    # -- MCP servers --------------------------------------------------------

    def convert_mcp_servers(self, servers: list[McpServer]) -> dict[str, Any]:
        if not servers:
            return {}
        mcp_block: dict[str, Any] = {}
        for srv in servers:
            mcp_block[srv.name] = srv.config
        return {"mcp_config.json": {"mcpServers": mcp_block}}

    # -- env vars -----------------------------------------------------------

    def convert_env_vars(self, env_vars: list[EnvVar]) -> dict[str, Any]:
        if not env_vars:
            return {}
        results: dict[str, Any] = {}

        # .env file
        env_lines: list[str] = []
        for var in env_vars:
            if var.is_secret:
                env_lines.append(f"# {var.name}=<set manually>")
            else:
                env_lines.append(f"{var.name}={var.value}")
        results[".env"] = "\n".join(env_lines) + "\n"

        # README_env.md documenting manual setup
        readme_lines = [
            "# Environment Variable Setup for Windsurf\n",
            "The following environment variables require manual configuration:\n",
        ]
        for var in env_vars:
            if var.is_secret:
                readme_lines.append(f"- `{var.name}`: set in your shell or Windsurf settings")
            else:
                readme_lines.append(f"- `{var.name}`: already configured in `.env`")
        results["README_env.md"] = "\n".join(readme_lines) + "\n"

        return results
