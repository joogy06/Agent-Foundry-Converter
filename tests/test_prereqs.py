"""tests/test_prereqs.py"""
from transfer_kit.prereqs import (
    Prerequisite,
    check_prereqs,
    get_install_hint,
)


def test_prerequisite_dataclass():
    p = Prerequisite(
        name="git",
        check_cmd="git",
        required_for="repository operations",
    )
    assert p.name == "git"
    assert p.found is False
    assert p.version is None


def test_check_prereqs_finds_python():
    results = check_prereqs(["python3"])
    assert len(results) == 1
    p = results[0]
    assert p.name == "python3"
    assert p.found is True
    assert p.version is not None


def test_get_install_hint():
    hint = get_install_hint("git", "apt")
    assert hint == "sudo apt install git"


def test_get_install_hint_unknown_manager():
    hint = get_install_hint("git", "unknown_mgr")
    assert hint is None
