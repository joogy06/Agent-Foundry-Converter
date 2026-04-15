"""tests/test_xref_resolver.py — xref_resolver tests (TS-XR-00*)."""

from __future__ import annotations

from pathlib import Path

from transfer_kit.core.foundry_loader import FoundryLoader
from transfer_kit.core.xref_resolver import resolve_refs, transitive_include
from transfer_kit.models import ClaudeEnvironment


FIXTURE = Path(__file__).parent / "fixtures" / "agent_foundry"


def _env():
    return FoundryLoader(FIXTURE).load()


def test_resolved_refs_when_all_present() -> None:
    env = _env()
    report = resolve_refs(env, env)
    # alpha references beta — beta IS in the env → resolved
    assert ("alpha", "beta") in report.resolved


def test_dangling_when_target_dropped() -> None:
    env = _env()
    from dataclasses import replace
    # Drop beta from filtered; alpha should register dangling.
    filtered = replace(env, skills=[s for s in env.skills if s.name != "beta"])
    report = resolve_refs(filtered, env)
    assert ("alpha", "beta") in report.dangling


def test_to_dict_is_sorted() -> None:
    env = _env()
    report = resolve_refs(env, env)
    d = report.to_dict()
    # resolved list is sorted tuples
    resolved = [(r["holder"], r["ref"]) for r in d["resolved"]]
    assert resolved == sorted(resolved)


def test_transitive_include_adds_missing() -> None:
    env = _env()
    from dataclasses import replace
    filtered = replace(env, skills=[s for s in env.skills if s.name != "beta"])
    augmented, added = transitive_include(filtered, env)
    assert "beta" in added
    assert any(s.name == "beta" for s in augmented.skills)


def test_unknown_tokens_not_flagged_as_dangling() -> None:
    env = _env()
    # gamma references `missing-skill` which is NOT in the universe — it is
    # "unknown" (likely a backticked English word) and should NOT pollute
    # the dangling list.
    report = resolve_refs(env, env)
    dangling_refs = {r for _, r in report.dangling}
    assert "missing-skill" not in dangling_refs


def test_no_dangling_when_env_complete() -> None:
    env = _env()
    report = resolve_refs(env, env)
    # When filtered == universe, every universe-name ref resolves.
    assert report.dangling == []
