"""tests/test_env.py"""
from transfer_kit.env import EnvManager


def _expected_line(name: str, value: str) -> str:
    """Return the managed-block line that EnvManager emits for the current
    platform's default shell. On Windows `get_shell_type()` returns
    ``"powershell"`` and EnvManager writes ``$env:NAME = 'value'``;
    on POSIX it writes ``export NAME="value"``. Tests must accept either.
    """
    from transfer_kit.platform_utils import get_shell_type

    if get_shell_type() == "powershell":
        return f"$env:{name} = '{value}'"
    return f'export {name}="{value}"'


def test_render_block():
    # render_block() is a platform-neutral classmethod that always emits
    # POSIX `export` syntax regardless of host. Only `apply()` consults
    # `get_shell_type()` to switch to PowerShell. Tests for apply() use
    # `_expected_line()`; this one stays POSIX by design.
    block = EnvManager.render_block({"FOO": "bar", "BAZ": "qux"})
    assert "# -- transfer_kit managed start --" in block
    assert "# -- transfer_kit managed end --" in block
    assert 'export FOO="bar"' in block
    assert 'export BAZ="qux"' in block


def test_apply_creates_file(tmp_path):
    profile = tmp_path / ".bashrc"
    mgr = EnvManager(profile)
    mgr.apply({"MY_VAR": "hello"})

    assert profile.exists()
    text = profile.read_text()
    assert _expected_line("MY_VAR", "hello") in text
    assert "# -- transfer_kit managed start --" in text


def test_apply_updates_existing_block(tmp_path):
    profile = tmp_path / ".bashrc"
    mgr = EnvManager(profile)

    mgr.apply({"A": "1"})
    mgr.apply({"A": "2", "B": "3"})

    text = profile.read_text()
    assert text.count("# -- transfer_kit managed start --") == 1
    assert _expected_line("A", "2") in text
    assert _expected_line("B", "3") in text


def test_remove_block(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("# keep me\n")
    mgr = EnvManager(profile)

    mgr.apply({"X": "1"})
    assert "transfer_kit managed" in profile.read_text()

    mgr.remove_block()
    text = profile.read_text()
    assert "transfer_kit managed" not in text
    assert "# keep me" in text


def test_render_block_powershell():
    block = EnvManager.render_block({"MY_KEY": "hello"}, shell="powershell")
    assert "$env:MY_KEY = 'hello'" in block
    assert "export" not in block


def test_round_trip_preserves_special_chars(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("", encoding="utf-8")
    mgr = EnvManager(profile)
    original = {"TEST_VAR": 'has$dollar"and`backtick'}
    mgr.apply(original)
    result = mgr.get_managed_vars()
    assert result["TEST_VAR"] == original["TEST_VAR"]


def test_backup_is_created(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("original\n")
    mgr = EnvManager(profile)

    mgr.apply({"KEY": "val"})

    backups = list(tmp_path.glob(".bashrc.transfer_kit_backup.*"))
    assert len(backups) >= 1
    assert backups[0].read_text() == "original\n"
