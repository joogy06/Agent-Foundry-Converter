"""transfer_kit/core/path_rewriter.py — Target-specific path rewriting.

Applied in two places (design spec §8):

1. Inside each converter's content pipeline (called by
   :func:`transfer_kit.converters.base.rewrite_tool_references`'s wrapper
   or directly by :class:`transfer_kit.converters.base.BaseConverter`
   hook implementations).
2. Directly on :attr:`transfer_kit.models.MetaFile.content` before the
   converter emits the file, because tool-reference rewriting does not
   traverse Python modules but paths in Python modules still need
   rewriting.

Known limitation (challenger C from the design dialogue): Python code
that builds paths at runtime via ``Path.home()`` / ``os.path.expanduser``
cannot be textually rewritten. Mitigation: :func:`inject_env_shim`
prepends an ``TRANSFER_KIT_SKILLS_ROOT`` env-var shim prologue to
``gates.py`` for non-Claude targets; the host-agent template fragment
sets that env var before invoking gates.
"""

from __future__ import annotations

import re


# Target-specific rewrite rule table.
#
# Each entry is ``(pattern_regex, replacement_template)``. Order matters —
# more-specific prefixes MUST come before their broader counterparts
# (``~/.claude/skills/_meta/`` before ``~/.claude/skills/``) because Python
# ``re`` performs leftmost, greedy-per-alternative matching. Replacement
# templates may contain ``{workspace}`` which is filled at rewrite time.
_RULES: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "claude": [],  # identity — no rewrites
    "copilot": [
        (re.compile(r"~/\.claude/skills/_meta/"), "{workspace}/.github/_meta/"),
        (re.compile(r"~/\.claude/skills/"),       "{workspace}/.github/instructions/"),
        (re.compile(r"~/\.claude/agents/"),       "{workspace}/.github/agents/"),
    ],
    "copilot-cli": [
        (re.compile(r"~/\.claude/skills/_meta/"), "{workspace}/docs/agent-foundry/_meta/"),
        (re.compile(r"~/\.claude/skills/"),       "{workspace}/.github/instructions/"),
        (re.compile(r"~/\.claude/agents/"),       "{workspace}/.github/agents/"),
    ],
    "gemini": [
        (re.compile(r"~/\.claude/skills/_meta/"), "~/.gemini/_meta/"),
        (re.compile(r"~/\.claude/skills/"),       "~/.gemini/skills/"),
        (re.compile(r"~/\.claude/agents/"),       "~/.gemini/agents/"),
    ],
    "windsurf": [
        (re.compile(r"~/\.claude/skills/_meta/"), "{workspace}/.windsurf/_meta/"),
        (re.compile(r"~/\.claude/skills/"),       "{workspace}/.windsurf/rules/"),
        (re.compile(r"~/\.claude/agents/"),       "{workspace}/.windsurf/agents/"),
    ],
}


# Sentinel comment that marks content already touched by the env-var shim
# injector, so re-running :func:`inject_env_shim` is idempotent.
_ENV_SHIM_MARKER = "# tk:pull-managed env-var shim — do not edit"

_ENV_SHIM_PROLOGUE = f"""\
{_ENV_SHIM_MARKER}
# Injected by transfer-kit pull for non-Claude targets. Host agents set
# TRANSFER_KIT_SKILLS_ROOT to point at their local skills directory before
# invoking this script.
import os as _tk_os
_TK_SKILLS_ROOT = _tk_os.environ.get("TRANSFER_KIT_SKILLS_ROOT", "")
if _TK_SKILLS_ROOT:
    _tk_os.environ.setdefault("HOME", _TK_SKILLS_ROOT.rsplit("/.claude/", 1)[0] or _TK_SKILLS_ROOT)
"""


def rewrite_paths(content: str, target: str, workspace: str = ".") -> str:
    """Apply target-specific path rewrites to ``content``.

    Parameters
    ----------
    content :
        Arbitrary source text (markdown body, Python module, YAML config)
        containing ``~/.claude/`` references.
    target :
        Target name used to look up the rule table. Unknown targets are
        treated as identity transforms — the caller is responsible for
        validating against the supported target list.
    workspace :
        String substituted for ``{workspace}`` in target rules. Defaults
        to ``"."`` (CWD-relative) which is correct for testing and
        dry-runs; real emission passes the actual output directory.

    Notes
    -----
    The function is idempotent under the supported targets: already-rewritten
    content contains no literal ``~/.claude/`` fragments so a second pass is
    a no-op. This property is covered by TS-PR-004 in the contract map.
    """
    rules = _RULES.get(target)
    if not rules:
        return content
    out = content
    for pattern, template in rules:
        replacement = template.replace("{workspace}", workspace)
        out = pattern.sub(replacement, out)
    return out


def inject_env_shim(content: str, name: str, target: str) -> str:
    """Inject the ``TRANSFER_KIT_SKILLS_ROOT`` shim prologue into ``gates.py``.

    This is a narrow helper: it only touches the file whose basename is
    ``gates.py`` and only on non-Claude targets. Everything else passes
    through unchanged. Re-running the injector on already-shimmed content
    is a no-op thanks to :data:`_ENV_SHIM_MARKER`.
    """
    if target == "claude" or name != "gates.py":
        return content
    if _ENV_SHIM_MARKER in content:
        return content
    # Preserve the shebang when present — the shim prologue must land AFTER it.
    if content.startswith("#!"):
        head, _, tail = content.partition("\n")
        return head + "\n" + _ENV_SHIM_PROLOGUE + "\n" + tail
    return _ENV_SHIM_PROLOGUE + "\n" + content


# Shebang rewrite for Windows emit. The ``#!/usr/bin/env python3`` line is
# harmless on Windows when invoked via a ``.cmd`` wrapper, but we still
# provide a helper for converters that want to strip it explicitly.
_SHEBANG_RE = re.compile(r"^#!.*\n", re.MULTILINE)


def rewrite_shebang_for_windows(content: str) -> str:
    """Remove the leading shebang so Windows ``.cmd`` wrappers can invoke python directly.

    Only rewrites the first line; subsequent ``#!`` markers (rare, but
    possible in embedded examples) are preserved. If no shebang is present,
    returns ``content`` unchanged.
    """
    if not content.startswith("#!"):
        return content
    return _SHEBANG_RE.sub("", content, count=1)


__all__ = [
    "rewrite_paths",
    "inject_env_shim",
    "rewrite_shebang_for_windows",
]
