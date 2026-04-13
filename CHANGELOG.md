# Changelog

All notable changes to Transfer Kit are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — v0.3.0 Smart Export (designed, not yet shipped)

Full design in `docs/superpowers/specs/2026-03-30-smart-export-design.md`.

### Planned

- Two-layer export pipeline: deterministic regex rewriting (Layer 1) plus
  AI-assisted semantic translation via `claude -p` / `codex exec` (Layer 2).
- Portability classification (portable / partial / claude-only) applied before
  conversion so incompatible items are filtered or flagged.
- Environment awareness: capability prober, analyzer, `self-test.sh`, and a
  `failure-memory.json` for self-healing deploys.
- `Agent` dataclass, `_scan_agents()`, and agent-aware converters.
- `Cursor` converter (fifth target IDE).
- `REGISTRY.md` master ecosystem map with cascade diagram and capability
  requirements.
- `transfer-flow.md` per-deployment manifest.
- `smart-export` CLI subcommand layering on existing `convert`.

### Fixed (P0 critical bugs queued for v0.3.0)

- `pyproject.toml` version mismatch (was 0.1.0, should be 0.2.0).
- `env.py` shell-escape gap (`!` and newlines not escaped).
- `crypto.py` GPG encryption missing `--batch` and recipient validation.
- `sync.py` using `repo.index.add("*")` instead of explicit file staging.
- `platform_utils.py` Windsurf Windows path.
- `cli.py` dead `Panel` import.

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

[Unreleased]: https://github.com/joogy06/Agent-Foundry-Converter/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/joogy06/Agent-Foundry-Converter/releases/tag/v0.2.0
[0.1.0]: https://github.com/joogy06/Agent-Foundry-Converter/releases/tag/v0.1.0
