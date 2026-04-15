# Agent-Foundry Pull & Host-IDE Convergence — Design Spec

**Date:** 2026-04-15
**Target version:** transfer_kit v0.3.0 (this feature ships standalone; existing Smart Export P0–P7 remains a parallel track)
**Status:** Design approved (user confirmed hybrid C+D+A, gates=a+G2, copilot_cli=separate file)
**Author:** Forge design team (Claude Opus 4.6 lead + Codex GPT-5.4 approach/challenger; Gemini unavailable this session)

---

## 1. Problem Statement

Transfer_kit today exports `~/.claude/` config and converts it to VS Code Copilot plugin, Gemini CLI, and Windsurf formats (export-only, Claude → target). The user needs the **inverse flow**: a host-IDE agent (running under VS Code Copilot, Gemini CLI, or GitHub Copilot CLI) should be able to pull the separate `joogy06/agent-foundry` payload (142 skills, 4 agents, `skills/_meta/` Python gates runtime, `docs/dependencies/` tiered manifest) and have transfer_kit convert it into the host's native format locally so the skills/agents/gates become usable on that host.

Secondary goal: ensure transfer_kit's existing converters still emit correct 2026-current paths/schemas for all target hosts, and close the gap that GitHub Copilot CLI has **no converter today**.

## 2. Scope

### In scope
- New CLI subcommand `transfer-kit pull <git-url-or-path>` accepting git URL or local folder path.
- New converter `transfer_kit/converters/copilot_cli.py` for GitHub Copilot CLI.
- Freshness alignment: verify/update existing converters against 2026 conventions (Phase A delta report).
- Host-agent onboarding templates: AGENTS.md / GEMINI.md / copilot-instructions.md fragments teaching host agents to invoke `transfer-kit pull`.
- `skills/_meta/` runtime port with targeted handling: full port to Claude target; G2 schema validator only to non-Claude targets; G1/G3 dropped as runtime, emitted as docs.
- Compatibility matrix declaring per-artifact portability per host.
- Cross-reference integrity resolver (tier filter safety).
- Credential scrubber on URL input.
- Windows/macOS/Linux CI matrix preservation.

