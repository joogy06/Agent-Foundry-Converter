"""tests/test_importer.py — Tests for the Importer class."""

import json
import tempfile
from pathlib import Path

from transfer_kit.core.exporter import Exporter
from transfer_kit.core.importer import Importer
from transfer_kit.core.scanner import Scanner

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude_home"


def _make_bundle(tmp: str) -> Path:
    """Helper: scan fixtures and export a bundle into *tmp*."""
    env = Scanner(claude_home=FIXTURES, shell_profiles=[]).scan()
    return Exporter(env).export(Path(tmp) / "bundle.tar.gz")


def test_reads_manifest():
    """Importer.read_manifest() returns a dict with expected keys."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _make_bundle(tmp)
        imp = Importer(bundle)
        manifest = imp.read_manifest()
        assert manifest["bundle_version"] == 1
        assert "checksums" in manifest
        assert "items" in manifest


def test_lists_items():
    """Importer.list_items() returns category names present in the bundle."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _make_bundle(tmp)
        imp = Importer(bundle)
        items = imp.list_items()
        assert isinstance(items, list)
        assert len(items) > 0
        # The fixture has skills, plugins, settings, projects, mcp, plans, teams.
        assert "skills" in items
        assert "plans" in items


def test_restores_to_target():
    """Importer.restore() extracts files into target directory."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _make_bundle(tmp)
        target = Path(tmp) / "restored"
        target.mkdir()

        imp = Importer(bundle)
        imp.restore(target)

        # Check that skill file was restored.
        skill_file = target / "skills" / "test-skill.md"
        assert skill_file.exists()
        assert "Test Skill" in skill_file.read_text(encoding="utf-8")

        # Check that plans were restored.
        plan_file = target / "plans" / "test-plan.md"
        assert plan_file.exists()


def test_creates_backup_on_conflict():
    """When on_conflict='overwrite', existing files are backed up."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _make_bundle(tmp)
        target = Path(tmp) / "restored"
        target.mkdir()

        # First restore to create the files.
        Importer(bundle).restore(target)

        # Write a marker into an existing file so we can verify backup.
        skill_file = target / "skills" / "test-skill.md"
        original_content = skill_file.read_text(encoding="utf-8")
        skill_file.write_text("ORIGINAL_MARKER", encoding="utf-8")

        # Second restore with overwrite.
        Importer(bundle).restore(target, on_conflict="overwrite")

        # The file should have been overwritten with bundle content.
        assert skill_file.read_text(encoding="utf-8") != "ORIGINAL_MARKER"

        # A backup directory should exist.
        backups_dir = target / "backups"
        assert backups_dir.exists()
        backup_files = list(backups_dir.rglob("test-skill.md"))
        assert len(backup_files) >= 1
        assert backup_files[0].read_text(encoding="utf-8") == "ORIGINAL_MARKER"


def test_importer_rejects_absolute_path_in_tar(tmp_path):
    """Importer must reject tar members with absolute paths."""
    import io, tarfile, json

    bundle = tmp_path / "malicious.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        manifest = json.dumps({"bundle_version": 1, "items": [], "checksums": {}}).encode()
        info = tarfile.TarInfo(name="transfer_kit_bundle/manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))

        payload = b"pwned"
        info = tarfile.TarInfo(name="transfer_kit_bundle//etc/passwd")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    bundle.write_bytes(buf.getvalue())

    from transfer_kit.core.importer import Importer
    importer = Importer(bundle)
    import pytest
    # Rejection message differs by platform: on POSIX the tar member path
    # "//etc/passwd" is flagged as absolute -> "Unsafe path"; on Windows
    # "Path.is_absolute()" is False for that same string, so the importer
    # falls through to the path-escape check -> "Path escapes target
    # directory". Either rejection is correct.
    with pytest.raises(ValueError, match=r"(Unsafe path|Path escapes target directory)"):
        importer.restore(tmp_path / "target")


def test_importer_rejects_symlink_in_tar(tmp_path):
    """Importer must skip symlinks in tar."""
    import io, tarfile, json

    bundle = tmp_path / "symlink.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        manifest = json.dumps({"bundle_version": 1, "items": [], "checksums": {}}).encode()
        info = tarfile.TarInfo(name="transfer_kit_bundle/manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))

        info = tarfile.TarInfo(name="transfer_kit_bundle/evil_link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/shadow"
        tar.addfile(info)

    bundle.write_bytes(buf.getvalue())

    from transfer_kit.core.importer import Importer
    importer = Importer(bundle)
    written = importer.restore(tmp_path / "target")
    assert not any("evil_link" in str(f) for f in written)
