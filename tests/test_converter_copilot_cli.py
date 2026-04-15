"""tests/test_converter_copilot_cli.py — CopilotCliConverter tests (TS-CC-00*)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transfer_kit.converters.copilot_cli import CopilotCliConverter
from transfer_kit.core.compat import CompatMatrix, filter_env
from transfer_kit.core.foundry_loader import FoundryLoader


FIXTURE = Path(__file__).parent / "fixtures" / "agent_foundry"


@pytest.fixture()
def filtered():
    env = FoundryLoader(FIXTURE).load()
    return filter_env(env, target="copilot-cli", tier="standard")


def test_convert_all_produces_expected_layout(filtered) -> None:
    env, _ = filtered
    conv = CopilotCliConverter(env)
    conv.workspace = "/tmp/test-output"
    results = conv.convert_all(env)
    # Skills land under .github/instructions/
    assert any(k.startswith(".github/instructions/") and k.endswith(".instructions.md") for k in results)


def test_agents_land_in_github_agents(filtered) -> None:
    env, _ = filtered
    conv = CopilotCliConverter(env)
    results = conv.convert_all(env)
    agents_keys = [k for k in results if k.startswith(".github/agents/")]
    assert len(agents_keys) >= 1  # alpha_agent + beta_agent (neither has claude-only markers)
    assert all(k.endswith(".agent.md") for k in agents_keys)


def test_bash_tool_preserved_as_lowercase() -> None:
    """TS-CC-002 — Copilot CLI has direct bash, so Bash rewrites to 'bash' not a replacement verb."""
    env = FoundryLoader(FIXTURE).load()
    filtered_env, _ = filter_env(env, target="copilot-cli", tier="standard")
    conv = CopilotCliConverter(filtered_env)
    results = conv.convert_all(filtered_env)
    beta = next(v for k, v in results.items() if k.endswith("beta.instructions.md"))
    # beta's body has "Uses the `Bash` tool" — rewritten to `bash`
    assert "`bash`" in beta


def test_g2_shim_emitted(filtered) -> None:
    env, _ = filtered
    conv = CopilotCliConverter(env)
    results = conv.convert_all(env)
    shim_key = "docs/agent-foundry/_meta/gates_g2_shim.py"
    assert shim_key in results
    assert "G2_FAIL" in results[shim_key]


def test_full_gates_py_is_emitted_as_docs(filtered) -> None:
    """TS-CC-003 — full gates.py is emitted as reference under docs/.../_meta/gates.py."""
    env, _ = filtered
    conv = CopilotCliConverter(env)
    results = conv.convert_all(env)
    docs_gates = "docs/agent-foundry/_meta/gates.py"
    assert docs_gates in results
    # Content includes the env-var shim prologue for non-Claude target.
    assert "TRANSFER_KIT_SKILLS_ROOT" in results[docs_gates]


def test_meta_readme_banner_emitted(filtered) -> None:
    env, _ = filtered
    conv = CopilotCliConverter(env)
    results = conv.convert_all(env)
    readme = "docs/agent-foundry/_meta/README.md"
    assert readme in results
    assert "gates_g2_shim.py" in results[readme]


def test_per_skill_applyto_honoured(filtered) -> None:
    env, _ = filtered
    conv = CopilotCliConverter(env)
    results = conv.convert_all(env)
    beta = next(v for k, v in results.items() if k.endswith("beta.instructions.md"))
    assert "applyTo: '**/*.py'" in beta


def test_empty_env_still_emits_shim_and_template() -> None:
    from transfer_kit.models import ClaudeEnvironment
    env = ClaudeEnvironment(
        skills=[], plugins=[], mcp_servers=[], projects=[],
        global_settings={}, local_settings={}, env_vars=[],
        plans=[], teams=[], keybindings=None, source_kind="agent-foundry",
    )
    conv = CopilotCliConverter(env)
    results = conv.convert_all(env)
    # With no meta files the G2 shim still synthesises (compat matrix says
    # ``meta.gates.py.g2-only: portable`` for copilot-cli). The host-agent
    # onboarding fragment also always lands as AGENTS.md so the host repo
    # always gets the managed-block for teaching its agent how to re-pull.
    assert set(results.keys()) == {
        "docs/agent-foundry/_meta/gates_g2_shim.py",
        "AGENTS.md",
    }
    assert "tk:pull-managed-begin" in results["AGENTS.md"]
