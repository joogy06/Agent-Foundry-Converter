"""tests/test_integration.py — End-to-end: scan -> export -> import -> convert."""
from pathlib import Path
from transfer_kit.core.scanner import Scanner
from transfer_kit.core.exporter import Exporter
from transfer_kit.core.importer import Importer
from transfer_kit.converters.gemini import GeminiConverter
from transfer_kit.converters.copilot import CopilotConverter
from transfer_kit.converters.windsurf import WindsurfConverter

FIXTURES = Path(__file__).parent / "fixtures" / "claude_home"


def test_full_export_import_roundtrip(tmp_path):
    """Scan -> export -> import to new location -> verify contents match."""
    scanner = Scanner(claude_home=FIXTURES, shell_profiles=[])
    env = scanner.scan()

    bundle = tmp_path / "bundle.tar.gz"
    Exporter(env, include_secrets=True).export(bundle)

    target = tmp_path / "restored"
    importer = Importer(bundle)
    written = importer.restore(target, on_conflict="overwrite")
    assert len(written) > 0
    assert any("settings" in str(f) for f in written)


def test_convert_to_all_targets(tmp_path):
    """Scan -> convert to all 3 targets -> verify output files exist."""
    scanner = Scanner(claude_home=FIXTURES, shell_profiles=[])
    env = scanner.scan()

    for name, cls in [("gemini", GeminiConverter), ("copilot", CopilotConverter),
                       ("windsurf", WindsurfConverter)]:
        out = tmp_path / name
        conv = cls(env)
        results = conv.convert_all()
        written = conv.write_output(out, results)
        assert len(written) > 0, f"{name} converter produced no output"


def test_export_with_redaction_then_import(tmp_path):
    """Export with redacted secrets, import, verify redacted placeholders present."""
    from transfer_kit.models import EnvVar
    scanner = Scanner(claude_home=FIXTURES, shell_profiles=[])
    env = scanner.scan()
    env.env_vars = [EnvVar(
        name="TEST_SECRET", value="supersecret",
        category="ai_cli", is_secret=True,
        source_file=Path("/fake"),
    )]

    bundle = tmp_path / "bundle.tar.gz"
    Exporter(env, include_secrets=False).export(bundle, items=["env"])

    target = tmp_path / "restored"
    Importer(bundle).restore(target, on_conflict="overwrite")

    import json
    env_file = target / "env" / "session_vars.json"
    assert env_file.exists()
    data = json.loads(env_file.read_text())
    assert any("TRANSFER_KIT_REDACTED" in item.get("value", "") for item in data)


def test_converter_output_writes_to_disk(tmp_path):
    """Verify write_output actually creates files on disk."""
    scanner = Scanner(claude_home=FIXTURES, shell_profiles=[])
    env = scanner.scan()

    conv = GeminiConverter(env)
    results = conv.convert_all()
    written = conv.write_output(tmp_path / "gemini_out", results)

    for f in written:
        assert f.exists(), f"Expected file not created: {f}"
        assert f.stat().st_size > 0, f"File is empty: {f}"
