# Transfer Kit — Architecture Overview

> Python CLI tool for migrating Claude Code configuration between machines and converting it to other IDE formats.

**Version:** 0.3.0 (released 2026-04-15 — agent-foundry pull feature shipped; Smart Export parallel track still deferred)
**Entry point:** `transfer-kit` CLI / `python -m transfer_kit`
**Python:** 3.10+
**Tests:** 204 (pytest) — 132 baseline + 72 new (71 for pull flow + 1 Windows-path regression test)
**CI:** `.github/workflows/ci.yml` — matrix: ubuntu/windows/macos x Python 3.10–3.13
**Repo:** https://github.com/joogy06/Agent-Foundry-Converter (public, MIT)

---

## Component Map

```
transfer_kit/
├── cli.py                  ← Click CLI group: scan, export, import, convert, pull, compare, sync, env, prereqs
├── interactive.py          ← Questionary menu-driven mode (no subcommand)
├── models.py               ← Dataclasses: Skill, Plugin, McpServer, EnvVar, Plan, Team, MetaFile, etc.
├── env.py                  ← Shell profile env var management (managed block)
├── platform_utils.py       ← OS detection, shell type, Claude home/project paths
├── prereqs.py              ← Prerequisite checker with per-OS install hints
├── core/
│   ├── scanner.py          ← Discovers ~/.claude/ config (parameterised via root=)
│   ├── exporter.py         ← Bundles selected items → .tar.gz with manifest
│   ├── importer.py         ← Restores bundle → ~/.claude/ with conflict resolution
│   ├── comparator.py       ← Side-by-side directory diff + interactive merge
│   ├── crypto.py           ← Fernet + GPG encryption for sync secrets
│   ├── sync.py             ← Git repo push/pull + file copy sync
│   ├── foundry_loader.py   ← NEW: load joogy06/agent-foundry repo → ClaudeEnvironment (pull flow)
│   ├── path_rewriter.py    ← NEW: ~/.claude/ path rewriting per target + env-var shim injector
│   ├── url_sanitizer.py    ← NEW: strip credentials from git URLs
│   ├── compat.py           ← NEW: load compat_matrix.yaml + filter env per target/tier
│   ├── xref_resolver.py    ← NEW: report dangling cross-refs post-filter
│   └── pull.py             ← NEW: orchestrate sanitise → clone → load → compat → xref → convert → write
├── converters/
│   ├── base.py             ← ABC + tool map + convert_agents/meta/deps hooks (default no-op)
│   ├── copilot.py          ← GitHub Copilot VS Code (per-skill applyTo supported since v0.3.0)
│   ├── copilot_cli.py      ← NEW: GitHub Copilot CLI (AGENTS.md + .github/agents/ + G2 shim)
│   ├── gemini.py           ← Gemini CLI (resource subdir passthrough since v0.3.0)
│   └── windsurf.py         ← Windsurf (unchanged)
├── data/
│   ├── compat_matrix.yaml  ← NEW: per-artifact × per-target portability declarations
│   └── gates_g2_shim.py    ← NEW: host-portable G2 schema validator shipped to non-Claude targets
└── templates/
    └── host_agents/
        ├── copilot.md      ← NEW: host-agent onboarding fragment for Copilot (VS Code)
        ├── copilot_cli.md  ← NEW: host-agent onboarding fragment for Copilot CLI
        └── gemini.md       ← NEW: host-agent onboarding fragment for Gemini CLI
```

## Data Flow

```
Forward (export / convert):
~/.claude/ ──scanner──→ ScanResult ──exporter──→ .tar.gz bundle
                                          │
                                    importer ←── .tar.gz bundle
                                          │
                                    converters ──→ Copilot / Gemini / Windsurf output

Inverse (pull, v0.3.0):
git-url-or-path ──url_sanitizer──→ clone──→ foundry_loader──→ ClaudeEnvironment
       → compat (matrix+tier filter) → xref_resolver → converter → path_rewriter → output dir
       with idempotent managed-block write, .tk-pull-archive on tier narrow, DEPENDENCIES.md render.
```

## Integration Edges

| Boundary | Details |
|----------|---------|
| **Claude Code home** | `~/.claude/` — skills, plugins, settings, projects, memory, plans, teams, keybindings |
| **Shell profiles** | `~/.bashrc`, `~/.zshrc`, PowerShell `$PROFILE` — env var managed blocks |
| **Git** | GitPython for sync push/pull to remote repos |
| **GPG** | Optional encryption via gpg/gpg2 binary |
| **Target IDEs** | Copilot (`.github/`), Gemini (`.gemini/`, `GEMINI.md`), Windsurf (`.windsurf/`), Cursor (`.cursor/rules/`) |
| **GitHub Actions** | `.github/workflows/ci.yml` — test matrix across 3 OS x 4 Python versions |

## External Dependencies

| Package | Purpose |
|---------|---------|
| click | CLI framework |
| questionary | Interactive prompts |
| rich | Formatted terminal output |
| gitpython | Git sync operations |
| pyyaml | YAML parsing |
| cryptography | Fernet encryption |

## Key Design Decisions

- **Tool name rewriting:** Converters contextually rewrite Claude Code tool references (Read, Edit, Bash, etc.) to target IDE equivalents. The `Agent` tool is rewritten to an instruction paragraph rather than a tool call.
- **Safe extraction:** Tar extraction validates paths (no absolute, no `..`, no symlinks) to prevent path traversal.
- **Secret masking:** Export redacts secrets by default; `env show` masks values.
- **Cross-platform:** Shell type detection, PowerShell env syntax, Windows path handling, gpg2 fallback.
- **Managed block:** Env vars written to shell profiles inside a delimited block for clean add/remove.
