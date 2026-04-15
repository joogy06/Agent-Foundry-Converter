# Project History

## 2026-04-15 — v0.3.0 Released (CI Green, Tag + GitHub Release Live)

### Post-merge CI cleanup
- Fix `path_rewriter.py`: `re.sub` was parsing Windows path backslashes (`C:\Users\...`) as regex replacement escapes, raising `KeyError: '\\U'` on 6 `test_pull` jobs. Wrapped replacement in a `lambda _m: replacement` to bypass `parse_template`. Added regression test (`test_rewrite_windows_workspace_with_backslash_escape_chars`).
- Fix 3 pre-existing Windows test biases (failing on master since 2026-04-13):
  - `test_env::test_apply_creates_file` and `test_apply_updates_existing_block` — tests asserted POSIX `export NAME="value"` but `EnvManager.apply()` correctly emits PowerShell `$env:NAME = 'value'` on Windows. New `_expected_line()` helper renders per-platform.
  - `test_importer::test_importer_rejects_absolute_path_in_tar` — regex `match="Unsafe path"` failed on Windows where `Path("//etc/passwd")` is not absolute and the importer falls through to "Path escapes target directory". Regex now accepts both messages.
- Self-inflicted regression on `test_render_block` (over-edited in the platform-aware pass) reverted — `render_block()` is a platform-neutral classmethod that always emits POSIX `export` syntax.

### Release
- Annotated tag `v0.3.0` pushed.
- GitHub release `v0.3.0 — Agent-Foundry Pull + Copilot CLI converter` published with the [0.3.0] CHANGELOG section as notes.
- CHANGELOG restructured: `[Unreleased] — v0.3.0` promoted to `[0.3.0] — 2026-04-15`. Unshipped Smart Export and queued P0 bug fixes moved to a new `[Unreleased]` section.
- 204 tests pass on 12/12 CI jobs (Ubuntu/macOS/Windows × Python 3.10/3.11/3.12/3.13). First fully-green CI run since 2026-04-13.

### Notes for next session
- PAT in `.git/config` flagged but not yet rotated/moved (terminal is trusted; cleanup path optional).
- Forge contract-map signing requires `session.key` read as **bytes** (no `.strip()`) to match `gates.py G1` canonical HMAC. Caused a one-iteration retry during Step 8a.2.
- Gemini direct CLI invocation broken in this session; reach Gemini via MCP `ask-gemini` instead. Memory note saved.

---

## 2026-04-15 — Agent-Foundry Pull (v0.3.0) — Implemented

### bob executed the approved design end-to-end

All 7 work packages landed in a single sequential execution (no agent-teams;
the WPs are heavily sequential on shared files so parallel execution would
have merge-conflicted). 203 tests pass (132 baseline preserved + 71 new).
G1/G2 gates pass, ledger pinned to contract-map revision 1.

**Delivered:**
- `transfer_kit/models.py` — `MetaFile` transit dataclass; `ClaudeEnvironment.source_kind` + `meta_files` + `dependency_docs` fields (additive).
- `transfer_kit/core/foundry_loader.py` — ingest-edge loader for agent-foundry layout.
- `transfer_kit/core/scanner.py` — `root=` parameter override (backwards-compatible).
- `transfer_kit/core/path_rewriter.py` — target-specific path rewrites + env-var shim injector + Windows shebang helper.
- `transfer_kit/core/url_sanitizer.py` — credential scrubber.
- `transfer_kit/core/compat.py` — compat matrix loader + `filter_env` with content-marker detection and tier filtering.
- `transfer_kit/data/compat_matrix.yaml` — declared portability matrix.
- `transfer_kit/data/gates_g2_shim.py` — host-portable G2 validator (G1/G3 stay Claude-only).
- `transfer_kit/core/xref_resolver.py` — dangling-ref report + transitive include.
- `transfer_kit/converters/copilot_cli.py` — GitHub Copilot CLI converter.
- `transfer_kit/converters/base.py` — `convert_agents`/`convert_meta`/`convert_deps` hooks (default no-op).
- `transfer_kit/converters/copilot.py` — Phase A fix: per-skill `applyTo` from frontmatter.
- `transfer_kit/converters/gemini.py` — Phase A fix: `scripts`/`references`/`assets` subdirectory passthrough.
- `transfer_kit/core/pull.py` + `transfer_kit/cli.py` `pull` subcommand + `interactive.py` menu entry.
- `transfer_kit/templates/host_agents/{copilot,copilot_cli,gemini}.md` onboarding fragments.
- 7 new test files: `test_foundry_loader.py`, `test_url_sanitizer.py`, `test_path_rewriter.py`, `test_compat_matrix.py`, `test_xref_resolver.py`, `test_converter_copilot_cli.py`, `test_pull.py`.
- `tests/fixtures/agent_foundry/` — 4-skill / 2-agent / 2-meta synthetic mini-repo.

