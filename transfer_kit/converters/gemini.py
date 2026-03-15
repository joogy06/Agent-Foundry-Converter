"""transfer_kit/converters/gemini.py — Convert Claude Code config → Gemini."""

from __future__ import annotations

import json
from typing import Any

from transfer_kit.converters.base import (
    BaseConverter,
    rewrite_tool_references,
    strip_frontmatter,
)
from transfer_kit.models import EnvVar, McpServer, ProjectConfig, Skill


class GeminiConverter(BaseConverter):
    target_name = "gemini"

    # -- skills -------------------------------------------------------------

    def convert_skills(self, skills: list[Skill]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        index_lines: list[str] = ["# Gemini Skills Index\n"]

        for skill in skills:
            body = strip_frontmatter(skill.content)
            body = rewrite_tool_references(body, self.target_name)
            rel = f"gemini-skills/{skill.name}.md"
            results[rel] = body
            index_lines.append(f"@import {rel}")

        if skills:
            results["GEMINI-skills-index.md"] = "\n".join(index_lines) + "\n"

        return results

    # -- project config (CLAUDE.md → GEMINI.md) -----------------------------

    def convert_project_config(self, config: ProjectConfig) -> dict[str, Any]:
        if not config.claude_md:
            return {}
        body = strip_frontmatter(config.claude_md)
        body = rewrite_tool_references(body, self.target_name)
        return {"GEMINI.md": body}

    # -- MCP servers --------------------------------------------------------

    def convert_mcp_servers(self, servers: list[McpServer]) -> dict[str, Any]:
        if not servers:
            return {}
        mcp_block: dict[str, Any] = {}
        for srv in servers:
            mcp_block[srv.name] = srv.config
        return {"gemini-settings.json": {"mcpServers": mcp_block}}

    # -- env vars -----------------------------------------------------------

    def convert_env_vars(self, env_vars: list[EnvVar]) -> dict[str, Any]:
        lines: list[str] = ["#!/usr/bin/env bash", "# Gemini environment variables\n"]
        for var in env_vars:
            if var.name.startswith("ANTHROPIC_"):
                lines.append(f"# {var.name} — not needed for Gemini")
            elif var.name.startswith(("GEMINI_", "GOOGLE_")):
                lines.append(f'export {var.name}="{var.value}"')
            else:
                lines.append(f'export {var.name}="{var.value}"')
        if not env_vars:
            return {}
        return {"gemini-env.sh": "\n".join(lines) + "\n"}
