"""tests/test_path_rewriter.py — path_rewriter tests (TS-PR-00* in contract map)."""

from __future__ import annotations

from transfer_kit.core.path_rewriter import (
    inject_env_shim,
    rewrite_paths,
    rewrite_shebang_for_windows,
)


# -- rewrite_paths ------------------------------------------------------------


def test_rewrite_claude_is_identity() -> None:
    body = "Look at ~/.claude/skills/foo and ~/.claude/agents/bob."
    assert rewrite_paths(body, "claude") == body


def test_rewrite_copilot_cli() -> None:
    out = rewrite_paths("use ~/.claude/skills/foo", "copilot-cli", workspace="/tmp/out")
    assert out == "use /tmp/out/.github/instructions/foo"


def test_rewrite_copilot_cli_meta_prefix_wins() -> None:
    # _meta/ must rewrite BEFORE the broader skills/ rule (order matters).
    out = rewrite_paths("~/.claude/skills/_meta/gates.py", "copilot-cli", workspace="/tmp/out")
    assert out == "/tmp/out/docs/agent-foundry/_meta/gates.py"


def test_rewrite_idempotent() -> None:
    src = "see ~/.claude/skills/foo"
    once = rewrite_paths(src, "copilot-cli", workspace=".")
    twice = rewrite_paths(once, "copilot-cli", workspace=".")
    assert once == twice


def test_rewrite_gemini() -> None:
    out = rewrite_paths("~/.claude/skills/foo and ~/.claude/agents/bob", "gemini")
    assert "~/.gemini/skills/foo" in out
    assert "~/.gemini/agents/bob" in out


def test_rewrite_windsurf() -> None:
    out = rewrite_paths("~/.claude/skills/foo", "windsurf", workspace="/ws")
    assert "/ws/.windsurf/rules/foo" in out


def test_rewrite_unknown_target_is_identity() -> None:
    assert rewrite_paths("~/.claude/skills/foo", "nonexistent") == "~/.claude/skills/foo"


def test_rewrite_windows_workspace_with_backslash_escape_chars() -> None:
    # Regression: Windows absolute paths with backslashes must not be
    # mis-parsed as regex replacement escapes (\U, \a, \n, ...).
    # Historical bug raised ``KeyError: '\\U'`` when workspace contained
    # ``C:\Users\...``.
    win_ws = r"C:\Users\runneradmin\AppData\Local\tk\out"
    out = rewrite_paths("~/.claude/skills/foo", "copilot-cli", workspace=win_ws)
    assert out == win_ws + "/.github/instructions/foo"
    # Escape-rich paths must also survive.
    tricky = r"C:\a\n\t\b\f\r\v\s\0\1"
    out2 = rewrite_paths("~/.claude/skills/bar", "copilot-cli", workspace=tricky)
    assert out2 == tricky + "/.github/instructions/bar"


# -- inject_env_shim ----------------------------------------------------------


def test_inject_env_shim_only_touches_gates_py() -> None:
    original = "print('not gates')\n"
    assert inject_env_shim(original, "other.py", "copilot-cli") == original


def test_inject_env_shim_claude_target_is_noop() -> None:
    src = "import os\n"
    assert inject_env_shim(src, "gates.py", "claude") == src


def test_inject_env_shim_adds_prologue() -> None:
    src = "import os\n\n# rest of file\n"
    out = inject_env_shim(src, "gates.py", "copilot-cli")
    assert "TRANSFER_KIT_SKILLS_ROOT" in out
    assert out.count("TRANSFER_KIT_SKILLS_ROOT") >= 1


def test_inject_env_shim_preserves_shebang() -> None:
    src = "#!/usr/bin/env python3\nimport os\n"
    out = inject_env_shim(src, "gates.py", "copilot-cli")
    assert out.startswith("#!/usr/bin/env python3\n")
    assert "TRANSFER_KIT_SKILLS_ROOT" in out


def test_inject_env_shim_is_idempotent() -> None:
    src = "import os\n"
    once = inject_env_shim(src, "gates.py", "copilot-cli")
    twice = inject_env_shim(once, "gates.py", "copilot-cli")
    assert once == twice


# -- rewrite_shebang_for_windows ---------------------------------------------


def test_rewrite_shebang_for_windows_strips() -> None:
    src = "#!/usr/bin/env python3\nimport sys\n"
    assert rewrite_shebang_for_windows(src) == "import sys\n"


def test_rewrite_shebang_for_windows_noop_without_shebang() -> None:
    src = "import sys\n"
    assert rewrite_shebang_for_windows(src) == src
