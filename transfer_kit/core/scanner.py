"""transfer_kit/core/scanner.py — Scan ~/.claude/ and build a ClaudeEnvironment."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from transfer_kit.models import (
    ClaudeEnvironment,
    EnvVar,
    McpServer,
    Plan,
    Plugin,
    ProjectConfig,
    Skill,
    TeamConfig,
)
from transfer_kit.platform_utils import get_claude_home, get_shell_profile_paths

# Env-var prefixes that belong to the "ai_cli" category.
_AI_CLI_PREFIXES = (
    "ANTHROPIC_",
    "CLAUDE_",
    "GEMINI_",
    "GOOGLE_",
    "OPENAI_",
    "NANOBANANA_",
)

# Subset of ai_cli that is "experimental".
_EXPERIMENTAL_PREFIX = "CLAUDE_CODE_EXPERIMENTAL_"

# Suffixes that flag a var as a service credential.
_CREDENTIAL_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")

# Standard shell vars we skip when scanning profiles.
_STANDARD_VARS = frozenset({
    "PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "EDITOR", "VISUAL", "PAGER", "MANPATH", "HOSTNAME",
    "LOGNAME", "MAIL", "TMPDIR", "TZ", "DISPLAY", "XDG_CONFIG_HOME",
    "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR",
    "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
})

# Name patterns that strongly suggest the value is a secret.
_SECRET_PATTERNS = re.compile(
    r"(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY|AUTH)", re.IGNORECASE
)


class Scanner:
    """Walk a Claude home directory and produce a :class:`ClaudeEnvironment`.

    .. note:: Scanner is responsible only for the canonical ``~/.claude/`` layout.
        Foreign layouts (e.g. the ``joogy06/agent-foundry`` repo shape) are
        handled by :class:`transfer_kit.core.foundry_loader.FoundryLoader`.
        The ``root`` parameter accepted here is a *convenience alias* that
        lets callers override ``claude_home`` without reaching into
        ``platform_utils``; it does NOT change the layout semantics.
    """

    def __init__(
        self,
        claude_home: Path | None = None,
        shell_profiles: list[Path] | None = None,
        root: Path | None = None,
    ) -> None:
        # `root` is an explicit override that takes precedence over
        # `claude_home`. Both are kept because existing tests and callers
        # pass `claude_home` positionally; `root` is the spec-§6 name used
        # by new call sites (pull, tests). Behaviour when neither is set
        # is unchanged from v0.2.0.
        self.claude_home = root or claude_home or get_claude_home()
        self.shell_profiles = shell_profiles if shell_profiles is not None else get_shell_profile_paths()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def scan(self) -> ClaudeEnvironment:
        """Execute a full scan and return a populated ClaudeEnvironment."""
        global_settings = self._read_json(self.claude_home / "settings.json")
        local_settings = self._read_json(self.claude_home / "settings.local.json")
        return ClaudeEnvironment(
            skills=self._scan_skills(),
            plugins=self._scan_plugins(),
            mcp_servers=self._scan_mcp_servers(),
            projects=self._scan_projects(),
            global_settings=global_settings,
            local_settings=local_settings,
            env_vars=self._scan_env_vars(),
            plans=self._scan_plans(),
            teams=self._scan_teams(),
            keybindings=self._read_json_or_none(self.claude_home / "keybindings.json"),
            hooks=global_settings.get("hooks") or local_settings.get("hooks"),
            permissions=local_settings.get("permissions"),
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def _scan_skills(self) -> list[Skill]:
        skills_dir = self.claude_home / "skills"
        if not skills_dir.is_dir():
            return []
        skills: list[Skill] = []
        for md_file in sorted(skills_dir.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            frontmatter = self._parse_frontmatter(content)
            skills.append(
                Skill(
                    name=frontmatter.get("name", md_file.stem),
                    path=md_file,
                    content=content,
                    frontmatter=frontmatter,
                    source="custom",
                )
            )
        return skills

    # ------------------------------------------------------------------
    # Plugins
    # ------------------------------------------------------------------

    def _scan_plugins(self) -> list[Plugin]:
        installed = self._read_json(self.claude_home / "plugins" / "installed_plugins.json")
        if not installed:
            return []

        global_settings = self._read_json(self.claude_home / "settings.json")
        enabled_map: dict[str, bool] = global_settings.get("enabledPlugins", {})

        plugins: list[Plugin] = []
        for plugin_key, entries in installed.get("plugins", {}).items():
            # plugin_key is "name@marketplace"
            parts = plugin_key.rsplit("@", 1)
            name = parts[0] if len(parts) == 2 else plugin_key
            marketplace = parts[1] if len(parts) == 2 else ""

            # Use the first (most recent) entry.
            entry = entries[0] if isinstance(entries, list) and entries else {}
            plugins.append(
                Plugin(
                    name=name,
                    marketplace=marketplace,
                    version=entry.get("version", ""),
                    install_path=Path(entry.get("installPath", "")),
                    enabled=enabled_map.get(plugin_key, False),
                )
            )
        return plugins

    # ------------------------------------------------------------------
    # MCP servers
    # ------------------------------------------------------------------

    def _scan_mcp_servers(self) -> list[McpServer]:
        local = self._read_json(self.claude_home / "settings.local.json")
        enabled_names: list[str] = local.get("enabledMcpjsonServers", [])

        # Look for mcpServers definitions in both settings files.
        global_settings = self._read_json(self.claude_home / "settings.json")
        all_servers: dict[str, dict] = {}
        for settings in (global_settings, local):
            all_servers.update(settings.get("mcpServers", {}))

        servers: list[McpServer] = []
        # Include servers defined in configs.
        for name, config in all_servers.items():
            servers.append(McpServer(name=name, enabled=name in enabled_names, config=config))

        # Also include enabled names that were not found in definitions.
        defined_names = {s.name for s in servers}
        for name in enabled_names:
            if name not in defined_names:
                servers.append(McpServer(name=name, enabled=True, config={}))

        return servers

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def _scan_projects(self) -> list[ProjectConfig]:
        projects_dir = self.claude_home / "projects"
        if not projects_dir.is_dir():
            return []

        projects: list[ProjectConfig] = []
        for child in sorted(projects_dir.iterdir()):
            if not child.is_dir():
                continue
            claude_md_path = child / "CLAUDE.md"
            claude_md = claude_md_path.read_text(encoding="utf-8") if claude_md_path.is_file() else None

            settings_path = child / "settings.json"
            settings = self._read_json(settings_path) if settings_path.is_file() else None

            memory_files = sorted(child.glob("*.memory.*"))

            # Current memory directory structure
            memory_dir = child / "memory"
            if memory_dir.is_dir():
                memory_files.extend(sorted(memory_dir.rglob("*.md")))

            projects.append(
                ProjectConfig(
                    project_path=child.name,
                    claude_md=claude_md,
                    settings=settings,
                    memory_files=memory_files,
                )
            )
        return projects

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    def _scan_plans(self) -> list[Plan]:
        plans_dir = self.claude_home / "plans"
        if not plans_dir.is_dir():
            return []
        plans: list[Plan] = []
        for md_file in sorted(plans_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            plans.append(Plan(name=md_file.stem, path=md_file, content=content))
        return plans

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def _scan_teams(self) -> list[TeamConfig]:
        teams_dir = self.claude_home / "teams"
        if not teams_dir.is_dir():
            return []
        teams: list[TeamConfig] = []
        for child in sorted(teams_dir.iterdir()):
            if not child.is_dir():
                continue
            config_path = child / "config.json"
            if config_path.is_file():
                config = self._read_json(config_path)
                teams.append(TeamConfig(name=child.name, config=config))
        return teams

    # ------------------------------------------------------------------
    # Environment variables from shell profiles
    # ------------------------------------------------------------------

    def _scan_env_vars(self) -> list[EnvVar]:
        env_vars: list[EnvVar] = []
        bash_re = re.compile(
            r"""^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$"""
        )
        ps_re = re.compile(
            r"""^\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$"""
        )
        for profile in self.shell_profiles:
            if not profile.is_file():
                continue
            is_powershell = profile.suffix.lower() == ".ps1"
            active_re = ps_re if is_powershell else bash_re
            for line in profile.read_text(encoding="utf-8").splitlines():
                m = active_re.match(line.strip())
                if not m:
                    continue
                name = m.group(1)
                raw = m.group(2)
                if (raw.startswith('"') and raw.endswith('"')) or \
                   (raw.startswith("'") and raw.endswith("'")):
                    value = raw[1:-1]
                else:
                    value = raw
                if name in _STANDARD_VARS:
                    continue
                env_vars.append(
                    EnvVar(
                        name=name,
                        value=value,
                        category=self._categorize_env_var(name),
                        is_secret=self._is_secret(name),
                        source_file=profile,
                    )
                )
        return env_vars

    # ------------------------------------------------------------------
    # Categorization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _categorize_env_var(name: str) -> str:
        if name.startswith(_EXPERIMENTAL_PREFIX):
            return "experimental"
        if name.startswith(_AI_CLI_PREFIXES):
            return "ai_cli"
        for suffix in _CREDENTIAL_SUFFIXES:
            if name.endswith(suffix):
                return "service_credential"
        return "other"

    @staticmethod
    def _is_secret(name: str) -> bool:
        return bool(_SECRET_PATTERNS.search(name))

    # ------------------------------------------------------------------
    # YAML frontmatter parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_frontmatter(text: str) -> dict:
        """Extract YAML frontmatter from a markdown string."""
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            return {}
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            return {}
        raw = "".join(lines[1:end_idx])
        try:
            data = yaml.safe_load(raw)
            return data if isinstance(data, dict) else {}
        except yaml.YAMLError:
            return {}

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_json(path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _read_json_or_none(path: Path) -> dict | None:
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
