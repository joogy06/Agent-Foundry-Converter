"""Tests for the CLI layer."""

from pathlib import Path

from click.testing import CliRunner

from transfer_kit.cli import main


def test_cli_shows_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Transfer Kit" in result.output


def test_cli_scan_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "scan" in result.output.lower()


def test_cli_export_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["export", "--help"])
    assert result.exit_code == 0
    assert "export" in result.output.lower()


def test_cli_convert_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "--help"])
    assert result.exit_code == 0
    assert "convert" in result.output.lower()


def test_cli_prereqs_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["prereqs", "--help"])
    assert result.exit_code == 0
    assert "prereqs" in result.output.lower()


def test_cli_env_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["env", "--help"])
    assert result.exit_code == 0
    assert "env" in result.output.lower()


def test_cli_import_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["import", "--help"])
    assert result.exit_code == 0
    assert "import" in result.output.lower()


def test_cli_sync_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.output.lower()


def test_cli_compare_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["compare", "--help"])
    assert result.exit_code == 0
    assert "--source" in result.output
    assert "--target" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_import_compare_does_not_crash(tmp_path, monkeypatch):
    """import --compare should not raise AttributeError."""
    from transfer_kit.core.scanner import Scanner
    from transfer_kit.core.exporter import Exporter

    fixtures = Path(__file__).parent / "fixtures" / "claude_home"
    scanner = Scanner(claude_home=fixtures, shell_profiles=[])
    env = scanner.scan()
    bundle = tmp_path / "bundle.tar.gz"
    Exporter(env).export(bundle)

    target = tmp_path / "target_home"
    target.mkdir()

    monkeypatch.setattr("transfer_kit.platform_utils.get_claude_home", lambda: target)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--yes", "import", "--from", str(bundle), "--compare",
    ], obj={"dry_run": False, "yes": True, "verbose": False,
            "quiet": False, "no_color": False})
    assert result.exit_code == 0, f"Crashed: {result.output}\n{result.exception}"


def test_sync_push_does_not_use_extractall(tmp_path, monkeypatch):
    """sync push must use safe member-by-member extraction, not extractall."""
    import tarfile

    def blocked_extractall(self, *args, **kwargs):
        raise AssertionError("extractall() must not be called — use safe extraction")

    monkeypatch.setattr(tarfile.TarFile, "extractall", blocked_extractall)

    fixtures = Path(__file__).parent / "fixtures" / "claude_home"
    from transfer_kit.core.scanner import Scanner
    from transfer_kit.core.exporter import Exporter
    scanner = Scanner(claude_home=fixtures, shell_profiles=[])
    env = scanner.scan()

    from transfer_kit.core.sync import SyncManager
    repo = tmp_path / "repo"
    mgr = SyncManager(repo)
    mgr.init_repo()

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "push", str(repo)],
        obj={"dry_run": False, "yes": False, "verbose": False,
             "quiet": False, "no_color": True})
    assert "extractall() must not be called" not in str(result.exception or "")


def test_sync_copy_requires_to_for_execute(tmp_path):
    """sync copy --from X --execute without --to should give a usage error, not crash."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "sync", "copy", "--from", str(tmp_path), "--execute",
    ], obj={"dry_run": False, "yes": False, "verbose": False,
            "quiet": False, "no_color": False})
    assert result.exit_code != 0
    assert "TypeError" not in (result.output or "")


def test_env_show_masks_secrets(tmp_path):
    """env show should not display full secret values."""
    profile = tmp_path / ".bashrc"
    profile.write_text(
        '# -- transfer_kit managed start --\n'
        'export ANTHROPIC_API_KEY="sk-ant-secret-12345"\n'
        'export MY_SAFE_VAR="hello"\n'
        '# -- transfer_kit managed end --\n'
    )

    from unittest.mock import patch
    with patch("transfer_kit.platform_utils.get_shell_profile_paths", return_value=[profile]):
        runner = CliRunner()
        result = runner.invoke(main, ["env", "show"],
            obj={"dry_run": False, "yes": False, "verbose": False,
                 "quiet": False, "no_color": True})

    assert "sk-ant-secret-12345" not in result.output
    assert "****" in result.output
    assert "hello" in result.output


FIXTURES = Path(__file__).parent / "fixtures" / "claude_home"


def test_cli_scan_runs(monkeypatch):
    """scan command should complete without error."""
    monkeypatch.setattr("transfer_kit.platform_utils.get_claude_home", lambda: FIXTURES)
    monkeypatch.setattr("transfer_kit.core.scanner.get_claude_home", lambda: FIXTURES)
    monkeypatch.setattr("transfer_kit.core.scanner.get_shell_profile_paths", lambda: [])
    runner = CliRunner()
    result = runner.invoke(main, ["scan"],
        obj={"verbose": False, "quiet": False, "yes": False,
             "dry_run": False, "no_color": True})
    assert result.exit_code == 0, f"Failed: {result.output}\n{result.exception}"


def test_cli_export_dry_run(tmp_path, monkeypatch):
    """export --dry-run should not create files."""
    monkeypatch.setattr("transfer_kit.platform_utils.get_claude_home", lambda: FIXTURES)
    monkeypatch.setattr("transfer_kit.core.scanner.get_claude_home", lambda: FIXTURES)
    monkeypatch.setattr("transfer_kit.core.scanner.get_shell_profile_paths", lambda: [])
    output = tmp_path / "bundle.tar.gz"
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "export", "-o", str(output)],
        obj={"verbose": False, "quiet": False, "yes": False,
             "dry_run": True, "no_color": True})
    assert result.exit_code == 0
    assert not output.exists()


def test_cli_convert_dry_run(tmp_path, monkeypatch):
    """convert --dry-run should not create files."""
    monkeypatch.setattr("transfer_kit.platform_utils.get_claude_home", lambda: FIXTURES)
    monkeypatch.setattr("transfer_kit.core.scanner.get_claude_home", lambda: FIXTURES)
    monkeypatch.setattr("transfer_kit.core.scanner.get_shell_profile_paths", lambda: [])
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "convert", "--target", "gemini", "-o", str(tmp_path / "out")],
        obj={"verbose": False, "quiet": False, "yes": False,
             "dry_run": True, "no_color": True})
    assert result.exit_code == 0
