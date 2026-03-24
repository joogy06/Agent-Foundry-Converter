"""transfer_kit/converters/base.py — Base converter and shared utilities."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from transfer_kit.models import (
    ClaudeEnvironment,
    EnvVar,
    McpServer,
    ProjectConfig,
    Skill,
)

# ---------------------------------------------------------------------------
# Tool-name mapping: Claude Code tool → target equivalent
# ---------------------------------------------------------------------------

TOOL_MAP: dict[str, dict[str, str]] = {
    "gemini": {
        "Read": "read_file",
        "Edit": "replace",
        "Write": "write_file",
        "Bash": "run_shell_command",
        "Grep": "search_file_content",
        "Glob": "glob",
        "Agent": "codebase_investigator",
        "WebSearch": "google_web_search",
        "WebFetch": "web_fetch",
        "NotebookEdit": "NotebookEdit",
        "TaskCreate": "TaskCreate",
        "TaskUpdate": "TaskUpdate",
    },
    "copilot": {
        "Read": "readFile",
        "Edit": "editFiles",
        "Write": "createFile",
        "Bash": "runInTerminal",
        "Grep": "textSearch",
        "Glob": "fileSearch",
        "Agent": "codebase",
        "WebSearch": "fetch",
        "WebFetch": "fetch",
        "NotebookEdit": "editNotebook",
        "TaskCreate": "todos",
        "TaskUpdate": "todos",
    },
    "windsurf": {
        "Read": "read_file",
        "Edit": "edit_file",
        "Write": "create_file",
        "Bash": "terminal",
        "Grep": "search",
        "Glob": "find_files",
        "Agent": "codeium_agent",
        "WebSearch": "web_search",
        "WebFetch": "web_fetch",
        "NotebookEdit": "NotebookEdit",
        "TaskCreate": "TaskCreate",
        "TaskUpdate": "TaskUpdate",
    },
}


def rewrite_tool_references(content: str, target: str) -> str:
    """Replace Claude Code tool names with *target* equivalents.

    Only replaces tool names in specific contexts to avoid mangling English prose:
    - Backtick-wrapped: `Read` -> `read_file`
    - "the X tool" pattern: the Read tool -> the read_file tool
    - "Use X to" pattern: Use Read to -> Use read_file to
    - Function call pattern: Read( -> read_file(
    """
    mapping = TOOL_MAP.get(target, {})
    for claude_name, target_name in mapping.items():
        content = re.sub(rf"`{claude_name}`", f"`{target_name}`", content)
        content = re.sub(rf"\bthe {claude_name} tool\b", f"the {target_name} tool", content)
        content = re.sub(rf"\bUse {claude_name} to\b", f"Use {target_name} to", content)
        content = re.sub(rf"\b{claude_name}\(", f"{target_name}(", content)
    return content


def strip_frontmatter(content: str) -> str:
    """Remove leading YAML frontmatter (``---`` … ``---``) from *content*."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].lstrip("\n")
    return content


# ---------------------------------------------------------------------------
# Abstract base converter
# ---------------------------------------------------------------------------


class BaseConverter(ABC):
    """Abstract base for all target-platform converters."""

    target_name: str  # e.g. "gemini", "copilot", "windsurf"

    def __init__(self, env: ClaudeEnvironment) -> None:
        self.env = env

    # -- abstract conversion methods ----------------------------------------

    @abstractmethod
    def convert_skills(self, skills: list[Skill]) -> dict[str, Any]:
        """Return a mapping of relative file paths → file contents."""
        ...

    @abstractmethod
    def convert_project_config(self, config: ProjectConfig) -> dict[str, Any]:
        """Return a mapping of relative file paths → file contents."""
        ...

    @abstractmethod
    def convert_mcp_servers(self, servers: list[McpServer]) -> dict[str, Any]:
        """Return a mapping of relative file paths → file contents."""
        ...

    @abstractmethod
    def convert_env_vars(self, env_vars: list[EnvVar]) -> dict[str, Any]:
        """Return a mapping of relative file paths → file contents."""
        ...

    # -- orchestration helpers ----------------------------------------------

    def convert_all(
        self,
        items: ClaudeEnvironment | None = None,
    ) -> dict[str, Any]:
        """Run every converter and merge the results into one dict."""
        env = items or self.env
        results: dict[str, Any] = {}
        results.update(self.convert_skills(env.skills))
        for proj in env.projects:
            results.update(self.convert_project_config(proj))
        results.update(self.convert_mcp_servers(env.mcp_servers))
        results.update(self.convert_env_vars(env.env_vars))
        return results

    def write_output(self, output_dir: str | Path, results: dict[str, Any]) -> list[Path]:
        """Write *results* (path → content) to *output_dir* and return paths."""
        output_dir = Path(output_dir)
        written: list[Path] = []
        for relpath, content in results.items():
            dest = output_dir / relpath
            dest.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (dict, list)):
                dest.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
            else:
                dest.write_text(str(content), encoding="utf-8")
            written.append(dest)
        return written