**Verified success criteria (design spec §24):**
- Happy path `transfer-kit pull /tmp/agent-foundry-recon --target copilot-cli --tier standard` completes in ~2s and writes 141 files.
- Re-run is idempotent (0 files written second pass).
- Minimal tier produces a narrower output (140 files) and surfaces dangling refs.
- URL with PAT → credentials scrubbed + stderr warning.
- Malformed URL → exit 2, no partial write.
- `gates_g2_shim.py` exits 0 on a valid contract-map and 2 on a malformed one when run standalone outside a Claude host.
- 132 baseline tests + 71 new tests = 203 passing.

---

## 2026-04-15 — Agent-Foundry Pull Design

### Design spec completed
- Design spec: `docs/plans/2026-04-15-agent-foundry-pull-design.md` (25 sections)
- Forge cycle with Claude + Codex design exploration (Gemini unavailable this session due to GCP API permission; memory updated to route via MCP `ask-gemini` next session)
- Four approaches explored (A minimal, B full dataclasses, C thin wrapper, D Codex source-compiler); triple-challenger review converged on hybrid C+D+A architecture.

**Key decisions:**
1. Hybrid C+D+A: parameterize Scanner(root=), new foundry_loader.py (ingest-edge isolation), reuse existing converter pipeline. No new Agent/Gate dataclasses (defer B).
2. Gates: (a+G2) emit _meta/ as docs on non-Claude targets + port G2 schema validator as runtime. G1/G3 remain Claude+forge-only.
3. New `copilot_cli.py` converter (separate file, not a variant flag).
4. New utilities: path_rewriter.py, url_sanitizer.py, compat.py, xref_resolver.py, pull.py.
5. compat_matrix.yaml declares per-artifact × per-target portability + EXCLUDE list.

**7 work packages, ~1,630 LOC, 4-6 engineer days estimated.**

**Explicit limitation (blind spot):** agent runtime behavior (Task tool, hooks, claims) does NOT port. Agents emit as degraded (prose-only) on non-Claude hosts. Documented in compat matrix.

---

## 2026-04-13 — Public Release to GitHub

### Published to https://github.com/joogy06/Agent-Foundry-Converter
- Full security review: scanned for secrets, PII, internal paths, credentials. Codebase clean.
- Rewrote all 33 commit authors from internal identity to `TadasRemeikis <tadasremeikis@gmail.com>` via `git filter-repo --mailmap`.
- Scrubbed internal path (`/mnt/data/dev04/transfer_kit`) from all blob contents in git history.
- Stripped all `Co-Authored-By: Claude` trailers from commit messages.
- Removed standalone scripts (`deploy_skills.py`, `folder_to_txt.py`) and internal design docs (`docs/superpowers/`) from repo and git history — repo now contains only the core transfer_kit package.
- Replaced `REPLACE_ME` placeholders with `joogy06/Agent-Foundry-Converter`.
- Added author + project URLs to `pyproject.toml`.
- Bumped `cryptography>=46.0.5,<47` to resolve CVE-2026-26007 (both Dependabot alerts auto-closed).
- Added `tasks.md` to `.gitignore` (internal project management).
- 132 tests passing, 0 Dependabot alerts.

