"""transfer_kit/env.py — Managed environment-variable block in shell profiles."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

_BLOCK_START = "# -- transfer_kit managed start --"
_BLOCK_END = "# -- transfer_kit managed end --"
_BLOCK_RE = re.compile(
    rf"^{re.escape(_BLOCK_START)}\n(.*?)\n{re.escape(_BLOCK_END)}\n?",
    re.MULTILINE | re.DOTALL,
)


class EnvManager:
    """Read / write a managed block of ``export`` lines in a shell profile."""

    def __init__(self, profile_path: str | Path) -> None:
        self.profile_path = Path(profile_path)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def render_block(env_vars: dict[str, str]) -> str:
        """Return the full managed block text (including markers)."""
        lines = [_BLOCK_START]
        for key, value in env_vars.items():
            lines.append(f'export {key}="{value}"')
        lines.append(_BLOCK_END)
        return "\n".join(lines) + "\n"

    def _read(self) -> str:
        if self.profile_path.exists():
            return self.profile_path.read_text()
        return ""

    def _backup(self) -> Path:
        """Copy the current profile to a timestamped backup file."""
        timestamp = str(int(time.time()))
        backup = self.profile_path.with_name(
            f"{self.profile_path.name}.transfer_kit_backup.{timestamp}"
        )
        shutil.copy2(self.profile_path, backup)
        return backup

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_managed_vars(self) -> dict[str, str]:
        """Parse the managed block and return its variables as a dict."""
        text = self._read()
        match = _BLOCK_RE.search(text)
        if match is None:
            return {}

        result: dict[str, str] = {}
        for line in match.group(1).splitlines():
            line = line.strip()
            if line.startswith("export "):
                rest = line[len("export "):]
                key, _, value = rest.partition("=")
                # Strip surrounding quotes
                value = value.strip('"').strip("'")
                result[key] = value
        return result

    def apply(self, env_vars: dict[str, str]) -> None:
        """Write *env_vars* into the managed block, creating a backup first.

        If the profile does not exist it will be created (no backup in that
        case, since there is nothing to back up).
        """
        block = self.render_block(env_vars)
        text = self._read()

        if self.profile_path.exists():
            self._backup()

        if _BLOCK_RE.search(text):
            text = _BLOCK_RE.sub(block, text)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += block

        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(text)

    def remove_block(self) -> None:
        """Remove the managed block from the profile (creates backup first)."""
        text = self._read()
        if not _BLOCK_RE.search(text):
            return

        self._backup()
        text = _BLOCK_RE.sub("", text)
        self.profile_path.write_text(text)
