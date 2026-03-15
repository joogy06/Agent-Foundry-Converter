"""transfer_kit/converters/copilot.py — Convert Claude Code config → GitHub Copilot."""

from __future__ import annotations

import json
from typing import Any

from transfer_kit.converters.base import (
    BaseConverter,
    rewrite_tool_references,
    strip_frontmatter,
)
from transfer_kit.models import EnvVar, McpServer, ProjectConfig, Skill


class CopilotConverter(BaseConverter):
    target_name = "copilot"

    # -- skills -------------------------------------------------------------

    def convert_skills(self, skills: list[Skill]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for skill in skills:
            body = strip_frontmatter(skill.content)
            body = rewrite_tool_references(body, self.target_name)
            description = skill.frontmatter.get("description", skill.name)
            frontmatter = (
                "---\n"
                f"name: {skill.name}\n"
                f"description: {description}\n"
                "applyTo: '**'\n"
                "---\n"
            )
            rel = f".github/instructions/{skill.name}.instructions.md"
            results[rel] = frontmatter + body
        return results

    # -- project config (CLAUDE.md → copilot-instructions.md) ---------------

    def convert_project_config(self, config: ProjectConfig) -> dict[str, Any]:
        if not config.claude_md:
            return {}
        body = strip_frontmatter(config.claude_md)
        body = rewrite_tool_references(body, self.target_name)
        return {".github/copilot-instructions.md": body}

    # -- MCP servers --------------------------------------------------------

    def convert_mcp_servers(self, servers: list[McpServer]) -> dict[str, Any]:
        if not servers:
            return {}
        server_entries: dict[str, Any] = {}
        for srv in servers:
            entry = dict(srv.config)
            entry.setdefault("type", "stdio")
            server_entries[srv.name] = entry
        return {".vscode/mcp.json": {"servers": server_entries}}

    # -- env vars -----------------------------------------------------------

    def convert_env_vars(self, env_vars: list[EnvVar]) -> dict[str, Any]:
        if not env_vars:
            return {}
        lines: list[str] = []
        for var in env_vars:
            if var.is_secret:
                lines.append(f"# {var.name}=<set manually>")
            else:
                lines.append(f"{var.name}={var.value}")
        return {".env": "\n".join(lines) + "\n"}