**Note:** GitHub contributor cache may show a stale "claude" contributor for up to 24h after the force push. All Co-Authored-By lines are confirmed removed from history.

---

## 2026-04-11 — Pre-Publication Audit (second pass)

- Re-audited codebase for secrets, PII, and machine paths.
- Codebase clean: no real secrets, test fixtures all synthetic.
- Fixed remaining local machine path in `docs/superpowers/plans/2026-03-15-transfer-kit-plan.md:72` (replaced with `<repo-root>`).
- Sanitized documentation files for public release.

---

## 2026-04-10 — Pre-Publication Audit & Cleanup

- Security audit: reviewed entire codebase for secrets, PII, machine paths. Verdict: safe after fixes.
- Deleted generated output directories and archive files containing private paths.
- Added: `LICENSE` (MIT), `CHANGELOG.md`, `.github/workflows/ci.yml` (3 OS x 4 Python matrix), `transfer_kit/py.typed` marker.
- Expanded `.gitignore` for comprehensive coverage.
- Fixed `pyproject.toml`: version 0.1.0 -> 0.2.0, `cryptography>=44,<46` (CVE fixes), upper bounds on all deps, classifiers, pytest config.
- Updated `README.md`: status banner, badges, contributing section.
- 132 tests passing.

---

## 2026-03-31 — v0.3.0 Design: Smart Export Pipeline

### Design spec completed (not yet implemented)
- Design spec: `docs/superpowers/specs/2026-03-30-smart-export-design.md` (16 sections)

**Design exploration** identified 39 codebase issues:
- 6 critical bugs (version mismatch, shell injection, GPG, sync staging)
- 8 high gaps (no agents, no env awareness, no self-test, tool map divergence)
- 10 medium code quality issues
- 5 innovation opportunities

**Design decisions made:**
1. Two-layer export pipeline: Layer 1 (deterministic regex) + Layer 2 (AI semantic translation via `claude -p` / `codex exec`)
2. Portability classification: portable (~70 skills) / partial (~12) / claude-only (~13 + 3 agents)
3. `transfer-flow.md` deployment manifest — standalone + pointer in auto-loaded entry file
4. `REGISTRY.md` master ecosystem map — cascade diagram, cross-refs, capability requirements
5. Environment awareness: capability prober, analyzer, self-test.sh, failure-memory.json
6. Agent support: Agent model, scanner, converters (currently all 3 agents are claude-only)
7. `smart-export` CLI subcommand (not standalone script) — layers on existing `convert`
8. Innovations: failure memory (stateful self-healing), provider brokerage, offline skill capsules

**Implementation plan:** 9 phases (P0 bug fixes -> P1-P7 features -> P4.5 registry)
**Status:** Design approved, spec reviewed, ready for implementation

---

## 2026-03-27 — deploy_skills.py v1.1.0

### Standalone skill scanner & deployer
- `15eaeaa` feat: add cross-platform skill scanner & deployer (v1.1.0)
- `89e0156` docs: add PROJECT.md architecture overview, v0.2.0 plan, update index

