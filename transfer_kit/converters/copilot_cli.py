"""transfer_kit/converters/copilot_cli.py — GitHub Copilot CLI converter.

Design decision D3: separate file, not a flag on :mod:`transfer_kit.converters.copilot`.
The two hosts have distinct mental models — VS Code Copilot tools are
GUI-first (``runInTerminal``, ``editFiles``), Copilot CLI is a shell-native
tool with direct ``bash``/``grep``/``find``. Mixing them into one converter
produces a confusing tool-rewrite map that would degrade both outputs.

Emission layout (design spec §9 + §10):

* ``AGENTS.md`` at repo root — native Copilot CLI load, merged with a
  ``<!-- tk:pull-managed -->`` block for idempotent re-pull.
* ``.github/copilot-instructions.md`` — secondary bootstrap companion.
* ``.github/instructions/<name>.instructions.md`` — each non-agent skill.
* ``.github/agents/<name>.agent.md`` — each ``Skill(source="agent")``.
* ``.mcp.json`` at workspace root — MCP servers (default location).
* ``docs/agent-foundry/_meta/<name>`` — docs-only meta files plus the
  runtime G2 shim.
* ``DEPENDENCIES.md`` — rendered passthrough of agent-foundry deps docs
  with compat report annotations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transfer_kit.converters.base import (
    BaseConverter,
    rewrite_tool_references,
    strip_frontmatter,
)
from transfer_kit.core.path_rewriter import inject_env_shim, rewrite_paths
from transfer_kit.models import (
    ClaudeEnvironment,
    EnvVar,
    McpServer,
    MetaFile,
    ProjectConfig,
    Skill,
)

# Managed-block sentinels. Keep byte-identical to the template fragments so
# the generator and the loader agree (§15 idempotent re-pull).
_BLOCK_BEGIN = "<!-- tk:pull-managed-begin v0.3.0 -->"
_BLOCK_END = "<!-- tk:pull-managed-end -->"

# Path to the canonical G2 shim source bundled with transfer_kit. Synthesised
# rather than read at module import so tests can stub it if needed.
_G2_SHIM_DATA_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "gates_g2_shim.py"
)

# Path to the Copilot CLI onboarding template fragment shipped with
# transfer_kit. Emitted even when the source has no project CLAUDE.md so
# the host repo always gets the ``<!-- tk:pull-managed -->`` block that
# teaches its agents how to invoke ``transfer-kit pull``.
_COPILOT_CLI_TEMPLATE = (
    Path(__file__).resolve().parent.parent / "templates" / "host_agents" / "copilot_cli.md"
)


def _managed_block(body: str) -> str:
    """Wrap ``body`` in the tk:pull-managed block markers."""
    return f"{_BLOCK_BEGIN}\n{body.rstrip()}\n{_BLOCK_END}\n"


class CopilotCliConverter(BaseConverter):
    """Convert a :class:`ClaudeEnvironment` to the GitHub Copilot CLI layout."""

    target_name = "copilot-cli"

    # Workspace placeholder substituted into path_rewriter templates.
    workspace: str = "."

    # -- skills ----------------------------------------------------------

    def convert_skills(self, skills: list[Skill]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for skill in skills:
            body = strip_frontmatter(skill.content)
            body = rewrite_tool_references(body, self.target_name)
            body = rewrite_paths(body, self.target_name, self.workspace)
            description = skill.frontmatter.get("description", skill.name)
            apply_to = skill.frontmatter.get("applyTo", "**")
            frontmatter = (
                "---\n"
                f"name: {skill.name}\n"
                f"description: {description}\n"
                f"applyTo: '{apply_to}'\n"
                "---\n"
            )
            rel = f".github/instructions/{skill.name}.instructions.md"
            results[rel] = frontmatter + body
        return results

    # -- agents ----------------------------------------------------------

    def convert_agents(self, agents: list[Skill]) -> dict[str, Any]:
        """Emit one ``.github/agents/<name>.agent.md`` per :class:`Skill` with ``source="agent"``.

        Frontmatter is the minimal Copilot-CLI shape: ``name``,
        ``description``, optional ``model``, optional ``tools``. The source
        frontmatter's ``description`` is honoured; ``tools`` is only
        propagated when present on the source (keeps the file terse).
        """
        results: dict[str, Any] = {}
        for agent in agents:
            body = strip_frontmatter(agent.content)
            body = rewrite_tool_references(body, self.target_name)
            body = rewrite_paths(body, self.target_name, self.workspace)
            description = agent.frontmatter.get("description", agent.name)
            fm_lines = [
                "---",
                f"name: {agent.name}",
                f"description: {description}",
            ]
            if "model" in agent.frontmatter:
                fm_lines.append(f"model: {agent.frontmatter['model']}")
            if "tools" in agent.frontmatter:
                fm_lines.append(f"tools: {agent.frontmatter['tools']}")
            fm_lines.append("---")
            rel = f".github/agents/{agent.name}.agent.md"
            results[rel] = "\n".join(fm_lines) + "\n" + body
        return results

    # -- meta files ------------------------------------------------------

    def convert_meta(self, meta_files: list[MetaFile]) -> dict[str, Any]:
        """Emit ``docs/agent-foundry/_meta/`` docs + G2 shim.

        The compat filter has already pruned claude-only entries, so
        whatever survives into ``meta_files`` is either ``portable``,
        ``degraded`` (rare on meta), or ``docs-only``. The converter
        treats all three as emit-to-docs — Copilot CLI never tries to
        *execute* the full gates.py; only the G2 shim is runtime.
        """
        results: dict[str, Any] = {}
        for m in meta_files:
            content = m.content
            if m.name.endswith(".py"):
                content = inject_env_shim(content, m.name, self.target_name)
            content = rewrite_paths(content, self.target_name, self.workspace)
            rel = f"docs/agent-foundry/_meta/{m.name}"
            results[rel] = content

        # README banner that explains the subset — only synthesised if
        # there are any meta files to emit.
        if meta_files:
            results["docs/agent-foundry/_meta/README.md"] = _META_README_BANNER

        return results

    def emit_template_fragment(self) -> dict[str, str]:
        """Emit the host-agent onboarding template fragment into ``AGENTS.md``.

        Always emits (design spec §10). The template already contains the
        ``<!-- tk:pull-managed-begin -->`` / end markers so the
        :func:`transfer_kit.core.pull._merge_managed` path will preserve
        user edits outside the block on re-pull.
        """
        if not _COPILOT_CLI_TEMPLATE.is_file():  # pragma: no cover — shipped with package
            return {}
        body = _COPILOT_CLI_TEMPLATE.read_text(encoding="utf-8")
        return {"AGENTS.md": body}

    def emit_g2_shim(self) -> dict[str, str]:
        """Emit the G2-only schema validator shim as a runtime artifact.

        Callers (pull.py) invoke this after :meth:`convert_meta` when the
        compat report's ``gates_g2_shim_emit`` is True. Kept as a separate
        method rather than folded into ``convert_meta`` because the shim
        is a SYNTHESIS RULE (see compat_matrix.yaml comment): it is not
        on the source side, so ``convert_meta`` never sees it as a
        :class:`MetaFile`.
        """
        if not _G2_SHIM_DATA_FILE.is_file():
            return {}
        shim_src = _G2_SHIM_DATA_FILE.read_text(encoding="utf-8")
        shim_src = rewrite_paths(shim_src, self.target_name, self.workspace)
        return {"docs/agent-foundry/_meta/gates_g2_shim.py": shim_src}

    # -- project config / MCP / env --------------------------------------

    def convert_project_config(self, config: ProjectConfig) -> dict[str, Any]:
        """Emit ``AGENTS.md`` (native load) + ``.github/copilot-instructions.md`` (companion).

        The copilot-cli host loads ``AGENTS.md`` from the repo root
        directly; the ``.github/copilot-instructions.md`` companion keeps
        cross-tool consistency with the VS Code Copilot converter.
        """
        if not config.claude_md:
            return {}
        body = strip_frontmatter(config.claude_md)
        body = rewrite_tool_references(body, self.target_name)
        body = rewrite_paths(body, self.target_name, self.workspace)
        return {
            "AGENTS.md": _managed_block(body),
            ".github/copilot-instructions.md": _managed_block(body),
        }

    def convert_mcp_servers(self, servers: list[McpServer]) -> dict[str, Any]:
        """Emit workspace-scoped ``.mcp.json``.

        User-global emission (``~/.copilot/mcp-config.json``) is gated on a
        caller flag threaded through pull's CLI; this default sticks to
        the workspace scope, which is what ``transfer-kit pull`` produces
        unless the user opts in.
        """
        if not servers:
            return {}
        mcp: dict[str, Any] = {"servers": {}}
        for srv in servers:
            mcp["servers"][srv.name] = srv.config
        return {".mcp.json": mcp}

    def convert_env_vars(self, env_vars: list[EnvVar]) -> dict[str, Any]:
        if not env_vars:
            return {}
        lines: list[str] = ["#!/usr/bin/env bash", "# Copilot CLI environment variables", ""]
        for var in env_vars:
            if var.is_secret:
                lines.append(f"# {var.name}=<set manually>")
            else:
                lines.append(f'export {var.name}="{var.value}"')
        return {"copilot-cli-env.sh": "\n".join(lines) + "\n"}

    # -- orchestration ---------------------------------------------------

    def convert_all(self, items: ClaudeEnvironment | None = None) -> dict[str, Any]:
        """Orchestrate the full Copilot CLI emission from a filtered env.

        Includes the G2 shim synthesis when the target is listed as
        ``portable`` in the matrix.
        """
        env = items or self.env
        results: dict[str, Any] = {}
        regular_skills = [s for s in env.skills if s.source != "agent"]
        agent_skills = [s for s in env.skills if s.source == "agent"]
        results.update(self.convert_skills(regular_skills))
        if agent_skills:
            results.update(self.convert_agents(agent_skills))
        for proj in env.projects:
            results.update(self.convert_project_config(proj))
        results.update(self.convert_mcp_servers(env.mcp_servers))
        results.update(self.convert_env_vars(env.env_vars))
        if env.meta_files:
            results.update(self.convert_meta(env.meta_files))
        # G2 shim is always synthesised for copilot-cli (compat matrix entry
        # ``meta.gates.py.g2-only: portable``). Pull may further gate this
        # but the converter defaults to emitting when data file is available.
        results.update(self.emit_g2_shim())
        # Template fragment — design spec §10; always emit so AGENTS.md
        # always exists for host agent consumption. If the source env had
        # a project CLAUDE.md the earlier convert_project_config call has
        # already populated AGENTS.md; in that case the fragment is
        # merged in at write time via the managed-block path.
        if "AGENTS.md" not in results:
            results.update(self.emit_template_fragment())
        return results


# Banner prepended to the docs/agent-foundry/_meta/README.md explaining why
# these Python files are here as docs, not runtime.
_META_README_BANNER = """\
# agent-foundry _meta files (reference)

These files come from the upstream
`joogy06/agent-foundry` skills/_meta/ directory. They are included here
as REFERENCE DOCUMENTATION — they are not part of the Copilot CLI runtime.

For schema validation (the G2 gate) a host-portable subset is provided at
`gates_g2_shim.py` in this directory. That shim IS runtime — you can
invoke it with:

```
python3 docs/agent-foundry/_meta/gates_g2_shim.py G2 progress/contract-map.yaml
```

G1 (HMAC-signed contract map) and G3 (bob-owned claims ledger) require
Claude Code + forge runtime and are intentionally absent on this host.
"""


__all__ = ["CopilotCliConverter"]
