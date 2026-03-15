"""transfer_kit/core/sync.py — Git repo and file copy sync."""

from __future__ import annotations

import shutil
from pathlib import Path

from git import Repo


class SyncManager:
    """Manages syncing config via git repo or file copy."""

    GITIGNORE_CONTENT = """\
# Transfer Kit — auto-generated
*.credentials.*
.credentials.json
*.secret
# Encrypted secrets are OK to commit
# .env.encrypted
"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._repo: Repo | None = None

    def init_repo(self, remote_url: str | None = None) -> Path:
        if remote_url:
            self._repo = Repo.clone_from(remote_url, str(self.repo_path))
        else:
            self.repo_path.mkdir(parents=True, exist_ok=True)
            self._repo = Repo.init(str(self.repo_path))

        gitignore = self.repo_path / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(self.GITIGNORE_CONTENT)
            self._repo.index.add([".gitignore"])
            self._repo.index.commit("Initial commit — transfer-kit sync repo")

        return self.repo_path

    def push(self, bundle_dir: Path, message: str = "sync update") -> None:
        repo = self._get_repo()
        for src in bundle_dir.rglob("*"):
            if src.is_file():
                rel = src.relative_to(bundle_dir)
                dest = self.repo_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        repo.index.add("*")
        if repo.is_dirty() or repo.untracked_files:
            repo.index.commit(message)
            if repo.remotes:
                repo.remote("origin").push()

    def pull(self) -> None:
        repo = self._get_repo()
        if repo.remotes:
            repo.remote("origin").pull()

    def copy_to(self, dest: Path, execute: bool = False, on_conflict: str = "overwrite") -> list[Path]:
        files = [
            f for f in self.repo_path.rglob("*")
            if f.is_file() and ".git" not in f.parts
        ]

        if not execute:
            return [f.relative_to(self.repo_path) for f in files]

        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in files:
            rel = src.relative_to(self.repo_path)
            target = dest / rel
            if target.exists() and on_conflict == "skip":
                continue
            if target.exists() and on_conflict == "fail":
                raise FileExistsError(f"Conflict: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied.append(target)
        return copied

    def _get_repo(self) -> Repo:
        if self._repo is None:
            self._repo = Repo(str(self.repo_path))
        return self._repo