Standalone Python script (no external dependencies) that:
- Detects 5 AI coding tools: Claude Code, GitHub Copilot, Gemini CLI, Windsurf, Cursor
- Scans all global + project-level skill locations per tool, per OS
- Deploys skills between tools with format conversion and tool name rewriting
- Falls back to user prompts when auto-detection fails
- Supports 2026 conventions: AGENTS.md, .agents/skills/, .cursor/rules/*/RULE.md, .github/agents/

Cross-platform review (Windows 11 + RHEL) identified and fixed 15 issues:
- 5 critical: substring rewriting corruption, CRLF/BOM handling, subprocess encoding, double-mapping
- 10 moderate: Windows reserved filenames, .cmd binary detection, Windsurf APPDATA path, Python version guard, Path.home safety, input() guards, overwrite protection, path component matching, extra PATH lookup, dead code removal

---

## 2026-03-24 — v0.2.0 Release & First Live Export

### First live conversion run
- Exported 78 skills from Claude Code to VS Code Copilot format
- Exported 78 skills from Claude Code to Gemini CLI format
- MCP and env sections excluded per user preference — skills only

### v0.2.0 — Bug Fixes, Platform Support, Feature Enhancements

- `4907701` chore: bump version to 0.2.0
- `07db220` test: add integration tests for import+compare and sync push
- `090bd7c` test: add functional CLI tests for scan, export, convert
- `bda1999` fix: frontmatter parser, Rich no_color, anonymize exports, type hint (M2, M4, M5, M7, M8)
- `099d215` feat: surface hooks and permissions in scan output (F3, F4)
- `dc589f0` feat: scan and export memory directory structure (F1, F2)
- `7ab3d3b` fix: Windows compat — tmpdir same fs, gpg2 fallback, posix paths, timestamps (W4, W5, W8, M3)
- `92ab75f` feat: PowerShell env var scanning, Windows python binary name (W2, W6)
- `61df978` feat: PowerShell env syntax, UTF-8 encoding, escape round-trip fix (W1, W3, M1)
- `b148883` feat: add get_shell_type(), fix PowerShell profile paths (W7)
- `3eb6362` chore: remove unused json import from windsurf converter
- `ec435f1` fix: Copilot MCP inputs, multi-project merge for all converters (H6, H9)
- `9424e11` fix: Gemini converter — correct skills path and settings location (H2, H3, H4)
- `aacdf5c` fix: update tool maps, context-aware rewriting, update all converter tests (H1, H5, H7, H8)
- `724a920` fix: mask secret values in env show output (C5)
- `8226c2b` fix: sync copy --from without --to no longer crashes (C4)
- `8b749d6` fix: harden tar path traversal — block absolute paths and symlinks (C3)
- `ad6e13d` fix: replace unsafe tar.extractall with safe extraction (C2)
- `d75cfb8` fix: import --compare crash — add extract_to() method (C1)

Key milestones:
- 5 critical bug fixes: import --compare crash, unsafe tar extraction, path traversal hardening, sync copy crash, secret masking
- 9 converter fixes: tool maps, context-aware rewriting, Gemini paths, Copilot MCP inputs, multi-project merge
- Windows/PowerShell support: shell type detection, PowerShell env syntax, UTF-8 encoding, profile paths
- New features: memory directory scanning, hooks and permissions surfacing
- Medium fixes: frontmatter parser, Rich no_color, anonymize exports, type hints, tmpdir same-fs
- Test coverage: functional CLI tests, integration tests for import+compare and sync push
- 132 tests passing

---

## 2026-03-15 — Initial Implementation

### v0.1.0 — Transfer Kit

- `09588e2` Add transfer-kit design specification
- `66ad557` Add implementation plan with 18 tasks across 8 chunks
- `7125a07` feat: implement transfer-kit v0.1.0 — full CLI tool
- `981edbd` Add compare & merge feature design spec
- `ac3a125` feat: add compare & merge with per-section interactive selection
- `245c571` fix: address QA review — security, correctness, and test improvements
- `c58cb39` docs: add README, project history, and file index

Key milestones:
- Design spec written and reviewed
- Implementation plan with 18 tasks across 8 chunks
- Core modules: scanner, exporter, importer, sync, crypto
- Converters: Gemini CLI, GitHub Copilot, Windsurf
- CLI: Click subcommands + questionary interactive mode
- Compare & merge feature with per-section diffing
- QA review: 5 critical fixes (path traversal, secret leakage, sync CLI, manifest alignment)
- Project documentation: README, history, file index
- 108 tests passing
