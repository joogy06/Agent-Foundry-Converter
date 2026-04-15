"""tests/test_converters_base.py — Tests for base converter utilities."""

from transfer_kit.converters.base import (
    TOOL_MAP,
    rewrite_tool_references,
    strip_frontmatter,
)


def test_tool_map_has_all_targets():
    assert set(TOOL_MAP.keys()) == {"gemini", "copilot", "copilot-cli", "windsurf"}
    for target, mapping in TOOL_MAP.items():
        assert "Read" in mapping
        assert "Bash" in mapping
        assert "WebSearch" in mapping, f"{target} missing WebSearch"
        assert "WebFetch" in mapping, f"{target} missing WebFetch"


def test_copilot_cli_tool_map_preserves_bash():
    """Copilot CLI has a native Bash; keep the Bash tool as-is (lowercase)."""
    c = TOOL_MAP["copilot-cli"]
    assert c["Bash"] == "bash"
    assert c["Read"] == "read_file"
    assert c["Grep"] == "grep"
    assert c["Glob"] == "find"


def test_gemini_tool_names_correct():
    g = TOOL_MAP["gemini"]
    assert g["Read"] == "read_file"
    assert g["Edit"] == "replace"
    assert g["Write"] == "write_file"
    assert g["Bash"] == "run_shell_command"
    assert g["Grep"] == "search_file_content"
    assert g["Glob"] == "glob"


def test_copilot_tool_names_correct():
    c = TOOL_MAP["copilot"]
    assert c["Read"] == "readFile"
    assert c["Edit"] == "editFiles"
    assert c["Write"] == "createFile"
    assert c["Bash"] == "runInTerminal"
    assert c["Grep"] == "textSearch"
    assert c["Glob"] == "fileSearch"


def test_rewrite_tool_references_gemini():
    text = "Use the `Read` tool and `Bash` to run a command."
    result = rewrite_tool_references(text, "gemini")
    assert "`read_file`" in result
    assert "`run_shell_command`" in result


def test_rewrite_does_not_replace_partial_words():
    text = "Reading files is fun. Use the `Bash` tool."
    result = rewrite_tool_references(text, "gemini")
    assert "Reading" in result
    assert "`run_shell_command`" in result


def test_rewrite_does_not_mangle_english_prose():
    text = "Read the documentation carefully. Write your code. Edit the configuration."
    result = rewrite_tool_references(text, "gemini")
    assert "read_file the documentation" not in result
    assert "write_file your code" not in result
    assert "replace the configuration" not in result


def test_rewrite_backtick_tool_references():
    text = "Use the `Read` tool and `Bash` to run commands."
    result = rewrite_tool_references(text, "gemini")
    assert "`read_file`" in result
    assert "`run_shell_command`" in result


def test_rewrite_the_x_tool_pattern():
    text = "Use the Read tool to view files."
    result = rewrite_tool_references(text, "gemini")
    assert "the read_file tool" in result


def test_strip_frontmatter():
    content = "---\nname: test\n---\n# Hello"
    assert strip_frontmatter(content) == "# Hello"
    assert strip_frontmatter("# No FM") == "# No FM"
