"""transfer_kit/models.py — Data models for Claude Code config items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    name: str
    path: Path
    content: str
    frontmatter: dict
    source: str  # "custom" or "plugin:<plugin_name>"


@dataclass
class Plugin:
    name: str
    marketplace: str
    version: str
    install_path: Path
    enabled: bool


@dataclass
class McpServer:
    name: str
    enabled: bool
    config: dict


@dataclass
class ProjectConfig:
    project_path: str
    claude_md: str | None
    settings: dict | None
    memory_files: list[Path] = field(default_factory=list)


@dataclass
class EnvVar:
    name: str
    value: str
    category: str  # "ai_cli" | "service_credential" | "experimental" | "other"
    is_secret: bool
    source_file: Path


@dataclass
class Plan:
    name: str
    path: Path
    content: str


@dataclass
class TeamConfig:
    name: str
    config: dict


@dataclass
class ClaudeEnvironment:
    skills: list[Skill]
    plugins: list[Plugin]
    mcp_servers: list[McpServer]
    projects: list[ProjectConfig]
    global_settings: dict
    local_settings: dict
    env_vars: list[EnvVar]
    plans: list[Plan]
    teams: list[TeamConfig]
    keybindings: dict | None
    hooks: dict | None = None
    permissions: dict | None = None
