"""transfer_kit/prereqs.py — Check for required external tools."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Prerequisite:
    name: str
    check_cmd: str
    required_for: str
    found: bool = False
    version: str | None = None


INSTALL_HINTS: dict[str, dict[str, str]] = {
    "git": {
        "apt": "sudo apt install git",
        "yum": "sudo yum install git",
        "dnf": "sudo dnf install git",
        "pacman": "sudo pacman -S git",
        "zypper": "sudo zypper install git",
        "apk": "sudo apk add git",
        "brew": "brew install git",
        "choco": "choco install git",
        "scoop": "scoop install git",
        "winget": "winget install --id Git.Git",
    },
    "python3": {
        "apt": "sudo apt install python3",
        "yum": "sudo yum install python3",
        "dnf": "sudo dnf install python3",
        "pacman": "sudo pacman -S python",
        "zypper": "sudo zypper install python3",
        "apk": "sudo apk add python3",
        "brew": "brew install python",
        "choco": "choco install python",
        "scoop": "scoop install python",
        "winget": "winget install --id Python.Python.3.12",
    },
    "node": {
        "apt": "sudo apt install nodejs",
        "yum": "sudo yum install nodejs",
        "dnf": "sudo dnf install nodejs",
        "pacman": "sudo pacman -S nodejs",
        "zypper": "sudo zypper install nodejs",
        "apk": "sudo apk add nodejs",
        "brew": "brew install node",
        "choco": "choco install nodejs",
        "scoop": "scoop install nodejs",
        "winget": "winget install --id OpenJS.NodeJS",
    },
    "rsync": {
        "apt": "sudo apt install rsync",
        "yum": "sudo yum install rsync",
        "dnf": "sudo dnf install rsync",
        "pacman": "sudo pacman -S rsync",
        "zypper": "sudo zypper install rsync",
        "apk": "sudo apk add rsync",
        "brew": "brew install rsync",
        "choco": "choco install rsync",
        "scoop": "scoop install rsync",
        "winget": "winget install --id DeltaCopy.DeltaCopy",
    },
    "gpg": {
        "apt": "sudo apt install gnupg",
        "yum": "sudo yum install gnupg2",
        "dnf": "sudo dnf install gnupg2",
        "pacman": "sudo pacman -S gnupg",
        "zypper": "sudo zypper install gpg2",
        "apk": "sudo apk add gnupg",
        "brew": "brew install gnupg",
        "choco": "choco install gpg4win",
        "scoop": "scoop install gpg",
        "winget": "winget install --id GnuPG.GnuPG",
    },
}

_VERSION_FLAGS: dict[str, list[str]] = {
    "git": ["git", "--version"],
    "python3": ["python3", "--version"],
    "node": ["node", "--version"],
    "rsync": ["rsync", "--version"],
    "gpg": ["gpg", "--version"],
}

_REQUIRED_FOR: dict[str, str] = {
    "git": "repository operations",
    "python3": "running transfer-kit",
    "node": "MCP servers and extensions",
    "rsync": "file synchronisation",
    "gpg": "encrypted export/import",
}


def _get_version(name: str) -> str | None:
    """Run the tool's version command and return the first line of output."""
    cmd = _VERSION_FLAGS.get(name)
    if cmd is None:
        return None
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5,
        )
        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
        return first_line
    except (subprocess.SubprocessError, FileNotFoundError, IndexError):
        return None


def check_prereqs(names: list[str] | None = None) -> list[Prerequisite]:
    """Check whether each named tool is available on ``$PATH``.

    Parameters
    ----------
    names:
        Tool names to check.  Defaults to all known tools when *None*.

    Returns
    -------
    list[Prerequisite]
        One entry per requested tool with *found* and *version* populated.
    """
    if names is None:
        names = list(INSTALL_HINTS.keys())

    results: list[Prerequisite] = []
    for name in names:
        found = shutil.which(name) is not None
        version = _get_version(name) if found else None
        results.append(
            Prerequisite(
                name=name,
                check_cmd=name,
                required_for=_REQUIRED_FOR.get(name, ""),
                found=found,
                version=version,
            )
        )
    return results


def get_install_hint(name: str, package_manager: str) -> str | None:
    """Return the install command for *name* using *package_manager*, or *None*."""
    tool_hints = INSTALL_HINTS.get(name)
    if tool_hints is None:
        return None
    return tool_hints.get(package_manager)
