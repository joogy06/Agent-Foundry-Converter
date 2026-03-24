"""tests/test_platform_utils.py"""
from pathlib import Path
from transfer_kit.platform_utils import (
    get_os, get_claude_home, get_gemini_home, get_windsurf_config_dir,
    get_shell_profile_paths, detect_package_manager,
)


def test_get_os():
    result = get_os()
    assert result in ("linux", "darwin", "windows")


def test_get_claude_home():
    result = get_claude_home()
    assert isinstance(result, Path)
    assert result.name == ".claude"


def test_get_gemini_home():
    result = get_gemini_home()
    assert isinstance(result, Path)
    assert result.name == ".gemini"


def test_get_windsurf_config_dir():
    result = get_windsurf_config_dir()
    assert isinstance(result, Path)
    assert "codeium" in str(result)


def test_get_shell_profile_paths():
    paths = get_shell_profile_paths()
    assert isinstance(paths, list)
    import platform
    if platform.system() != "Windows":
        assert len(paths) >= 1


def test_get_shell_type_linux(monkeypatch):
    monkeypatch.setattr("transfer_kit.platform_utils.get_os", lambda: "linux")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    from transfer_kit.platform_utils import get_shell_type
    assert get_shell_type() == "zsh"

def test_get_shell_type_windows(monkeypatch):
    monkeypatch.setattr("transfer_kit.platform_utils.get_os", lambda: "windows")
    from transfer_kit.platform_utils import get_shell_type
    assert get_shell_type() == "powershell"


def test_detect_package_manager():
    result = detect_package_manager()
    assert result is None or isinstance(result, str)
