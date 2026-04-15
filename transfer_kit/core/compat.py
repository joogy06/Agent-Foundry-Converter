"""transfer_kit/core/compat.py — Per-target / per-tier compatibility filter.

Design spec §11. Loads ``transfer_kit/data/compat_matrix.yaml`` and filters
an incoming :class:`transfer_kit.models.ClaudeEnvironment` for a given
target, returning the filtered environment plus a structured report.

The filter is split into three operations:

1. **Artifact routing** — each ``MetaFile`` and each ``Skill(source="agent")``
   gets a classification (``portable`` / ``degraded`` / ``docs-only`` /
   ``claude-only`` / ``excluded``). ``claude-only`` and ``excluded`` are
   dropped; ``docs-only`` is retained but flagged so the converter knows
   not to emit it as executable runtime.
2. **Content-marker detection** — content containing a
   ``claude_ecosystem_only_markers`` substring is re-classified as
   ``claude-only`` regardless of filename, catching files whose names look
   portable but whose bodies reference Claude-only primitives.
3. **Tier pruning** — ``tier`` is applied conservatively: ``minimal`` drops
   everything tagged ``agent`` or ``docs-only``; ``standard`` drops only
   ``claude-only`` (the default); ``full`` drops nothing. This mapping is
   deliberately simple and documented — the test plan covers boundaries.

The report is a plain dict (serialisable) rather than a dataclass so
pull.py can log it and pass it to DEPENDENCIES.md rendering without a
bespoke adapter.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from transfer_kit.models import ClaudeEnvironment, MetaFile, Skill


_DEFAULT_MATRIX_PATH = Path(__file__).resolve().parent.parent / "data" / "compat_matrix.yaml"


# ---------------------------------------------------------------------------
# Matrix loader
# ---------------------------------------------------------------------------


@dataclass
class CompatMatrix:
    """Parsed ``compat_matrix.yaml`` content."""

    artifacts: dict[str, Any] = field(default_factory=dict)
    excludes: list[str] = field(default_factory=list)
    content_markers: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "CompatMatrix":
        src = Path(path) if path else _DEFAULT_MATRIX_PATH
        raw = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
        return cls(
            artifacts=raw.get("artifacts", {}) or {},
            excludes=list(raw.get("excludes", []) or []),
            content_markers=list(raw.get("claude_ecosystem_only_markers", []) or []),
        )

    # -- artifact lookup --------------------------------------------------

    def classify_meta(self, meta_name: str, target: str) -> str:
        """Return the matrix classification for a :class:`MetaFile`.

        Looks up by ``meta.<basename>`` (e.g. ``meta.gates.py``). Unknown
        files default to ``portable`` on the assumption that newly-added
        ``_meta/`` artifacts should ride along until someone explicitly
        restricts them; this is conservative in the direction of emitting
        documentation rather than silently dropping.
        """
        key = f"meta.{meta_name}"
        entry = self.artifacts.get(key)
        return _scalar_or_target(entry, target, default="portable")

    def classify_artifact(self, kind: str, target: str) -> str:
        """Return the matrix classification for a kind-level artifact."""
        entry = self.artifacts.get(kind)
        return _scalar_or_target(entry, target, default="portable")

    def emits_g2_shim(self, target: str) -> bool:
        """Return True if ``gates_g2_shim.py`` should be synthesised for ``target``."""
        return self.classify_artifact("meta.gates.py.g2-only", target) == "portable"

    def path_excluded(self, rel_path: str) -> bool:
        """Return True when the path matches any ``excludes`` glob."""
        for pattern in self.excludes:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    def content_has_claude_only_marker(self, content: str) -> bool:
        """Return True when any ``claude_ecosystem_only_markers`` substring appears."""
        return any(m in content for m in self.content_markers)


def _scalar_or_target(entry: Any, target: str, *, default: str) -> str:
    """Normalise a matrix entry that may be a scalar or a per-target dict."""
    if entry is None:
        return default
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        value = entry.get(target)
        if isinstance(value, str):
            return value
    return default


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


# Tier → set of classifications that tier permits.
_TIER_ALLOW: dict[str, frozenset[str]] = {
    "minimal": frozenset({"portable"}),
    "standard": frozenset({"portable", "degraded"}),
    "full": frozenset({"portable", "degraded", "docs-only"}),
}


def _allowed_for_tier(tier: str) -> frozenset[str]:
    return _TIER_ALLOW.get(tier, _TIER_ALLOW["standard"])


def filter_env(
    env: ClaudeEnvironment,
    target: str,
    tier: str = "standard",
    matrix: CompatMatrix | None = None,
) -> tuple[ClaudeEnvironment, dict[str, Any]]:
    """Apply the compat matrix to ``env`` and return ``(filtered_env, report)``.

    The returned environment is a *new* :class:`ClaudeEnvironment` built
    via :func:`dataclasses.replace`; the input is not mutated. The report
    is a dict with counts and per-file classifications, ready to render
    into DEPENDENCIES.md.
    """
    matrix = matrix or CompatMatrix.load()
    allowed = _allowed_for_tier(tier)

    report: dict[str, Any] = {
        "target": target,
        "tier": tier,
        "counts": {"portable": 0, "degraded": 0, "docs-only": 0, "claude-only-dropped": 0, "excluded": 0},
        "meta_classifications": {},
        "agent_classifications": {},
        "skill_classifications": {},
        "gates_g2_shim_emit": False,
        "dropped_claude_only": [],
        "docs_only_emit": [],
    }

    # --- skills --------------------------------------------------------

    kept_skills: list[Skill] = []
    for skill in env.skills:
        artifact_kind = "agent" if skill.source == "agent" else "skill"
        cls = matrix.classify_artifact(artifact_kind, target)
        if matrix.content_has_claude_only_marker(skill.content):
            cls = "claude-only"
        # Tier filter on top of classification.
        if cls == "excluded":
            report["counts"]["excluded"] += 1
            continue
        if cls == "claude-only":
            report["counts"]["claude-only-dropped"] += 1
            report["dropped_claude_only"].append(str(skill.path))
            continue
        if cls not in allowed:
            # Tier drops it (e.g. minimal tier drops degraded agents).
            report["counts"]["claude-only-dropped"] += 1
            report["dropped_claude_only"].append(str(skill.path))
            continue
        report["counts"][cls] = report["counts"].get(cls, 0) + 1
        if artifact_kind == "agent":
            report["agent_classifications"][skill.name] = cls
        else:
            report["skill_classifications"][skill.name] = cls
        kept_skills.append(skill)

    # --- meta files ----------------------------------------------------

    kept_meta: list[MetaFile] = []
    for m in env.meta_files:
        cls = matrix.classify_meta(m.name, target)
        if cls != "claude-only" and matrix.content_has_claude_only_marker(m.content):
            cls = "claude-only"
        report["meta_classifications"][m.name] = cls
        if cls == "excluded":
            report["counts"]["excluded"] += 1
            continue
        if cls == "claude-only":
            report["counts"]["claude-only-dropped"] += 1
            report["dropped_claude_only"].append(str(m.path))
            continue
        if cls == "skip":
            # Intentionally not emitted on this target (different from
            # excluded — see YAML comments). Don't count as dropped.
            continue
        if cls == "docs-only":
            report["counts"]["docs-only"] += 1
            report["docs_only_emit"].append(m.name)
            kept_meta.append(m)
            continue
        if cls == "portable":
            report["counts"]["portable"] += 1
            kept_meta.append(m)
            continue
        if cls == "degraded":
            report["counts"]["degraded"] += 1
            kept_meta.append(m)

    report["gates_g2_shim_emit"] = matrix.emits_g2_shim(target)

    filtered = replace(
        env,
        skills=kept_skills,
        meta_files=kept_meta,
    )
    return filtered, report


__all__ = ["CompatMatrix", "filter_env"]
