"""transfer_kit/converters/copilot.py — Convert Claude Code config → GitHub Copilot."""

from __future__ import annotations

from typing import Any

from transfer_kit.converters.base import (
    BaseConverter,
    rewrite_tool_references,
    strip_frontmatter,
)
from transfer_kit.models import ClaudeEnvironment, EnvVar, McpServer, ProjectConfig, Skill


class CopilotConverter(BaseConverter):
    target_name = "copilot"

    # -- skills -------------------------------------------------------------

    def convert_skills(self, skills: list[Skill]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for skill in skills:
            body = strip_frontmatter(skill.content)
            body = rewrite_tool_references(body, self.target_name)
            description = skill.frontmatter.get("description", skill.name)
            # Phase A fix (design spec §17): honour per-skill applyTo from the
            # source frontmatter when present, falling back to ``'**'``. This
            # lets agent-foundry skills scope themselves to specific globs.
            apply_to = skill.frontmatter.get("applyTo", "**")
            frontmatter = (
                "---\n"
                f"name: {skill.name}\n"
                f"description: {description}\n"
                f"applyTo: '{apply_to}'\n"
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
        inputs: list[dict[str, Any]] = []

        for srv in servers:
            entry = dict(srv.config)
            if "url" in entry or "httpUrl" in entry:
                entry.setdefault("type", "sse")
            else:
                entry.setdefault("type", "stdio")
            server_entries[srv.name] = entry

        for var in self.env.env_vars:
            if var.is_secret:
                inputs.append({
                    "type": "promptString",
                    "id": var.name.lower().replace("_", "-"),
                    "description": f"{var.name} (secret)",
                    "password": True,
                })

        return {".vscode/mcp.json": {"inputs": inputs, "servers": server_entries}}

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

    # -- orchestration (multi-project merge) --------------------------------

    def convert_all(self, items: ClaudeEnvironment | None = None) -> dict[str, Any]:
        env = items or self.env
        results: dict[str, Any] = {}
        results.update(self.convert_skills(env.skills))

        # Merge multiple project configs into one file
        project_parts: list[str] = []
        for proj in env.projects:
            proj_result = self.convert_project_config(proj)
            if proj_result:
                for key, val in proj_result.items():
                    project_parts.append(val)
        if project_parts:
            results[".github/copilot-instructions.md"] = "\n\n---\n\n".join(project_parts)

        results.update(self.convert_mcp_servers(env.mcp_servers))
        results.update(self.convert_env_vars(env.env_vars))
        return results
