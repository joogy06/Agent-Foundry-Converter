"""transfer_kit/core/importer.py — Restore a transfer-kit bundle to a target directory."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


_BUNDLE_PREFIX = "transfer_kit_bundle/"


class Importer:
    """Read and restore a .tar.gz bundle produced by :class:`Exporter`."""

    def __init__(self, bundle_path: str | Path) -> None:
        self.bundle_path = Path(bundle_path)
        if not self.bundle_path.is_file():
            raise FileNotFoundError(f"Bundle not found: {self.bundle_path}")

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def read_manifest(self) -> dict:
        """Extract and return the manifest dict from the bundle."""
        with tarfile.open(self.bundle_path, "r:gz") as tar:
            manifest_member = tar.getmember(_BUNDLE_PREFIX + "manifest.json")
            f = tar.extractfile(manifest_member)
            if f is None:
                raise ValueError("manifest.json is not a regular file in the bundle")
            return json.loads(f.read())

    def list_items(self) -> list[str]:
        """Return the list of category names present in the bundle."""
        manifest = self.read_manifest()
        items = manifest.get("items", {})
        if isinstance(items, dict):
            return list(items.keys())
        return list(items)

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore(
        self,
        target_dir: str | Path,
        items: list[str] | None = None,
        on_conflict: str = "skip",
    ) -> list[Path]:
        """Restore bundle contents into *target_dir*.

        Returns list of files written.
        """
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest = self.read_manifest()
        checksums: dict[str, str] = manifest.get("checksums", {})

        tmpdir = Path(tempfile.mkdtemp(prefix="transfer_kit_restore_"))
        backups: list[tuple[Path, Path]] = []  # (original, backup)
        written: list[Path] = []

        try:
            # Phase 1: Extract to tempdir and verify checksums.
            with tarfile.open(self.bundle_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if not member.name.startswith(_BUNDLE_PREFIX):
                        continue
                    rel = member.name[len(_BUNDLE_PREFIX):]
                    if not rel or rel == "manifest.json":
                        continue

                    rel_path = Path(rel)
                    if ".." in rel_path.parts:
                        raise ValueError(f"Unsafe path in bundle: {member.name}")

                    # Filter by requested items.
                    if items is not None and not self._matches_items(rel, items):
                        continue

                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    data = f.read()

                    # Verify checksum.
                    expected = checksums.get(rel)
                    if expected is not None:
                        actual = hashlib.sha256(data).hexdigest()
                        if actual != expected:
                            raise ValueError(
                                f"Checksum mismatch for {rel}: "
                                f"expected {expected}, got {actual}"
                            )

                    dest = tmpdir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)

            # Phase 2: Handle conflicts and create backups.
            for tmp_file in sorted(tmpdir.rglob("*")):
                if tmp_file.is_dir():
                    continue
                rel = tmp_file.relative_to(tmpdir)
                final = target_dir / rel

                if final.exists():
                    if on_conflict == "skip":
                        continue
                    elif on_conflict == "fail":
                        raise FileExistsError(f"File already exists: {final}")
                    elif on_conflict == "overwrite":
                        backup = self._backup_file(final, target_dir)
                        backups.append((final, backup))

                # Phase 3: Atomic move from temp to final.
                final.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(tmp_file), str(final))
                written.append(final)

        except Exception:
            # Rollback: restore backups to their original locations.
            for original, backup in reversed(backups):
                if backup.exists():
                    shutil.move(str(backup), str(original))
            raise

        finally:
            if tmpdir.exists():
                shutil.rmtree(tmpdir, ignore_errors=True)

        return written

    # ------------------------------------------------------------------
    # Extract without restoring
    # ------------------------------------------------------------------

    def extract_to(self, dest_dir: str | Path) -> list[Path]:
        """Extract bundle contents to *dest_dir* without restoring.

        Returns list of extracted file paths. The caller owns *dest_dir* lifecycle.
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        manifest = self.read_manifest()
        checksums: dict[str, str] = manifest.get("checksums", {})
        extracted: list[Path] = []

        with tarfile.open(self.bundle_path, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.name.startswith(_BUNDLE_PREFIX):
                    continue
                rel = member.name[len(_BUNDLE_PREFIX):]
                if not rel or rel == "manifest.json":
                    continue

                rel_path = Path(rel)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    raise ValueError(f"Unsafe path in bundle: {member.name}")
                if member.issym() or member.islnk():
                    continue

                f = tar.extractfile(member)
                if f is None:
                    continue
                data = f.read()

                expected = checksums.get(rel)
                if expected is not None:
                    actual = hashlib.sha256(data).hexdigest()
                    if actual != expected:
                        raise ValueError(
                            f"Checksum mismatch for {rel}: expected {expected}, got {actual}"
                        )

                dest = dest_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                extracted.append(dest)

        return extracted

    # ------------------------------------------------------------------
    # Backup helper
    # ------------------------------------------------------------------

    @staticmethod
    def _backup_file(file_path: Path, target_dir: Path) -> Path:
        """Create a backup of *file_path* under ``target_dir/backups/import_<ts>/``."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup_dir = target_dir / "backups" / f"import_{ts}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        rel = file_path.relative_to(target_dir)
        backup_path = backup_dir / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(file_path), str(backup_path))
        return backup_path

    # ------------------------------------------------------------------
    # Item filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_items(rel_path: str, items: list[str]) -> bool:
        """Return True if *rel_path* belongs to one of the requested categories."""
        # Map item names to the archive path prefixes used by Exporter
        category_prefixes = {
            "skills": ("skills/",),
            "plugins": ("plugins.json",),
            "settings": ("settings.json", "settings.local.json"),
            "projects": ("projects/",),
            "mcp": ("mcp_servers.json",),
            "mcp_servers": ("mcp_servers.json",),
            "env": ("env/",),
            "env_vars": ("env/",),
            "plans": ("plans/",),
            "teams": ("teams.json",),
            "keybindings": ("keybindings.json",),
        }
        for item in items:
            prefixes = category_prefixes.get(item, ())
            for prefix in prefixes:
                if rel_path.startswith(prefix) or rel_path == prefix:
                    return True
        return False
