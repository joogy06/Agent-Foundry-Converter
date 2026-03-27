# Project History

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
- Exported 78 skills from Claude Code to VS Code Copilot format (`output_copilot/.github/instructions/`)
- Exported 78 skills from Claude Code to Gemini CLI format (`output_gemini/.gemini/skills/`)
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
