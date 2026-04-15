"""tests/test_url_sanitizer.py — sanitize_git_url tests."""

from __future__ import annotations

import pytest

from transfer_kit.core.url_sanitizer import sanitize_git_url


def test_https_url_without_credentials_passes_through() -> None:
    u, had = sanitize_git_url("https://github.com/owner/repo")
    assert u == "https://github.com/owner/repo"
    assert had is False


def test_https_pat_is_stripped() -> None:
    u, had = sanitize_git_url("https://ghp_ABC123@github.com/o/r")
    assert u == "https://github.com/o/r"
    assert had is True


def test_https_user_pass_is_stripped() -> None:
    u, had = sanitize_git_url("https://user:secret@github.com/o/r")
    assert u == "https://github.com/o/r"
    assert had is True


def test_local_path_passes_through() -> None:
    u, had = sanitize_git_url("/mnt/data/foundry")
    assert u == "/mnt/data/foundry"
    assert had is False
    u, had = sanitize_git_url("./foundry")
    assert u == "./foundry"
    assert had is False


def test_empty_url_raises() -> None:
    with pytest.raises(ValueError):
        sanitize_git_url("")


def test_malformed_url_raises() -> None:
    with pytest.raises(ValueError):
        sanitize_git_url("not a url")


def test_ssh_scp_style_passes_through() -> None:
    u, had = sanitize_git_url("git@github.com:owner/repo.git")
    assert u == "git@github.com:owner/repo.git"
    # git@ is the conventional non-credential user; we don't flag it
    assert had is False


def test_windows_drive_path_treated_as_local() -> None:
    u, had = sanitize_git_url("C:/foo/bar")
    assert u == "C:/foo/bar"
    assert had is False
