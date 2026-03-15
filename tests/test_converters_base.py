"""tests/test_converters_base.py — Tests for base converter utilities."""

from transfer_kit.converters.base import (
    TOOL_MAP,
    rewrite_tool_references,
    strip_frontmatter,
)


def test_tool_map_has_all_targets():
    assert set(TOOL_MAP.keys()) == {"gemini", "copilot", "windsurf"}
    for target, mapping in TOOL_MAP.items():
        assert "Read" in mapping
        assert "Bash" in mapping


def test_rewrite_tool_references_gemini():
    text = "Use the Read tool and then Bash to run a command."
    result = rewrite_tool_references(text, "gemini")
    assert "read_file" in result
    assert "run_terminal_cmd" in result
    # Original names should be gone
    assert "Read" not in result
    assert "Bash" not in result


def test_rewrite_does_not_replace_partial_words():
    text = "Reading files is fun. Use the Bash tool."
    result = rewrite_tool_references(text, "gemini")
    # "Reading" should stay untouched because the regex needs a word boundary
    assert "Reading" in result
    assert "run_terminal_cmd" in result


def test_strip_frontmatter():
    content = "---\nname: test\n---\n# Hello"
    assert strip_frontmatter(content) == "# Hello"
    # No frontmatter → content unchanged
    assert strip_frontmatter("# No FM") == "# No FM"
