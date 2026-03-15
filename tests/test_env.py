"""tests/test_env.py"""
from transfer_kit.env import EnvManager


def test_render_block():
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
    assert 'export MY_VAR="hello"' in text
    assert "# -- transfer_kit managed start --" in text


def test_apply_updates_existing_block(tmp_path):
    profile = tmp_path / ".bashrc"
    mgr = EnvManager(profile)

    mgr.apply({"A": "1"})
    mgr.apply({"A": "2", "B": "3"})

    text = profile.read_text()
    assert text.count("# -- transfer_kit managed start --") == 1
    assert 'export A="2"' in text
    assert 'export B="3"' in text


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


def test_backup_is_created(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("original\n")
    mgr = EnvManager(profile)

    mgr.apply({"KEY": "val"})

    backups = list(tmp_path.glob(".bashrc.transfer_kit_backup.*"))
    assert len(backups) >= 1
    assert backups[0].read_text() == "original\n"
