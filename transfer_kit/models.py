"""transfer_kit/models.py — Data models for Claude Code config items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class Skill:
    name: str
    path: Path
    content: str
    frontmatter: dict
    source: str  # "custom" | "plugin:<plugin_name>" | "agent"


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


# Closed-list classification for _meta files discovered by FoundryLoader.
MetaFileKind = Literal[
    "gate-script",   # gates.py, gates.sh
    "checklist",     # hard-rules-checklist.md
    "families",      # skill-families.json
    "hook",          # forge_reminder_hook.py, pause_state.py
    "claims",        # claims.py
    "audit",         # audit_spawn.py
    "trusted",       # trusted_runner.py
    "scanner",       # scan_hard_rules.py
    "other",
]


@dataclass
class MetaFile:
    """File under ``skills/_meta/`` — runtime scripts, checklists, JSON configs.

    A lightweight transit dataclass, not a full Gate/Hook domain model. Just
    enough metadata to carry the file through the pipeline and let the compat
    matrix + path rewriter make decisions by name + kind.

    Fields
    ------
    name :
        Basename of the file (e.g. ``"gates.py"``).
    path :
        Absolute or source-relative path of the file.
    content :
        Raw file content as a string. Binary files are not expected under
        ``_meta/`` — the loader reads with UTF-8; decoding errors raise.
    kind :
        Classification from :data:`MetaFileKind`. The FoundryLoader computes
        this from the filename; consumers (compat, path_rewriter) may branch
        on it.
    """

    name: str
    path: Path
    content: str
    kind: str  # runtime-validated Literal[MetaFileKind]; str for backwards-compat tooling


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
    # NEW in v0.3.0 — agent-foundry ingest support.
    # Defaults preserve v0.2.0 behaviour for all existing Scanner call sites.
    source_kind: str = "claude-home"  # "claude-home" | "agent-foundry"
    meta_files: list[MetaFile] = field(default_factory=list)
    # Raw dependency docs passthrough (agent-foundry only). Keys are basenames
    # (README.md, agent-graph.md, ...); values are raw contents.
    dependency_docs: dict = field(default_factory=dict)
