"""transfer_kit/converters/gemini.py — Convert Claude Code config → Gemini CLI."""

from __future__ import annotations

from typing import Any

from transfer_kit.converters.base import (
    BaseConverter,
    rewrite_tool_references,
    strip_frontmatter,
)
from transfer_kit.models import ClaudeEnvironment, EnvVar, McpServer, ProjectConfig, Skill


class GeminiConverter(BaseConverter):
    target_name = "gemini"

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
                "---\n"
            )
            rel = f".gemini/skills/{skill.name}/SKILL.md"
            results[rel] = frontmatter + body
        return results

    def convert_project_config(self, config: ProjectConfig) -> dict[str, Any]:
        if not config.claude_md:
            return {}
        body = strip_frontmatter(config.claude_md)
        body = rewrite_tool_references(body, self.target_name)
        return {"GEMINI.md": body}

    def convert_mcp_servers(self, servers: list[McpServer]) -> dict[str, Any]:
        if not servers:
            return {}
        mcp_block: dict[str, Any] = {}
        for srv in servers:
            mcp_block[srv.name] = srv.config
        return {".gemini/settings.json": {"mcpServers": mcp_block}}

    def convert_env_vars(self, env_vars: list[EnvVar]) -> dict[str, Any]:
        lines: list[str] = ["#!/usr/bin/env bash", "# Gemini environment variables", ""]
        for var in env_vars:
            if var.name.startswith("ANTHROPIC_"):
                lines.append(f"# {var.name} — not needed for Gemini")
            elif var.is_secret:
                lines.append(f"# {var.name}=<set manually>")
            else:
                lines.append(f'export {var.name}="{var.value}"')
        if not env_vars:
            return {}
        return {"gemini-env.sh": "\n".join(lines) + "\n"}

    def convert_all(self, items: ClaudeEnvironment | None = None) -> dict[str, Any]:
        env = items or self.env
        results: dict[str, Any] = {}
        results.update(self.convert_skills(env.skills))

        project_parts: list[str] = []
        for proj in env.projects:
            proj_result = self.convert_project_config(proj)
            if proj_result and "GEMINI.md" in proj_result:
                project_parts.append(proj_result["GEMINI.md"])
        if project_parts:
            results["GEMINI.md"] = "\n\n---\n\n".join(project_parts)

        results.update(self.convert_mcp_servers(env.mcp_servers))
        results.update(self.convert_env_vars(env.env_vars))
        return results
