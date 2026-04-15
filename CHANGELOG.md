# Changelog

All notable changes to Transfer Kit are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned — Smart Export (parallel track)

Design retained locally. Not blocked by and does not block the pull feature.

- Two-layer export pipeline (deterministic + AI-assisted semantic translation).
- Portability classification at export time.
- Capability prober, analyzer, self-test, failure-memory.
- `Agent` dataclass, `_scan_agents()`, Cursor converter.
- `REGISTRY.md`, `transfer-flow.md`, `smart-export` CLI subcommand.

### Queued P0 bug fixes (not yet shipped)

- `env.py` shell-escape gap (`!` and newlines not escaped).
- `crypto.py` GPG encryption missing `--batch` and recipient validation.
- `sync.py` using `repo.index.add("*")` instead of explicit file staging.
- `platform_utils.py` Windsurf Windows path.
- `cli.py` dead `Panel` import.

## [0.3.0] — 2026-04-15

### Added — Agent-Foundry Pull (inverse flow)

Design: `docs/plans/2026-04-15-agent-foundry-pull-design.md`.

- New CLI subcommand `transfer-kit pull <git-url-or-path>` for pulling the
  upstream `joogy06/agent-foundry` payload (skills, agents, meta runtime,
  dependency docs) into a host-IDE layout (Copilot, Copilot CLI, Gemini,
  Windsurf).
- New converter `transfer_kit/converters/copilot_cli.py` for GitHub Copilot
  CLI — emits `AGENTS.md`, `.github/agents/`, `.github/instructions/`,
  `docs/agent-foundry/_meta/`, `.mcp.json`, rendered `DEPENDENCIES.md`.
- New core modules: `foundry_loader.py`, `path_rewriter.py`,
  `url_sanitizer.py`, `compat.py`, `xref_resolver.py`, `pull.py`.
- Compatibility matrix (`transfer_kit/data/compat_matrix.yaml`) declaring
  per-artifact × per-target portability (portable / degraded / docs-only /
  claude-only / excluded). Includes content-marker detection for files that
  look portable by name but reference Claude-only runtime primitives.
- Host-portable G2 schema validator shim (`transfer_kit/data/gates_g2_shim.py`)
  shipped to non-Claude targets. G1 (HMAC signing) and G3 (claims ledger)
  are Claude-only and intentionally NOT ported.
- Host-agent onboarding template fragments under
  `transfer_kit/templates/host_agents/` that teach host agents how to
  invoke `transfer-kit pull`.
- Scanner parameterised with `root=<path>` override so tests and the pull
  pipeline can target non-default Claude-home locations without
  environment manipulation.
- Phase A freshness fixes on existing converters:
  - `copilot.py`: per-skill `applyTo` now honoured from source
    frontmatter (falls back to `'**'`).
  - `gemini.py`: `scripts/`, `references/`, `assets/` subdirectories
    preserved when the source skill uses the agent-foundry layout.
- Idempotent re-pull: files with `<!-- tk:pull-managed-* -->` markers
  merge only inside the block; content-hash conflict detection on
  full-file replacements; `--force` / `--preserve` flags for
  opt-in overwrite or conflict-sidecar behaviour.
- Credential scrubber on git URLs: strips `user:pass@` and `ghp_…@`
  userinfo before any subprocess or log statement, with a stderr
  warning when credentials were present.
- Tier-change semantics: narrowing `--tier` moves previously-present
  tk-owned files to `<output>/.tk-pull-archive/<timestamp>/` by
  default; `--no-archive` hard-deletes.

### Fixed

- `path_rewriter.py`: `re.sub` backslash-escape parsing of Windows paths
  (`C:\Users\…` → `KeyError: '\\U'`) now bypassed via lambda replacement.
- `test_env` assertions made platform-aware (PowerShell vs POSIX shell
  output in the managed env block).
- `test_importer` regex now accepts both `"Unsafe path"` (POSIX) and
  `"Path escapes target directory"` (Windows) for the malicious-tar test.

### Changed

- Version bumped `0.2.0` → `0.3.0`.
- 132 baseline tests preserved, 72 new tests added (204 total, all green
  on Ubuntu/macOS/Windows × Python 3.10/3.11/3.12/3.13).

## [0.2.0] — 2026-03-24

### Added

- Memory directory scanning and export (`~/.claude/projects/*/memory/`).
- Hooks and permissions surfaced in `scan` output.
- PowerShell env var scanning and PowerShell env-set syntax on Windows.
- Functional CLI tests and integration tests for `import --compare` and
  `sync push`.

### Fixed

- `import --compare` crash: new `extract_to()` helper on the importer.
- Unsafe tar extraction replaced with a safe extractor that blocks absolute
  paths, `..` traversal, and symlinks.
- Extra path-traversal hardening on tar entries.
- `sync copy --from` crash when `--to` was omitted.
- Secret values masked in `env show` output.
- Frontmatter parser edge cases.
- Rich `no_color` honoured end-to-end.
- Anonymized exports produce deterministic output.
- Copilot MCP inputs and multi-project merge across all converters.
- Gemini converter skill path and settings location.
- Tool-map updates and context-aware rewriting in all converters.
- Windows compatibility: tmpdir on same filesystem, `gpg2` fallback, POSIX
  paths, timestamp handling, UTF-8 encoding, escape round-trip.

### Changed

- Bumped version to 0.2.0.
- 132 tests passing (up from 108 in v0.1.0).

## [0.1.0] — 2026-03-15

### Added

- Initial release.
- Core CLI: `scan`, `export`, `import`, `convert`, `compare`, `sync`, `env`,
  `prereqs`.
- Interactive menu mode (`questionary`).
- Core modules: scanner, exporter, importer, sync, crypto.
- Converters: Gemini CLI, GitHub Copilot, Windsurf.
- Compare & merge feature with per-section interactive diffing.
- 108 tests passing.

### Security

- QA review addressed 5 critical issues: path traversal, secret leakage,
  sync CLI correctness, manifest alignment.

[Unreleased]: https://github.com/joogy06/Agent-Foundry-Converter/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/joogy06/Agent-Foundry-Converter/releases/tag/v0.3.0
[0.2.0]: https://github.com/joogy06/Agent-Foundry-Converter/releases/tag/v0.2.0
[0.1.0]: https://github.com/joogy06/Agent-Foundry-Converter/releases/tag/v0.1.0
