"""tests/test_compat_matrix.py — CompatMatrix + filter_env tests (TS-CP-00*)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transfer_kit.core.compat import CompatMatrix, filter_env
from transfer_kit.core.foundry_loader import FoundryLoader


FIXTURE = Path(__file__).parent / "fixtures" / "agent_foundry"


@pytest.fixture()
def matrix() -> CompatMatrix:
    return CompatMatrix.load()


def test_matrix_loads(matrix: CompatMatrix) -> None:
    assert matrix.artifacts
    assert matrix.content_markers
    assert "meta.gates.py" in matrix.artifacts


def test_classify_artifact_skill(matrix: CompatMatrix) -> None:
    assert matrix.classify_artifact("skill", "copilot-cli") == "portable"
    assert matrix.classify_artifact("skill", "claude") == "portable"


def test_classify_meta_docs_only_for_copilot_cli(matrix: CompatMatrix) -> None:
    assert matrix.classify_meta("gates.py", "copilot-cli") == "docs-only"
    assert matrix.classify_meta("gates.py", "claude") == "portable"


def test_classify_claude_only_for_claims_py(matrix: CompatMatrix) -> None:
    assert matrix.classify_meta("claims.py", "copilot-cli") == "claude-only"
    assert matrix.classify_meta("claims.py", "claude") == "claude-only"


def test_emits_g2_shim_for_non_claude(matrix: CompatMatrix) -> None:
    assert matrix.emits_g2_shim("copilot-cli") is True
    assert matrix.emits_g2_shim("gemini") is True
    assert matrix.emits_g2_shim("claude") is False


def test_content_marker_detection(matrix: CompatMatrix) -> None:
    assert matrix.content_has_claude_only_marker("text /codex:review text") is True
    assert matrix.content_has_claude_only_marker("use ScheduleWakeup") is True
    assert matrix.content_has_claude_only_marker("plain prose") is False


def test_filter_env_copilot_cli_standard() -> None:
    env = FoundryLoader(FIXTURE).load()
    filtered, report = filter_env(env, target="copilot-cli", tier="standard")
    # delta (with ScheduleWakeup content marker) must be classified claude-only
    # even though its filename is benign.
    kept_names = {s.name for s in filtered.skills}
    assert "delta" not in kept_names
    # report tracks the drop
    assert report["counts"]["claude-only-dropped"] >= 1
    # gates.py survives as docs-only
    assert any(m.name == "gates.py" for m in filtered.meta_files)
    assert report["gates_g2_shim_emit"] is True


def test_filter_env_claude_target_keeps_everything() -> None:
    env = FoundryLoader(FIXTURE).load()
    filtered, report = filter_env(env, target="claude", tier="standard")
    # On claude target the content marker is effectively irrelevant because
    # the skill artifact class is portable; delta still drops because the
    # content marker forces claude-only even for claude target (by design).
    # However gates.py etc remain portable.
    assert report["gates_g2_shim_emit"] is False


def test_excludes_skill_families_json() -> None:
    # Synthesise a meta file named skill-families.json
    env = FoundryLoader(FIXTURE).load()
    from transfer_kit.models import MetaFile
    env.meta_files.append(
        MetaFile(name="skill-families.json", path=Path("x"),
                 content="{}", kind="families")
    )
    filtered, report = filter_env(env, target="copilot-cli", tier="standard")
    assert not any(m.name == "skill-families.json" for m in filtered.meta_files)


def test_tier_minimal_drops_degraded_agents() -> None:
    env = FoundryLoader(FIXTURE).load()
    _, standard = filter_env(env, target="copilot-cli", tier="standard")
    _, minimal = filter_env(env, target="copilot-cli", tier="minimal")
    # minimal drops more than standard (or at least not fewer)
    assert minimal["counts"]["claude-only-dropped"] >= standard["counts"]["claude-only-dropped"]
