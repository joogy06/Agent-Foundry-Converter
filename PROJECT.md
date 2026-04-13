# Transfer Kit — Architecture Overview

> Python CLI tool for migrating Claude Code configuration between machines and converting it to other IDE formats.

**Version:** 0.2.0
**Entry point:** `transfer-kit` CLI / `python -m transfer_kit`
**Python:** 3.10+
**Tests:** 132 (pytest)
**CI:** `.github/workflows/ci.yml` — matrix: ubuntu/windows/macos x Python 3.10–3.13

---

## Component Map

```
transfer_kit/
├── cli.py                  ← Click CLI group: scan, export, import, convert, compare, sync, env, prereqs
├── interactive.py          ← Questionary menu-driven mode (no subcommand)
├── models.py               ← Dataclasses: Skill, Plugin, McpServer, EnvVar, Plan, Team, etc.
├── env.py                  ← Shell profile env var management (managed block)
├── platform_utils.py       ← OS detection, shell type, Claude home/project paths
├── prereqs.py              ← Prerequisite checker with per-OS install hints
├── core/
│   ├── scanner.py          ← Discovers ~/.claude/ config (skills, plugins, MCP, projects, memory, hooks, permissions)
│   ├── exporter.py         ← Bundles selected items → .tar.gz with manifest
│   ├── importer.py         ← Restores bundle → ~/.claude/ with conflict resolution
│   ├── comparator.py       ← Side-by-side directory diff + interactive merge
│   ├── crypto.py           ← Fernet + GPG encryption for sync secrets
│   └── sync.py             ← Git repo push/pull + file copy sync
└── converters/
    ├── base.py             ← ABC + tool name mapping table (Claude→target rewriting)
    ├── copilot.py          ← GitHub Copilot: .github/instructions/, mcp.json
    ├── gemini.py           ← Gemini CLI: GEMINI.md, .gemini/skills/, settings.json
    └── windsurf.py         ← Windsurf: .windsurf/rules/, mcp_config.json
```

## Data Flow

```
~/.claude/ ──scanner──→ ScanResult ──exporter──→ .tar.gz bundle
                                          │
                                    importer ←── .tar.gz bundle
                                          │
                                    converters ──→ Copilot / Gemini / Windsurf output

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
