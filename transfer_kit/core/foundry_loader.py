"""transfer_kit/core/foundry_loader.py — Load agent-foundry repo → ClaudeEnvironment.

Isolation rationale (design spec §7, challenger CC):

* :class:`transfer_kit.core.scanner.Scanner` walks the canonical
  ``~/.claude/`` layout. Teaching it about ``joogy06/agent-foundry``'s
  layout would double its surface area and break existing tests.
* :class:`FoundryLoader` is a narrow ingest-edge loader for the
  agent-foundry repo shape (``skills/``, ``agents/``, ``skills/_meta/``,
  ``docs/dependencies/``). It produces the same :class:`ClaudeEnvironment`
  dataclass, but tagged ``source_kind="agent-foundry"`` so downstream
  components (compat, converters) can branch on provenance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from transfer_kit.models import (
    ClaudeEnvironment,
    MetaFile,
    Skill,
)

# ---------------------------------------------------------------------------
# Meta-file classification
# ---------------------------------------------------------------------------

# Filename → MetaFile.kind. Checked in order against the file basename.
# Extend here when new _meta/ filenames appear in upstream agent-foundry.
_META_KIND_RULES: list[tuple[str, str]] = [
    ("gates.py", "gate-script"),
    ("gates.sh", "gate-script"),
    ("claims.py", "claims"),
    ("audit_spawn.py", "audit"),
    ("trusted_runner.py", "trusted"),
    ("forge_reminder_hook.py", "hook"),
    ("pause_state.py", "hook"),
    ("scan_hard_rules.py", "scanner"),
    ("hard-rules-checklist.md", "checklist"),
    ("skill-families.json", "families"),
]


def classify_meta(name: str) -> str:
    """Return the :data:`transfer_kit.models.MetaFileKind` value for a basename."""
    for pattern, kind in _META_KIND_RULES:
        if name == pattern:
            return kind
    return "other"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    """Extract leading YAML frontmatter. Returns ``{}`` on any error."""
    if not text.startswith("---"):
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class FoundryLoader:
    """Compile an agent-foundry repo into a :class:`ClaudeEnvironment`.

    Parameters
    ----------
    root :
        Filesystem path to the root of a ``joogy06/agent-foundry``-shaped
        repository. May be the product of ``git clone`` or a local working
        copy. Missing subdirectories are tolerated — they contribute empty
        lists, not errors. This keeps the loader usable against partial
        fixtures.
    """

    # Subdirectory names under ``skills/`` that are NOT skills themselves.
    # ``_meta`` is handled separately; add more here if upstream introduces
    # non-skill sibling directories.
    _SKILL_EXCLUDES: frozenset[str] = frozenset({"_meta"})

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # -- public ------------------------------------------------------------

    def load(self) -> ClaudeEnvironment:
        """Build and return a :class:`ClaudeEnvironment` from ``self.root``.

        Agents are loaded as :class:`Skill` records with ``source="agent"``
        (see spec §5.2 — additive, not a narrowing). ``projects`` stays
        empty because agent-foundry has no per-project CLAUDE.md analogue;
        the repo-root CLAUDE.md is captured via ``dependency_docs`` if
        present.
        """
        return ClaudeEnvironment(
            skills=self._load_skills() + self._load_agents_as_skills(),
            plugins=[],
            mcp_servers=[],
            projects=[],
            global_settings={},
            local_settings={},
            env_vars=[],
            plans=[],
            teams=[],
            keybindings=None,
            hooks=None,
            permissions=None,
            source_kind="agent-foundry",
            meta_files=self._load_meta(),
            dependency_docs=self._load_dependency_docs(),
        )

    # -- skills ------------------------------------------------------------

    def _load_skills(self) -> list[Skill]:
        """Load one :class:`Skill` per ``skills/<name>/SKILL.md`` file.

        Directories under ``skills/`` that are in
        :attr:`_SKILL_EXCLUDES` (e.g. ``_meta``) are skipped entirely so
        their contents do not masquerade as skills.
        """
        skills_dir = self.root / "skills"
        if not skills_dir.is_dir():
            return []
        skills: list[Skill] = []
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name in self._SKILL_EXCLUDES:
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            content = skill_md.read_text(encoding="utf-8")
            frontmatter = _parse_frontmatter(content)
            skills.append(
                Skill(
                    name=frontmatter.get("name", child.name),
                    path=skill_md,
                    content=content,
                    frontmatter=frontmatter,
                    source="custom",
                )
            )
        return skills

    # -- agents ------------------------------------------------------------

    def _load_agents_as_skills(self) -> list[Skill]:
        """Load each ``agents/*.md`` as a :class:`Skill` with ``source="agent"``.

        The frontmatter is augmented with ``kind: "agent"`` so converters can
        route these records to an agents-specific output layout (e.g.
        ``.github/agents/*.agent.md`` for Copilot CLI) instead of the regular
        instructions directory.
        """
        agents_dir = self.root / "agents"
        if not agents_dir.is_dir():
            return []
        agents: list[Skill] = []
        for md_file in sorted(agents_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            frontmatter = _parse_frontmatter(content)
            # Copy so we don't mutate the parsed dict if callers share it.
            frontmatter = dict(frontmatter)
            frontmatter.setdefault("kind", "agent")
            agents.append(
                Skill(
                    name=frontmatter.get("name", md_file.stem),
                    path=md_file,
                    content=content,
                    frontmatter=frontmatter,
                    source="agent",
                )
            )
        return agents

    # -- meta --------------------------------------------------------------

    def _load_meta(self) -> list[MetaFile]:
        """Load every file under ``skills/_meta/`` as a :class:`MetaFile`.

        Walks one level deep: ``skills/_meta/*``. Subdirectories (e.g. the
        upstream ``skills/_meta/tests/`` folder) are skipped — they are
        implementation detail of the runtime, not portable artifacts.
        """
        meta_dir = self.root / "skills" / "_meta"
        if not meta_dir.is_dir():
            return []
        meta: list[MetaFile] = []
        for child in sorted(meta_dir.iterdir()):
            if not child.is_file():
                continue
            try:
                content = child.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Binary meta artifacts are not expected and silently skipped;
                # compat_matrix will not list them so they cannot slip into
                # output by default.
                continue
            meta.append(
                MetaFile(
                    name=child.name,
                    path=child,
                    content=content,
                    kind=classify_meta(child.name),
                )
            )
        return meta

    # -- dependency docs ---------------------------------------------------

    def _load_dependency_docs(self) -> dict:
        """Read ``docs/dependencies/*.md`` verbatim into a ``{basename: content}`` dict.

        The pull pipeline renders these into ``DEPENDENCIES.md`` on the
        target — no structured parsing (challenger B4 warned: fragile).
        """
        deps_dir = self.root / "docs" / "dependencies"
        if not deps_dir.is_dir():
            return {}
        out: dict = {}
        for f in sorted(deps_dir.glob("*.md")):
            try:
                out[f.name] = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        return out


__all__ = ["FoundryLoader", "classify_meta"]
