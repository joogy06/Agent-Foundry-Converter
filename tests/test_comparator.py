"""tests/test_comparator.py — Tests for ConfigComparator."""
import json
from pathlib import Path

from transfer_kit.core.comparator import ConfigComparator, DiffItem


def _setup_dirs(tmp_path, source_files: dict, target_files: dict):
    """Helper: create source and target dirs with given files."""
    src = tmp_path / "source"
    tgt = tmp_path / "target"
    for base, files in [(src, source_files), (tgt, target_files)]:
        for name, content in files.items():
            f = base / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
    return src, tgt


# --- Basic comparison tests ---

def test_identical_dirs_no_diffs(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {"file.md": "# Same\nContent"},
        {"file.md": "# Same\nContent"},
    )
    comp = ConfigComparator(src, tgt)
    assert comp.compare() == []


def test_new_file_detected(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {"new.md": "# New file"},
        {},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert len(diffs) == 1
    assert diffs[0].item_type == "new"
    assert diffs[0].current is None
    assert "New file" in diffs[0].incoming


def test_removed_file_detected(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {},
        {"old.md": "# Old file"},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert len(diffs) == 1
    assert diffs[0].item_type == "removed"
    assert diffs[0].incoming is None


def test_modified_file_detected(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {"file.txt": "new content"},
        {"file.txt": "old content"},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert len(diffs) == 1
    assert diffs[0].item_type == "modified"


# --- Markdown section diffing ---

def test_markdown_section_diff(tmp_path):
    current_md = "## Skills\nOld skills\n\n## Settings\nSame settings"
    incoming_md = "## Skills\nNew skills\n\n## Settings\nSame settings"
    src, tgt = _setup_dirs(tmp_path,
        {"config.md": incoming_md},
        {"config.md": current_md},
    )
    diffs = ConfigComparator(src, tgt).compare()
    # Only Skills section should differ, Settings identical
    assert len(diffs) == 1
    assert diffs[0].section == "## Skills"
    assert "Old skills" in diffs[0].current
    assert "New skills" in diffs[0].incoming


def test_markdown_new_section(tmp_path):
    current_md = "## Skills\nExisting"
    incoming_md = "## Skills\nExisting\n\n## MCP\nNew MCP config"
    src, tgt = _setup_dirs(tmp_path,
        {"config.md": incoming_md},
        {"config.md": current_md},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert any(d.section == "## MCP" and d.item_type == "new" for d in diffs)


# --- JSON key diffing ---

def test_json_key_diff(tmp_path):
    current_json = json.dumps({"key1": "old", "key2": "same"})
    incoming_json = json.dumps({"key1": "new", "key2": "same"})
    src, tgt = _setup_dirs(tmp_path,
        {"config.json": incoming_json},
        {"config.json": current_json},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert len(diffs) == 1
    assert diffs[0].section == "key1"
    assert diffs[0].item_type == "modified"


def test_json_new_key(tmp_path):
    current_json = json.dumps({"existing": "val"})
    incoming_json = json.dumps({"existing": "val", "new_key": "new_val"})
    src, tgt = _setup_dirs(tmp_path,
        {"config.json": incoming_json},
        {"config.json": current_json},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert len(diffs) == 1
    assert diffs[0].section == "new_key"
    assert diffs[0].item_type == "new"


# --- Env var diffing ---

def test_env_var_diff(tmp_path):
    current_env = 'export KEY1="old"\nexport KEY2="same"'
    incoming_env = 'export KEY1="new"\nexport KEY2="same"'
    src, tgt = _setup_dirs(tmp_path,
        {"vars.sh": incoming_env},
        {"vars.sh": current_env},
    )
    diffs = ConfigComparator(src, tgt).compare()
    assert len(diffs) == 1
    assert diffs[0].section == "KEY1"


# --- Apply selections ---

def test_apply_incoming_selection(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {"file.txt": "incoming content"},
        {"file.txt": "current content"},
    )
    comp = ConfigComparator(src, tgt)
    diffs = comp.compare()
    written = comp.apply_selections(diffs, {0: "incoming"})
    assert len(written) == 1
    assert (tgt / "file.txt").read_text() == "incoming content"


def test_apply_keep_selection(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {"file.txt": "incoming content"},
        {"file.txt": "current content"},
    )
    comp = ConfigComparator(src, tgt)
    diffs = comp.compare()
    written = comp.apply_selections(diffs, {0: "keep"})
    assert len(written) == 0
    assert (tgt / "file.txt").read_text() == "current content"


def test_apply_creates_backup(tmp_path):
    src, tgt = _setup_dirs(tmp_path,
        {"file.txt": "new"},
        {"file.txt": "old"},
    )
    comp = ConfigComparator(src, tgt)
    diffs = comp.compare()
    comp.apply_selections(diffs, {0: "incoming"})
    backups = list((tgt / "backups").rglob("file.txt"))
    assert len(backups) == 1
    assert backups[0].read_text() == "old"


def test_apply_json_partial_merge(tmp_path):
    current = json.dumps({"keep_this": "a", "replace_this": "old", "untouched": "x"})
    incoming = json.dumps({"keep_this": "b", "replace_this": "new", "untouched": "x"})
    src, tgt = _setup_dirs(tmp_path,
        {"config.json": incoming},
        {"config.json": current},
    )
    comp = ConfigComparator(src, tgt)
    diffs = comp.compare()
    # Find indices for each key
    selections = {}
    for i, d in enumerate(diffs):
        if d.section == "keep_this":
            selections[i] = "keep"
        elif d.section == "replace_this":
            selections[i] = "incoming"

    comp.apply_selections(diffs, selections)
    result = json.loads((tgt / "config.json").read_text())
    assert result["keep_this"] == "a"       # kept current
    assert result["replace_this"] == "new"  # used incoming
    assert result["untouched"] == "x"       # unchanged
