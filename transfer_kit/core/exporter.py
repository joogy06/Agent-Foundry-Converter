"""transfer_kit/core/exporter.py — Bundle a ClaudeEnvironment into a .tar.gz archive."""

from __future__ import annotations

import hashlib
import io
import json
import platform
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import transfer_kit
from transfer_kit.models import ClaudeEnvironment, EnvVar


_BUNDLE_PREFIX = "transfer_kit_bundle/"


class Exporter:
    """Serialize a :class:`ClaudeEnvironment` into a portable .tar.gz bundle."""

    def __init__(self, env: ClaudeEnvironment, include_secrets: bool = False) -> None:
        self.env = env
        self.include_secrets = include_secrets

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def export(self, output_path: str | Path, items: list[str] | None = None) -> Path:
        """Create a .tar.gz bundle at *output_path* and return its :class:`Path`.

        Parameters
        ----------
        output_path:
            Destination file path for the archive.
        items:
            Optional list of category names to include (e.g. ``["skills", "plugins"]``).
            When *None*, all non-empty categories are included.
        """
        output_path = Path(output_path)
        staged = self._stage(items)
        manifest = self._build_manifest(staged)

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # Write manifest first.
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            self._add_bytes(tar, "manifest.json", manifest_bytes)

            # Write each staged file.
            for arc_name, data in staged.items():
                self._add_bytes(tar, arc_name, data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(buf.getvalue())
        return output_path

    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------

    # Aliases so callers can use either "env" or "env_vars", "mcp" or "mcp_servers"
    _ITEM_ALIASES = {"env": "env_vars", "mcp_servers": "mcp"}

    def _stage(self, items: list[str] | None) -> dict[str, bytes]:
        """Return ``{archive_relative_path: bytes}`` for every category."""
        if items is not None:
            items = [self._ITEM_ALIASES.get(i, i) for i in items]
        staged: dict[str, bytes] = {}

        stagers: dict[str, callable] = {
            "skills": self._stage_skills,
            "plugins": self._stage_plugins,
            "settings": self._stage_settings,
            "projects": self._stage_projects,
            "mcp": self._stage_mcp,
            "env_vars": self._stage_env_vars,
            "plans": self._stage_plans,
            "teams": self._stage_teams,
            "keybindings": self._stage_keybindings,
        }

        for category, stager in stagers.items():
            if items is not None and category not in items:
                continue
            result = stager()
            if result:
                staged.update(result)

        return staged

    def _stage_skills(self) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for skill in self.env.skills:
            arc = f"skills/{skill.name}.md"
            out[arc] = skill.content.encode("utf-8")
        return out

    def _stage_plugins(self) -> dict[str, bytes]:
        if not self.env.plugins:
            return {}
        data = [
            {
                "name": p.name,
                "marketplace": p.marketplace,
                "version": p.version,
                "enabled": p.enabled,
            }
            for p in self.env.plugins
        ]
        return {"plugins.json": json.dumps(data, indent=2).encode("utf-8")}

    def _stage_settings(self) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        if self.env.global_settings:
            out["settings.json"] = json.dumps(self.env.global_settings, indent=2).encode("utf-8")
        if self.env.local_settings:
            out["settings.local.json"] = json.dumps(self.env.local_settings, indent=2).encode("utf-8")
        return out

    def _stage_projects(self) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for proj in self.env.projects:
            prefix = f"projects/{proj.project_path}"
            if proj.claude_md is not None:
                out[f"{prefix}/CLAUDE.md"] = proj.claude_md.encode("utf-8")
            if proj.settings is not None:
                out[f"{prefix}/settings.json"] = json.dumps(proj.settings, indent=2).encode("utf-8")
        return out

    def _stage_mcp(self) -> dict[str, bytes]:
        if not self.env.mcp_servers:
            return {}
        data = [
            {"name": s.name, "enabled": s.enabled, "config": s.config}
            for s in self.env.mcp_servers
        ]
        return {"mcp_servers.json": json.dumps(data, indent=2).encode("utf-8")}

    def _stage_env_vars(self) -> dict[str, bytes]:
        if not self.env.env_vars:
            return {}
        data = [self._serialize_env_var(v) for v in self.env.env_vars]
        return {"env/session_vars.json": json.dumps(data, indent=2).encode("utf-8")}

    def _stage_plans(self) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for plan in self.env.plans:
            arc = f"plans/{plan.name}.md"
            out[arc] = plan.content.encode("utf-8")
        return out

    def _stage_teams(self) -> dict[str, bytes]:
        if not self.env.teams:
            return {}
        data = [{"name": t.name, "config": t.config} for t in self.env.teams]
        return {"teams.json": json.dumps(data, indent=2).encode("utf-8")}

    def _stage_keybindings(self) -> dict[str, bytes]:
        if self.env.keybindings is None:
            return {}
        return {"keybindings.json": json.dumps(self.env.keybindings, indent=2).encode("utf-8")}

    # ------------------------------------------------------------------
    # Secret redaction
    # ------------------------------------------------------------------

    def _serialize_env_var(self, var: EnvVar) -> dict:
        value = var.value
        if var.is_secret and not self.include_secrets:
            value = f"<TRANSFER_KIT_REDACTED:{var.name}>"
        return {
            "name": var.name,
            "value": value,
            "category": var.category,
            "is_secret": var.is_secret,
            "source_file": str(var.source_file),
        }

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _build_manifest(self, staged: dict[str, bytes]) -> dict:
        checksums: dict[str, str] = {}
        for arc_name, data in staged.items():
            checksums[arc_name] = hashlib.sha256(data).hexdigest()

        # Determine which item categories are present.
        items_present: list[str] = []
        category_prefixes = {
            "skills": "skills/",
            "plugins": "plugins.json",
            "settings": "settings",
            "projects": "projects/",
            "mcp": "mcp_servers.json",
            "env_vars": "env/",
            "plans": "plans/",
            "teams": "teams.json",
            "keybindings": "keybindings.json",
        }
        for category, prefix in category_prefixes.items():
            if any(name.startswith(prefix) or name == prefix for name in staged):
                items_present.append(category)

        return {
            "bundle_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "transfer_kit_version": transfer_kit.__version__,
            "source_platform": platform.system().lower(),
            "source_hostname": platform.node(),
            "items": items_present,
            "checksums": checksums,
        }

    # ------------------------------------------------------------------
    # Tar helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name=_BUNDLE_PREFIX + name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
