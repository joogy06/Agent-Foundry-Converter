"""tests/test_exporter.py — Tests for the Exporter class."""

import json
import tarfile
import tempfile
from pathlib import Path

from transfer_kit.core.exporter import Exporter
from transfer_kit.core.scanner import Scanner
from transfer_kit.models import EnvVar

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude_home"


def _scan() -> Scanner:
    return Scanner(claude_home=FIXTURES, shell_profiles=[])


def test_creates_archive():
    """Export produces a valid .tar.gz file."""
    env = _scan().scan()
    with tempfile.TemporaryDirectory() as tmp:
        out = Exporter(env).export(Path(tmp) / "bundle.tar.gz")
        assert out.exists()
        assert out.suffix == ".gz"
        assert tarfile.is_tarfile(out)


def test_contains_manifest():
    """The archive contains a manifest.json with expected keys."""
    env = _scan().scan()
    with tempfile.TemporaryDirectory() as tmp:
        out = Exporter(env).export(Path(tmp) / "bundle.tar.gz")
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("transfer_kit_bundle/manifest.json")
            assert f is not None
            manifest = json.loads(f.read())
        assert manifest["bundle_version"] == 1
        assert "created_at" in manifest
        assert "transfer_kit_version" in manifest
        assert "source_platform" in manifest
        assert "checksums" in manifest
        assert isinstance(manifest["items"], (dict, list))


def test_redacts_secrets():
    """Secret env vars are redacted by default."""
    env = _scan().scan()
    env.env_vars = [
        EnvVar(
            name="ANTHROPIC_API_KEY",
            value="sk-ant-secret-value",
            category="ai_cli",
            is_secret=True,
            source_file=Path("/home/user/.bashrc"),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Exporter(env, include_secrets=False).export(Path(tmp) / "bundle.tar.gz")
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("transfer_kit_bundle/env/session_vars.json")
            assert f is not None
            data = json.loads(f.read())
        assert len(data) == 1
        assert data[0]["value"] == "<TRANSFER_KIT_REDACTED:ANTHROPIC_API_KEY>"
        assert "sk-ant-secret-value" not in json.dumps(data)


def test_includes_secrets_when_flagged():
    """Secret env vars are included when include_secrets=True."""
    env = _scan().scan()
    env.env_vars = [
        EnvVar(
            name="ANTHROPIC_API_KEY",
            value="sk-ant-secret-value",
            category="ai_cli",
            is_secret=True,
            source_file=Path("/home/user/.bashrc"),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Exporter(env, include_secrets=True).export(Path(tmp) / "bundle.tar.gz")
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("transfer_kit_bundle/env/session_vars.json")
            assert f is not None
            data = json.loads(f.read())
        assert data[0]["value"] == "sk-ant-secret-value"
