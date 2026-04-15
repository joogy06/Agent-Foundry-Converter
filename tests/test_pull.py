"""tests/test_pull.py — End-to-end pull tests against the fixture."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from transfer_kit.core.pull import PullResult, run_pull, auto_detect_target


FIXTURE = Path(__file__).parent / "fixtures" / "agent_foundry"


def test_pull_happy_path_copilot_cli(tmp_path: Path) -> None:
    out = tmp_path / "out"
    err = StringIO()
    result = run_pull(str(FIXTURE), "copilot-cli", output=out, stderr=err)
    assert result.exit_code == 0
    # At least one skill file written
    assert any(p.name.endswith(".instructions.md") for p in result.files_written)
    # Shim present
    shim = out / "docs" / "agent-foundry" / "_meta" / "gates_g2_shim.py"
    assert shim.is_file()


def test_pull_idempotent(tmp_path: Path) -> None:
    out = tmp_path / "out"
    err = StringIO()
    first = run_pull(str(FIXTURE), "copilot-cli", output=out, stderr=err)
    assert first.exit_code == 0
    # Second run writes zero files.
    second = run_pull(str(FIXTURE), "copilot-cli", output=out, stderr=err)
    assert second.exit_code == 0
    assert len(second.files_written) == 0


def test_pull_dry_run_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "out"
    err = StringIO()
    result = run_pull(str(FIXTURE), "copilot-cli", output=out, dry_run=True, stderr=err)
    assert result.exit_code == 0
    # Output directory should not exist (no writes happened).
    assert not out.exists() or not any(out.rglob("*"))


def test_pull_malformed_url_exits_2(tmp_path: Path) -> None:
    err = StringIO()
    result = run_pull("not a url", "copilot-cli", output=tmp_path / "out", stderr=err)
    assert result.exit_code == 2
    assert "not a URL" in err.getvalue()


def test_pull_strips_pat_and_warns(tmp_path: Path) -> None:
    err = StringIO()
    # Use a local-ish URL that will still fail on clone but the sanitizer
    # must strip first and log the warning.
    result = run_pull("https://ghp_ABC@github.invalid/o/r",
                       "copilot-cli", output=tmp_path / "out", stderr=err)
    assert result.had_credentials is True
    assert "credentials were present" in err.getvalue()


def test_pull_auto_detect_target_from_env(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLI_VERSION", "1.0")
    assert auto_detect_target() == "copilot-cli"
    monkeypatch.delenv("COPILOT_CLI_VERSION")
    monkeypatch.setenv("GEMINI_CLI", "1.0")
    assert auto_detect_target() == "gemini"


def test_pull_auto_detect_falls_through_without_env(monkeypatch) -> None:
    # Clear all relevant vars.
    for v in ("COPILOT_CLI_VERSION", "GEMINI_CLI", "VSCODE_PID"):
        monkeypatch.delenv(v, raising=False)
    assert auto_detect_target() is None


def test_pull_force_overwrites_conflict(tmp_path: Path) -> None:
    out = tmp_path / "out"
    err = StringIO()
    # First pull to establish baseline.
    run_pull(str(FIXTURE), "copilot-cli", output=out, stderr=err)
    # Manually hand-edit one instruction file so re-pull sees a conflict.
    inst = next(out.rglob("*.instructions.md"))
    inst.write_text(inst.read_text() + "\n# manual edit")
    # Re-run with --force → must overwrite, exit 0.
    result = run_pull(str(FIXTURE), "copilot-cli", output=out, force=True, stderr=err)
    assert result.exit_code == 0
    assert "# manual edit" not in inst.read_text()


def test_pull_preserve_writes_sidecar(tmp_path: Path) -> None:
    out = tmp_path / "out"
    err = StringIO()
    run_pull(str(FIXTURE), "copilot-cli", output=out, stderr=err)
    inst = next(out.rglob("*.instructions.md"))
    inst.write_text(inst.read_text() + "\n# manual edit")
    result = run_pull(str(FIXTURE), "copilot-cli", output=out, preserve=True, stderr=err)
    assert result.exit_code == 0
    # Sidecar exists
    sidecar = inst.with_suffix(inst.suffix + ".conflict")
    assert sidecar.is_file()


def test_pull_resolve_refs_includes_transitive(tmp_path: Path) -> None:
    out = tmp_path / "out"
    err = StringIO()
    result = run_pull(
        str(FIXTURE), "copilot-cli", output=out,
        resolve_refs_flag=True, stderr=err,
    )
    assert result.exit_code == 0
