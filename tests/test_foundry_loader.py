"""tests/test_foundry_loader.py — FoundryLoader unit tests.

Exercises the ingest edge that turns an agent-foundry repo shape into a
:class:`ClaudeEnvironment`. Fixture lives at
``tests/fixtures/agent_foundry/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transfer_kit.core.foundry_loader import FoundryLoader, classify_meta
from transfer_kit.models import ClaudeEnvironment, MetaFile, Skill


FIXTURE = Path(__file__).parent / "fixtures" / "agent_foundry"


@pytest.fixture()
def env() -> ClaudeEnvironment:
    return FoundryLoader(FIXTURE).load()


# -- skills / agents ---------------------------------------------------------


def test_loads_skills_excluding_meta(env: ClaudeEnvironment) -> None:
    regular = [s for s in env.skills if s.source != "agent"]
    names = {s.name for s in regular}
    # _meta/ must NOT show up as a skill named "_meta".
    assert "_meta" not in names
    assert names == {"alpha", "beta", "gamma", "delta"}


def test_agents_tagged_source_agent(env: ClaudeEnvironment) -> None:
    agents = [s for s in env.skills if s.source == "agent"]
    assert {a.name for a in agents} == {"alpha_agent", "beta_agent"}
    for a in agents:
        assert a.frontmatter.get("kind") == "agent"


def test_regular_skills_source_is_custom(env: ClaudeEnvironment) -> None:
    regular = [s for s in env.skills if s.source != "agent"]
    assert all(s.source == "custom" for s in regular)


def test_source_kind_is_agent_foundry(env: ClaudeEnvironment) -> None:
    assert env.source_kind == "agent-foundry"


def test_projects_empty(env: ClaudeEnvironment) -> None:
    # CRITICAL per design spec §7: agents must NOT be flattened into ProjectConfig.
    assert env.projects == []


def test_frontmatter_parsed(env: ClaudeEnvironment) -> None:
    beta = next(s for s in env.skills if s.name == "beta")
    assert beta.frontmatter.get("applyTo") == "**/*.py"


def test_skill_path_points_to_source(env: ClaudeEnvironment) -> None:
    alpha = next(s for s in env.skills if s.name == "alpha" and s.source == "custom")
    assert alpha.path.name == "SKILL.md"
    assert alpha.path.parent.name == "alpha"


# -- meta classification -----------------------------------------------------


def test_meta_files_loaded(env: ClaudeEnvironment) -> None:
    names = {m.name for m in env.meta_files}
    assert {"gates.py", "hard-rules-checklist.md"} <= names


def test_meta_kind_classified(env: ClaudeEnvironment) -> None:
    by_name = {m.name: m.kind for m in env.meta_files}
    assert by_name["gates.py"] == "gate-script"
    assert by_name["hard-rules-checklist.md"] == "checklist"


def test_classify_meta_standalone() -> None:
    assert classify_meta("gates.py") == "gate-script"
    assert classify_meta("gates.sh") == "gate-script"
    assert classify_meta("claims.py") == "claims"
    assert classify_meta("audit_spawn.py") == "audit"
    assert classify_meta("trusted_runner.py") == "trusted"
    assert classify_meta("skill-families.json") == "families"
    assert classify_meta("hard-rules-checklist.md") == "checklist"
    assert classify_meta("forge_reminder_hook.py") == "hook"
    assert classify_meta("pause_state.py") == "hook"
    assert classify_meta("unknown.txt") == "other"


# -- dependency docs passthrough --------------------------------------------


def test_dependency_docs_loaded(env: ClaudeEnvironment) -> None:
    assert "README.md" in env.dependency_docs
    assert "Dependencies (fixture)" in env.dependency_docs["README.md"]


# -- tolerates missing subdirs ----------------------------------------------


def test_missing_skills_dir_returns_empty(tmp_path: Path) -> None:
    # Empty dir — no skills/, no agents/, no _meta/.
    env = FoundryLoader(tmp_path).load()
    assert env.skills == []
    assert env.meta_files == []
    assert env.dependency_docs == {}


def test_missing_agents_dir_does_not_raise(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    env = FoundryLoader(tmp_path).load()
    assert env.skills == []  # only skills dir, no agents/SKILL.md


# -- loader does not confuse _meta for a skill ------------------------------


def test_meta_subdir_is_not_a_skill() -> None:
    env = FoundryLoader(FIXTURE).load()
    # Even if _meta had a SKILL.md sibling file, the loader must skip it.
    assert not any(s.name == "_meta" for s in env.skills)
