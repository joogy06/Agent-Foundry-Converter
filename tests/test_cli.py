"""Tests for the CLI layer."""

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
