"""transfer_kit/core/xref_resolver.py — Cross-reference integrity check.

Design spec §13. After the compat filter prunes agents, skills, and meta
files, some surviving agents may reference dropped skills by name
(e.g. ``bob`` references ``agent-teams`` which was excluded). This module
walks agent and skill bodies, looks for backtick-quoted name tokens that
match the universe of known skill names, and reports whether each
reference resolves.

The resolver does NOT mutate the environment — it only reports. Pull uses
``--resolve-refs`` to decide whether to re-include dangling refs
transitively, or to warn only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from transfer_kit.models import ClaudeEnvironment, Skill


# A reasonable skill-name token: lowercase kebab-case or snake_case, 3-80 chars.
# We don't want to match every English word; limit to plausible skill names.
_REF_RE = re.compile(r"`([a-z][a-z0-9_-]{2,79})`")


@dataclass
class XRefReport:
    """Structured cross-reference report emitted by :func:`resolve_refs`."""

    resolved: list[tuple[str, str]] = field(default_factory=list)  # (holder, ref)
    dangling: list[tuple[str, str]] = field(default_factory=list)  # (holder, ref)
    unknown: list[tuple[str, str]] = field(default_factory=list)   # (holder, ref)  — matched token that is not a skill at all

    def to_dict(self) -> dict:
        # Sort for stable output — the walking order depends on set
        # iteration which is not insertion-ordered for strings. The
        # report is a presentation artifact; deterministic ordering makes
        # the pull idempotent (spec §15) and diffable across runs.
        resolved_sorted = sorted(self.resolved)
        dangling_sorted = sorted(self.dangling)
        return {
            "resolved_count": len(self.resolved),
            "dangling_count": len(self.dangling),
            "unknown_count": len(self.unknown),
            "resolved": [{"holder": h, "ref": r} for h, r in resolved_sorted],
            "dangling": [{"holder": h, "ref": r} for h, r in dangling_sorted],
        }


def resolve_refs(
    filtered_env: ClaudeEnvironment,
    universe_env: ClaudeEnvironment,
    tier: str = "standard",
) -> XRefReport:
    """Report cross-references from ``filtered_env`` against the pre-filter universe.

    Parameters
    ----------
    filtered_env :
        The :class:`ClaudeEnvironment` *after* compat filtering. Only its
        surviving skills/agents are walked for references.
    universe_env :
        The original :class:`ClaudeEnvironment` *before* compat filtering.
        Its skill/agent name set is the authoritative "known names"
        universe — a reference that isn't in the universe is classified
        as ``unknown`` (likely an English word that happened to match the
        token regex), while a reference that is in the universe but not
        in ``filtered_env`` is ``dangling``.
    tier :
        Recorded for reporting purposes only; filtering is already applied
        to ``filtered_env``.

    Notes
    -----
    The universe/filtered split exists because otherwise any non-skill
    backticked token would register as a dangling ref and flood the report.
    """
    del tier  # included for signature stability; report adds it from caller context
    filtered_names = {s.name for s in filtered_env.skills}
    universe_names = {s.name for s in universe_env.skills}
    report = XRefReport()
    for holder in filtered_env.skills:
        refs = _extract_refs(holder)
        for ref in refs:
            if ref == holder.name:
                continue
            if ref in filtered_names:
                report.resolved.append((holder.name, ref))
            elif ref in universe_names:
                report.dangling.append((holder.name, ref))
            # else: unknown token — omit by default to keep the report signal-to-noise high
    return report


def _extract_refs(skill: Skill) -> set[str]:
    """Return the set of plausible skill-name tokens referenced in a skill body."""
    return {m.group(1) for m in _REF_RE.finditer(skill.content)}


def transitive_include(
    filtered_env: ClaudeEnvironment,
    universe_env: ClaudeEnvironment,
) -> tuple[ClaudeEnvironment, list[str]]:
    """Re-include dangling skill references transitively.

    Returns a new :class:`ClaudeEnvironment` with any skill referenced by a
    surviving skill/agent added back in (up to the universe), and a list of
    added names. Iterates to fixed point so second-order refs are picked up.
    """
    from dataclasses import replace

    universe_by_name = {s.name: s for s in universe_env.skills}
    kept = {s.name: s for s in filtered_env.skills}
    added: list[str] = []
    while True:
        report = resolve_refs(replace(filtered_env, skills=list(kept.values())), universe_env)
        if not report.dangling:
            break
        grew = False
        for _holder, ref in report.dangling:
            if ref not in kept and ref in universe_by_name:
                kept[ref] = universe_by_name[ref]
                added.append(ref)
                grew = True
        if not grew:
            break
    return replace(filtered_env, skills=list(kept.values())), added


__all__ = ["XRefReport", "resolve_refs", "transitive_include"]