### Out of scope
- Porting the forge skill itself to non-Claude hosts.
- MCP server implementation of transfer_kit (phase 2 if demand emerges).
- Behavioral equivalence of agent runtime primitives on non-Claude hosts (bob's `Task` tool, hooks, claims runtime). This is an explicit acknowledged limitation.
- Cursor converter (mentioned in PROJECT.md but deferred to a later release).
- LFS support on cloned repos.
- Existing v0.3.0 Smart Export P0–P7 plan (parallel track, not blocked by this).

## 3. Locked Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Hybrid C+D+A architecture; defer B's dataclasses.** | Smallest working diff (~750 LOC). Scanner parameterization (C) + narrow ingest loader (D) + template fragments (A). No new `Agent` / `Gate` / `DependencyManifest` dataclasses. Agents ride as `Skill(source="agent")`. |
| D2 | **Gates port = (a+G2):** emit `_meta/` as docs on non-Claude targets + port G2 schema validator as runtime there. | G1 requires `.forge/session.key` (Claude-only). G2 is pure schema validation, host-independent, catches ~80% of bugs. G3 requires claims ledger (Claude-only). Honest degradation. |
| D3 | **Separate `copilot_cli.py` converter** (not a variant flag on `copilot.py`). | Different host mental model (Bash available, AGENTS.md native, different MCP schema). Keeps test matrix readable. |

## 4. Architecture

### 4.1 Component map (post-implementation)

```
transfer_kit/
├── cli.py                        ← add `pull` subcommand
├── interactive.py                ← add `pull` menu option
├── models.py                     ← add ClaudeEnvironment.source_kind flag; add transit `MetaFile` (no new domain dataclasses — agents/gates stay as Skill/MetaFile)
├── core/
│   ├── scanner.py                ← parameterize Scanner(root=None)
│   ├── foundry_loader.py         ← NEW: walks agent-foundry layout, returns ClaudeEnvironment
│   ├── path_rewriter.py          ← NEW: generalized path rewriting utility
│   ├── compat.py                 ← NEW: loads compat_matrix.yaml, filters artifacts per target
│   ├── xref_resolver.py          ← NEW: cross-reference integrity check under tier filter
│   ├── url_sanitizer.py          ← NEW: strips credentials from git URLs
│   └── pull.py                   ← NEW: orchestrates clone→load→compat→xref→convert→write
├── converters/
│   ├── base.py                   ← extend with convert_agents, convert_meta, convert_deps hooks (default no-op)
│   ├── copilot.py                ← add AGENTS.md emission; minor path-scope frontmatter fix
│   ├── copilot_cli.py            ← NEW: GitHub Copilot CLI converter
│   ├── gemini.py                 ← add resource subdirs (scripts/references/assets) pass-through
│   └── windsurf.py               ← unchanged in this release
├── data/
│   └── compat_matrix.yaml        ← NEW: per-artifact × per-target portability declarations
└── templates/
    └── host_agents/
        ├── copilot.md            ← fragment dropped into .github/copilot-instructions.md
        ├── copilot_cli.md        ← fragment dropped into AGENTS.md
        └── gemini.md             ← fragment dropped into GEMINI.md
```

### 4.2 Data flow

```
User command: transfer-kit pull <url|path> --target X [--tier Y] [--output Z]
    │
    ▼
url_sanitizer.py ── strip credentials from URL, warn if present ──▶ sanitized_url
    │
    ▼
pull.py ──┬── if URL: git clone --depth=1 --branch <ref or default> ──▶ temp dir
          └── if path: use in place
    │
    ▼
foundry_loader.py ── walk skills/ agents/ skills/_meta/ docs/dependencies/
                     → ClaudeEnvironment(source_kind="agent-foundry", skills=[...], projects=[], ...)
    │
    ▼
compat.py ── load compat_matrix.yaml, filter ClaudeEnvironment per target + EXCLUDE list
    │
    ▼
xref_resolver.py ── walk agent/skill bodies for name refs; under --tier, warn on dangling
    │
    ▼
converters/<target>.py ── convert_all(env) → dict[rel_path, content]
                          (existing path), plus new convert_agents / convert_meta / convert_deps hooks
    │
    ▼
path_rewriter.py ── applied inside rewrite_tool_references AND on _meta/ content
                    (rewrites ~/.claude/skills/... → host-specific paths)
    │
    ▼
output writer ── idempotent write to --output dir with managed-block markers
                 + DEPENDENCIES.md rendered from compat_matrix + agent-foundry's deps docs
                 + template fragments from templates/host_agents/<target>.md
```

## 5. Data Model Changes (Minimal)

### 5.1 `models.py` — one field added

```python
# transfer_kit/models.py

from typing import Literal

@dataclass
class ClaudeEnvironment:
    skills: list[Skill] = field(default_factory=list)
    plugins: list[Plugin] = field(default_factory=list)
    mcp_servers: list[McpServer] = field(default_factory=list)
    # ... existing fields ...

    # NEW:
    source_kind: Literal["claude-home", "agent-foundry"] = "claude-home"
    meta_files: list["MetaFile"] = field(default_factory=list)  # optional; empty for claude-home source

@dataclass
class MetaFile:
    """Files under skills/_meta/ — runtime scripts, checklists, JSON configs.

    NOT a full Gate dataclass — just enough to carry the file through the pipeline.
    """
    name: str
    path: Path
    content: str
    kind: Literal["gate-script", "checklist", "families", "hook", "claims", "audit", "other"]
```

`MetaFile` is intentionally lightweight — it's a transit dataclass, not a domain model. If v0.3.0 Smart Export later needs a real `Gate` with exit codes / env contracts, B's design waits in the wings.

### 5.2 `Skill` — no change to shape; `source` field accepts new value

Current in-repo reality (verified): `Skill.source` is a free-form `str`, today taking values `"custom"` or `"plugin:<plugin_name>"` (e.g. `"plugin:superpowers"`). We do NOT narrow it to a `Literal`. We add `"agent"` as a third value used only for skills loaded from agent-foundry's `agents/*.md`.

**Bob must audit all `source ==` and `source in` filter sites in the repo before WP-1 lands** — the existing baseline is `{"custom", "plugin:*"}`, not `{"custom", "builtin"}` as earlier drafts assumed. Expected sites: `exporter.py`, `comparator.py`, possibly `converters/*.py`. Round-trip export/import must preserve `source="agent"` without coercing to another value.

## 6. Scanner Parameterization (Decision D1, chassis from C)

```python
# transfer_kit/core/scanner.py — line 56-63 change

class Scanner:
    def __init__(
        self,
        claude_home: Path | None = None,
        shell_profiles: list[Path] | None = None,
        root: Path | None = None,                    # NEW
        layout: Literal["claude-home", "agent-foundry"] = "claude-home",  # NEW
    ) -> None:
        self.claude_home = root or claude_home or get_claude_home()
        self.layout = layout
        # ...
```

For `layout == "claude-home"`: existing behavior, 132 tests pass unchanged.
For `layout == "agent-foundry"`: delegates to `FoundryLoader` — scanner is *not* taught foreign layouts directly (per challenger CC).

## 7. Foundry Loader (Decision D1, ingest-edge isolation from D)

```python
# transfer_kit/core/foundry_loader.py  (NEW, ~150 LOC)

class FoundryLoader:
    """Compile an agent-foundry repo into a ClaudeEnvironment.

    Isolation rationale: Scanner targets canonical Claude-home; FoundryLoader
    targets the joogy06/agent-foundry repo shape. Different jobs, different files.
    """
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self) -> ClaudeEnvironment:
        return ClaudeEnvironment(
            skills=self._load_skills() + self._load_agents_as_skills(),
            mcp_servers=[],
            projects=[],            # CRITICAL: do NOT flatten agents into ProjectConfig
            meta_files=self._load_meta(),
            source_kind="agent-foundry",
        )

    def _load_skills(self) -> list[Skill]:
        # Walk skills/*/SKILL.md; bundle scripts/references/assets as frontmatter hints
        ...

    def _load_agents_as_skills(self) -> list[Skill]:
        # agents/*.md → Skill(source="agent", frontmatter gets "kind: agent")
        ...

    def _load_meta(self) -> list[MetaFile]:
        # skills/_meta/*.py|*.md|*.json — classify by extension + filename
        # gates.py → kind="gate-script"; hard-rules-checklist.md → kind="checklist"; etc.
        ...
```

## 8. Path Rewriter (Decision D1, from C)

```python
# transfer_kit/core/path_rewriter.py  (NEW, ~100 LOC)

# Rules are (pattern, replacement) tuples, applied in order (more-specific first).
_RULES: dict[str, list[tuple[str, str]]] = {
    "claude": [],  # identity
    "copilot": [
        (r"~/\.claude/skills/_meta/", "<workspace>/.github/_meta/"),
        (r"~/\.claude/skills/",        "<workspace>/.github/instructions/"),
        (r"~/\.claude/agents/",        "<workspace>/.github/agents/"),
    ],
    "copilot-cli": [
        (r"~/\.claude/skills/_meta/", "<workspace>/docs/agent-foundry/_meta/"),
        (r"~/\.claude/skills/",        "<workspace>/.github/instructions/"),
        (r"~/\.claude/agents/",        "<workspace>/.github/agents/"),
    ],
    "gemini": [
        (r"~/\.claude/skills/_meta/", "~/.gemini/_meta/"),
        (r"~/\.claude/skills/",        "~/.gemini/skills/"),
        (r"~/\.claude/agents/",        "~/.gemini/agents/"),
    ],
    "windsurf": [
        (r"~/\.claude/skills/_meta/", "<workspace>/.windsurf/_meta/"),
        (r"~/\.claude/skills/",        "<workspace>/.windsurf/rules/"),
    ],
}

def rewrite_paths(content: str, target: str, workspace: str = ".") -> str: ...
```

Applied inside `rewrite_tool_references` in `converters/base.py` AND directly on `MetaFile.content` before emission.

Known limitation (from challenger C): Python code in `_meta/gates.py` that builds paths at runtime via `Path.home()` or `os.path.expanduser()` cannot be rewritten textually. Mitigation: `gates.py` gets an env-var shim — a small prologue block injected by `path_rewriter.py` that reads `TRANSFER_KIT_SKILLS_ROOT` env var if present, else falls back to `~/.claude/skills/`. Host-agent template fragment sets this env var before invoking gates.

## 9. Copilot CLI Converter (Decision D3)

```python
# transfer_kit/converters/copilot_cli.py  (NEW, ~220 LOC)

class CopilotCliConverter(BaseConverter):
    target_name = "copilot-cli"

    # Tool rewrite map differs from VS Code Copilot — CLI HAS a Bash tool
    TOOL_REWRITES = {
        "Read": "read_file",
        "Edit": "write_file (after read_file)",
        "Bash": "bash",              # different from copilot.py — CLI has bash directly
        "Grep": "grep",
        "Glob": "find or ls",
        # ...
    }

    def convert_skills(self, skills) -> dict[str, Any]:
        # Skills without source="agent" → .github/instructions/{name}.instructions.md
        ...

    def convert_agents(self, agents: list[Skill]) -> dict[str, Any]:
        # Skills with source="agent" → .github/agents/{name}.agent.md
        # Frontmatter: {name, description, tools, model (optional)}
        ...

    def convert_project_config(self, cfg) -> dict[str, Any]:
        # Emits AGENTS.md at repo root (primary, native Copilot CLI load)
        # + .github/copilot-instructions.md (secondary, bootstrap-compatible)
        ...

    def convert_mcp_servers(self, servers) -> dict[str, Any]:
        # Default: workspace .mcp.json
        # Optional flag: ~/.copilot/mcp-config.json (user-global)
        ...

    def convert_meta(self, meta_files: list[MetaFile]) -> dict[str, Any]:
        # See §11 below — G2 port + docs for G1/G3
        ...
```

## 10. Template Fragments (from A)

```
templates/host_agents/
├── copilot.md          (~40 lines) — appended to .github/copilot-instructions.md under <!-- tk:pull-managed --> markers
├── copilot_cli.md      (~40 lines) — appended to AGENTS.md under <!-- tk:pull-managed --> markers
└── gemini.md           (~40 lines) — appended to GEMINI.md under <!-- tk:pull-managed --> markers
```

Each fragment contains:
1. One-line explainer ("This project can pull agent-foundry payloads via transfer-kit.")
2. Invocation pattern the host agent should use when user asks "pull agent-foundry" or similar
3. Flag defaults (target auto-detected, tier=standard default)
4. Failure modes (offline clone, disk full, idempotent re-run)

Fragments are **NOT** generated from source — they are static `.md` templates shipped with the package.

## 11. Compatibility Matrix + EXCLUDE List

```yaml
# transfer_kit/data/compat_matrix.yaml

schema_version: "1.0.0"

# Per-artifact × per-target portability
# Values: portable | degraded | claude-only | forge-only | excluded

artifacts:
  skill:
    claude: portable
    copilot: portable
    copilot-cli: portable
    gemini: portable
    windsurf: portable

  agent:
    claude: portable
    copilot: degraded       # host lacks Task tool; agent becomes prose-only
    copilot-cli: degraded
    gemini: degraded
    windsurf: degraded

  meta.gates.py:
    claude: portable
    copilot: docs-only      # emit to docs/agent-foundry/_meta/; G1/G3 dropped
    copilot-cli: docs-only
    gemini: docs-only
    windsurf: docs-only

  # NOTE: meta.gates.py.g2-only below is a SYNTHESIS RULE, not a source artifact.
  # It names a file that transfer-kit GENERATES (from templates/data/gates_g2_shim.py)
  # for non-Claude targets. Do not look it up on load — treat it as an emit-time decision.
  meta.gates.py.g2-only:
    claude: skip            # full gates.py serves this role; no g2-only shim emitted
    copilot: portable
    copilot-cli: portable
    gemini: portable
    windsurf: portable

  meta.hard-rules-checklist.md:
    claude: portable
    copilot: degraded       # becomes reference doc, not hook-enforced
    copilot-cli: degraded
    gemini: degraded
    windsurf: degraded

  meta.claims.py: claude-only
  meta.audit_spawn.py: claude-only
  meta.forge_reminder_hook.py: claude-only
  meta.pause_state.py: claude-only
  meta.trusted_runner.py: claude-only

  meta.skill-families.json: excluded        # Claude UX grouping, no port value
  meta.scan_hard_rules.py: claude-only

excludes:
  # Files matching these patterns never emit, regardless of target
  - "skills/**/tests/**"                # per-skill test dirs if any exist
  - ".github/**"                        # source repo metadata
  - ".git/**"
  - "**/__pycache__/**"
  - "**/.pytest_cache/**"

claude_ecosystem_only_markers:
  # Content-level markers that force `claude-only` classification
  # if found inside a file that would otherwise be portable
  - "/codex:"                           # Codex plugin slash commands
  - "ScheduleWakeup"                    # Claude-only tool
  - "CronCreate"                        # Claude-only tool
  - ".forge/session.key"                # Forge session artifact
  - "claims.apply_request_idempotent"   # Claims runtime
```

`compat.py` loads this, filters the `ClaudeEnvironment`, and emits a report: `{portable: N, degraded: N, claude-only-dropped: N, excluded: N}` printed on every `pull` run.

## 12. G2-Only Schema Validator Port (Decision D2, the +G2 piece)

```python
# For non-Claude targets: emit transfer_kit/data/gates_g2_shim.py  (~60 LOC)
# Contains only G2 logic extracted from agent-foundry's skills/_meta/gates.py

#!/usr/bin/env python3
"""gates_g2_shim.py — host-portable schema validator for contract-map.yaml.

This is a SUBSET of agent-foundry/skills/_meta/gates.py.
G1 (HMAC signing) and G3 (claims ledger) require Claude+forge runtime and
are NOT included here. If you need full gate enforcement, use Claude Code.

Usage:
    python3 gates_g2_shim.py G2 <path-to-contract-map.yaml>

Exit codes: 0=pass, 2=fail (schema violation), 3=env error.
"""
# ... G2 logic only: schema validation, V1–V15 field checks, semantic_type
# registry, technical closed list. No HMAC, no session, no ledger.
```

Lives at `<workspace>/docs/agent-foundry/_meta/gates_g2_shim.py` on non-Claude targets.
Banner README explains the subset.

## 13. Cross-Reference Resolver (Challenger CC2)

```python
# transfer_kit/core/xref_resolver.py  (NEW, ~80 LOC)

def resolve_refs(env: ClaudeEnvironment, tier: str) -> XRefReport:
    """Walk agent/skill bodies for `name` references. Return a report of
    which refs resolve under the tier filter and which are dangling.

    Tier filter applied externally via compat_matrix + tier rules (see §11).
    Resolver does NOT drop files — it warns. User can re-run with a different
    tier or let transfer-kit auto-include transitive deps via --resolve-refs.
    """
```

The `--resolve-refs` flag (default: warn-only): when true, transitively includes any skill referenced by an included agent or skill even if the tier filter would have dropped it.

## 14. URL Credential Scrubber (Challenger CC6)

```python
# transfer_kit/core/url_sanitizer.py  (NEW, ~30 LOC)

def sanitize_git_url(url: str) -> tuple[str, bool]:
    """Return (sanitized_url, had_credentials).

    Strip userinfo (any `user:pass@` or `ghp_xxx@`) from the URL.
    Warn on stderr if credentials were present.
    """
```

Called at the start of `pull.py` before any git operation. Any embedded PAT/token is removed before logging or process invocation.

## 15. Idempotent Re-Pull (Challenger CC5)

- All generated files are written with **managed-block markers** where applicable:
  ```
  <!-- tk:pull-managed-begin v0.3.0 <sha1-of-inputs> -->
  ...generated content...
  <!-- tk:pull-managed-end -->
  ```
- Re-running `pull` against the same target dir with the same inputs is a no-op (sha1 match → skip write).
- Re-running with different inputs replaces ONLY the content between markers; user edits outside markers are preserved.
- Files with no block markers (e.g. full-file replacements like `.github/instructions/<name>.instructions.md`) default behavior: **if content hash matches, no-op; if hash differs, abort with a conflict list unless `--force` or `--preserve` is set.** `--force` overwrites everything; `--preserve` skips and writes a `.conflict` sidecar listing what would have changed.

### 15.1 Tier-change semantics (second-run with different `--tier`)

When a subsequent `pull` narrows the tier (e.g., `standard → minimal` drops 40 skills):
- Files present in the previous run but **not** in the new tier are moved to `<output>/.tk-pull-archive/<timestamp>/` (not deleted outright) and the change is printed in the summary.
- Files introduced by the new tier are written normally (subject to the conflict rules above).
- Use `--no-archive` to hard-delete instead of archive. `--dry-run` reports what would move / delete without touching files.

Tier widening (e.g., `minimal → standard`) is additive — new files are written, existing files subject to conflict rules.

## 16. CLI Surface

```
transfer-kit pull <git-url-or-path> [OPTIONS]

Arguments:
  SOURCE  Git URL (https://... or git@...) or local filesystem path.

Options:
  --target TEXT         copilot | copilot-cli | gemini | windsurf  [default: auto-detect]
  --tier TEXT           minimal | standard | full  [default: standard]
  --output DIR          Output directory.  [default: ./pulled-foundry]
  --ref TEXT            Git ref (branch/tag/sha) to check out.  [default: main]
  --resolve-refs        Transitively include dependencies of included skills/agents.
  --force               Overwrite files even if content hashes differ.
  --preserve            Skip overwrites; report conflicts.
  --dry-run             Compute changes, don't write.
  -v, --verbose         Log every file operation.
```

**Auto-detect target:** check env var `COPILOT_CLI_VERSION` → `copilot-cli`; else `GEMINI_CLI` → `gemini`; else `VSCODE_PID` with Copilot extension → `copilot`; else fail.

## 17. Phase A Freshness Fixes (existing converters)

Based on `/tmp/forge-wave1/phase-a-delta.md`:

### copilot.py
- Line 30: hardcoded `applyTo: '**'` → read per-skill from frontmatter if present, fallback to `'**'`.
- Add AGENTS.md emission at repo root (mirrors what we do in copilot_cli.py), for cross-tool consistency.

### gemini.py
- **Already clean.** Add pass-through for `scripts/`, `references/`, `assets/` subdirs when present in source skills (not needed for `~/.claude` source since scanner flattens, but needed for agent-foundry source which preserves subdirs).

### windsurf.py
- No changes in this release.

## 18. Dependencies Rendering

`pull.py` emits a `<output>/DEPENDENCIES.md` document per run, built from:
1. Source: `<foundry>/docs/dependencies/{README,agent-graph,local-tools,mcp-servers}.md`
2. Compat matrix filtering: mark each required dep as `[required | optional | N/A for this target]`
3. Tier table: show what Minimal / Standard / Full each require.
4. Install hints per host OS (leveraging existing `prereqs.py`).

No structured parsing of the source markdown (challenger B4 warned: fragile). Instead, pass-through with annotations added as fenced blocks.

## 19. Platform Portability

- **Shebangs:** `_meta/*.py` shebangs on Windows targets get rewritten from `#!/usr/bin/env python3` to a cross-platform wrapper pattern: keep the shebang (works on \*nix), add `.cmd` wrapper on Windows that runs `python`. `path_rewriter.py` owns shebang rewrite for the Windows target.
- **Path separators:** `path_rewriter.py` uses `posixpath` for URL-style paths, `os.path` only at write time.
- **Git clone on Windows:** CRLF concerns — pass `--config core.autocrlf=false` to git clone.
- **Python discovery:** `gates_g2_shim.py` header uses `#!/usr/bin/env python3` on \*nix, `.cmd` wrapper named `gates_g2_shim.cmd` on Windows invokes `python` (fallback: `py -3`).

## 20. Test Plan

### New test files
- `tests/test_foundry_loader.py` (~15 tests): fixture agent-foundry mini-repo at `tests/fixtures/agent_foundry/`; verify skills count, agents tagged correctly, meta_files classified.
- `tests/test_path_rewriter.py` (~13 tests): round-trip rewriting, idempotence, collision rules, shebang rewrite, **env-var shim prologue correctly injects `TRANSFER_KIT_SKILLS_ROOT` lookup into `gates.py` for non-Claude targets**.
- `tests/test_compat_matrix.py` (~8 tests): load matrix, filter for each target, EXCLUDE list, claude_ecosystem_only_markers content-level detection.
- `tests/test_xref_resolver.py` (~6 tests): dangling refs, transitive inclusion.
- `tests/test_url_sanitizer.py` (~5 tests): PAT stripping, userinfo stripping, warn on credential presence.
- `tests/test_converter_copilot_cli.py` (~14 tests): AGENTS.md emission, custom agents dir, MCP workspace vs user, Bash tool in rewrite map.
- `tests/test_pull.py` (~10 tests): end-to-end with mock git, idempotent re-pull, --dry-run, --force/--preserve, --resolve-refs.

### Fixture
`tests/fixtures/agent_foundry/` — minimal repo with 4 skills, 2 agents, 2 meta files (one gate script, one checklist), one dep manifest. No real Claude-only runtime scripts.

### CI
Preserve 3-OS × 4-Python matrix. Add skip-marker for CI environments without `git` available (shouldn't happen; safety belt).

### Coverage target
Retain 132 baseline + add ~70 new = ~200 tests total. No regression in existing behavior.

## 21. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Agent-foundry upstream schema changes break pull | high | Compat matrix uses semantic markers; xref_resolver catches dangling refs at convert time. Pin `--ref` for reproducibility. |
| G2-only shim drifts from upstream gates.py | medium | Checksum upstream `gates.py` on each release; if checksum changes, CI fails until shim is re-audited. |
| Host-agent template fragments become stale (e.g. Copilot CLI changes AGENTS.md semantics) | medium | Template fragments are versioned; Phase A audit is re-run per transfer_kit release. |
| Windows shebang / python3 mismatch | medium | `.cmd` wrappers; integration test on Windows CI runner. |
| Idempotent re-pull clobbers user edits | high | Managed-block markers; content-hash conflict detection; `--preserve` flag. |
| Supply-chain: malicious agent-foundry fork cloned | medium | Credential scrubber; default clone is to temp dir (read-only to user's workspace until convert); document `--ref` pinning to commit SHA. |
| Bob (runtime orchestrator agent) doesn't work on Copilot CLI | high — but explicit | Compat matrix declares `agent: degraded`. Template fragments tell host user bob runs in "prose mode" without Task/claims/gates. Blind-spot accepted, documented. |

## 22. Explicit Non-Goals (Acknowledged Limitations)

1. **Agent runtime behavior equivalence.** The "one blind spot" from challenger's section 5: bob/alf/pa/wiki depend on Claude-specific primitives (Task tool, hooks, claims). We port the TEXT, not the BEHAVIOR. Host agents on Copilot CLI / Gemini CLI get a degraded experience. Documented in compat_matrix as `agent: degraded`.
2. **Full forge on non-Claude hosts.** Deferred indefinitely. Would require Task tool emulation, skill composition, hook system — effectively rebuilding Claude Code as a library.
3. **Cursor target.** Noted in PROJECT.md, not in this release.
4. **LFS.** Not needed for current agent-foundry; contract doesn't forbid future.
5. **MCP server wrapping of transfer_kit.** Phase 2 if user demand emerges. Current: shell CLI invocation only.
6. **Smart Export P0-P7.** Parallel track; not blocked by this feature.

## 23. Phasing (Work Breakdown for Bob)

Estimated effort: 4-6 engineer days across 7 WPs.

| WP | Name | Files | Est. LOC |
|----|------|-------|----------|
| WP-1 | Scanner parameterization + foundry_loader | scanner.py, foundry_loader.py, models.py (source_kind, MetaFile) | ~250 |
| WP-2 | path_rewriter + url_sanitizer utilities | path_rewriter.py, url_sanitizer.py, base.py integration | ~180 |
| WP-3 | compat_matrix + compat.py + EXCLUDE list | data/compat_matrix.yaml, compat.py | ~150 |
| WP-4 | xref_resolver | xref_resolver.py | ~100 |
| WP-5 | copilot_cli converter + Phase A fixes on copilot/gemini | converters/copilot_cli.py, copilot.py, gemini.py | ~280 |
| WP-6 | pull.py + CLI wiring + templates + G2 shim | pull.py, cli.py, interactive.py, templates/, data/gates_g2_shim.py | ~220 |
| WP-7 | Tests + CI + docs | tests/, README, CHANGELOG | ~450 |

**Total:** ~1,630 LOC (implementation + tests + data + templates).

## 24. Success Criteria

1. `transfer-kit pull https://github.com/joogy06/agent-foundry --target copilot-cli --output /tmp/test-out --tier standard` completes in under 60s on a fresh clone on a typical dev machine (CI may be slower; no hard wall-clock criterion in CI).
2. Output directory contains: `AGENTS.md` (merged with managed-block fragment), `.github/instructions/*` (skills), `.github/agents/*` (agents), `docs/agent-foundry/_meta/` (meta files as docs + G2 shim), `DEPENDENCIES.md` (rendered), `.mcp.json` (if MCP servers declared).
3. Re-running the same command is a no-op (idempotent).
4. Running with `--tier minimal` excludes skills not in the minimal tier; xref_resolver reports 0 dangling refs OR warns with explicit list.
5. Running against a URL with an embedded PAT strips credentials and warns.
6. CI passes on Ubuntu, macOS, Windows × Python 3.10/3.11/3.12/3.13.
7. 132 existing tests pass unchanged + ~70 new tests pass.
8. `gates_g2_shim.py` exits 0 on a valid contract-map.yaml and exits 2 on a malformed one when invoked on a non-Claude host.

## 25. Open Questions (for user pre-bob)

None — all prior open questions resolved by design decisions D1/D2/D3. Remaining ambiguity is inside implementation details (exact test fixtures, exact frontmatter shape for `.github/agents/*.agent.md` — deferred to bob).

---

**End of design spec.**

---

## 26. Component Contract Map

Generated by `component-contract-mapping@1.0.0` on 2026-04-15. Signed payload at `progress/contract-map.yaml.sig`. G2 validation: **PASS**.

| Component | Purpose | Inputs | Outputs | Callers | Callees | Flow Role |
|---|---|---|---|---|---|---|
| `url-sanitizer` | Strip credentials from git URLs | `raw_url` (url_http) | `sanitized_url` (url_http), `had_credentials` (_meta) | pull | — | — |
| `foundry-loader` | Compile agent-foundry repo → ClaudeEnvironment | `root` (internal_ref) | `env` (opaque) | pull | — | — |
| `compat` | Filter env per target/tier via compat_matrix.yaml | `env` (opaque), `target` (version), `tier` (version) | `filtered_env` (opaque), `report` (opaque) | pull | — | — |
| `xref-resolver` | Report dangling skill cross-references under tier | `env` (opaque), `tier` (version) | `report` (opaque) | pull | — | — |
| `path-rewriter` | Rewrite ~/.claude/ paths per target + shebang/shim | `content` (opaque), `target` (version), `workspace` (internal_ref) | `rewritten_content` (opaque) | copilot-cli-converter | — | — |
| `copilot-cli-converter` | Emit GitHub Copilot CLI layout from env | `env` (opaque) | `files` (opaque) | pull | path-rewriter | **terminal** |
| `pull` | Orchestrate end-to-end pull flow | `source` (url_http), `target` (version), `tier` (version), `output_dir` (internal_ref), `dry_run` (_meta) | `exit_code` (_meta) | — | all | **entry** |

**Declared flows:**
- **FLOW-001 (critical):** end-to-end pull — `pull → url-sanitizer → foundry-loader → compat → xref-resolver → copilot-cli-converter` — enters at `pull.source` with fixture `tests/fixtures/agent_foundry/`, terminates at `copilot-cli-converter.files`.

**New semantic types declared for this project:** none. All inputs use v1 registry values (`url_http`), `semantic_type: technical` from the closed list (`_meta`, `version`, `internal_ref`), or `kind: opaque` with `opaque_reason` + `opaque_fixture_source`. This is a developer-tool project — the domain-centric v1 registry does not apply to most fields.

**Scope note:** other existing converters (copilot, gemini, windsurf) are NOT listed as components because they receive only minor Phase A freshness fixes in this release (§17). They retain their current contracts. Only the 7 new/substantially-changed modules above are contract-mapped.
