"""tests/test_sync.py"""
from pathlib import Path
from transfer_kit.core.sync import SyncManager


def test_sync_init_creates_repo(tmp_path):
    repo_path = tmp_path / "sync_repo"
    mgr = SyncManager(repo_path)
    mgr.init_repo()
    assert (repo_path / ".git").is_dir()
    assert (repo_path / ".gitignore").exists()


def test_sync_gitignore_excludes_secrets(tmp_path):
    repo_path = tmp_path / "sync_repo"
    mgr = SyncManager(repo_path)
    mgr.init_repo()
    gitignore = (repo_path / ".gitignore").read_text()
    assert "*.credentials.*" in gitignore


def test_sync_copy_local(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "test.txt").write_text("hello")
    dest = tmp_path / "dest"
    mgr = SyncManager(src)
    copied = mgr.copy_to(dest, execute=True)
    assert (dest / "test.txt").exists()
    assert (dest / "test.txt").read_text() == "hello"


def test_sync_copy_dry_run(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "test.txt").write_text("hello")
    dest = tmp_path / "dest"
    mgr = SyncManager(src)
    files = mgr.copy_to(dest, execute=False)
    assert len(files) >= 1
    assert not dest.exists()


def test_sync_copy_skip_conflict(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "test.txt").write_text("new")
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "test.txt").write_text("existing")
    mgr = SyncManager(src)
    mgr.copy_to(dest, execute=True, on_conflict="skip")
    assert (dest / "test.txt").read_text() == "existing"
