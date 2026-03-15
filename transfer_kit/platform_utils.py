"""transfer_kit/platform_utils.py — Cross-platform path resolution and OS detection."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def get_os() -> str:
    """Return normalized OS name: 'linux', 'darwin', or 'windows'."""
    return platform.system().lower()


def get_claude_home() -> Path:
    """Return path to ~/.claude/ directory."""
    return Path.home() / ".claude"


def get_gemini_home() -> Path:
    """Return path to ~/.gemini/ directory."""
    return Path.home() / ".gemini"


def get_windsurf_config_dir() -> Path:
    """Return path to Windsurf config directory."""
    if get_os() == "windows":
        return Path(os.environ.get("USERPROFILE", Path.home())) / ".codeium" / "windsurf"
    return Path.home() / ".codeium" / "windsurf"


def get_shell_profile_paths() -> list[Path]:
    """Return list of shell profile files that exist on this system."""
    home = Path.home()
    candidates: list[Path] = []

    if get_os() == "windows":
        ps_profile = home / "Documents" / "PowerShell" / "profile.ps1"
        wps_profile = home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
        candidates = [ps_profile, wps_profile]
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        if "zsh" in shell:
            candidates = [home / ".zshrc", home / ".zprofile"]
        else:
            candidates = [home / ".bashrc", home / ".bash_profile", home / ".profile"]

    return [p for p in candidates if p.exists()]


def detect_package_manager() -> str | None:
    """Detect the system package manager."""
    os_name = get_os()

    if os_name == "darwin":
        managers = ["brew", "port"]
    elif os_name == "windows":
        managers = ["choco", "scoop", "winget"]
    else:  # linux
        managers = ["apt", "dnf", "yum", "pacman", "zypper", "apk"]

    for mgr in managers:
        if shutil.which(mgr):
            return mgr
    return None
