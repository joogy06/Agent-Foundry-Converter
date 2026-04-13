# Transfer Kit

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-132%20passing-brightgreen.svg)](tests/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)

Migrate Claude Code configuration to new machines and convert it to other IDEs.

## Project Status

**Alpha — v0.2.0 shipped, v0.3.0 in design.**

Transfer Kit v0.2.0 is functional and has 132 passing tests. It can scan,
export, import, convert, compare, and sync Claude Code configurations across
machines and to GitHub Copilot, Gemini CLI, and Windsurf.

See [`CHANGELOG.md`](CHANGELOG.md) for the roadmap.

Interfaces may change before v1.0.

## Features

- **Scan** your Claude Code environment and display a summary of skills, plugins, MCP servers, projects, env vars, plans, teams, and keybindings.
- **Export** selected config items to a portable `.tar.gz` bundle with optional secret redaction.
- **Import** a bundle into a Claude Code installation with conflict resolution and optional post-import diff.
- **Convert** Claude Code config to GitHub Copilot, Gemini CLI, or Windsurf format, including tool-name rewriting.
- **Compare** two config directories side-by-side and interactively resolve differences.
- **Sync** config between machines via a git repository or direct file copy.
- **Manage environment variables** across shell profiles with a managed block approach.
- **Check prerequisites** and display install hints for your OS and package manager.
- **Interactive mode** with menu-driven workflows when no subcommand is given.
- Cross-platform support for Linux, macOS, and Windows.

## Installation

Requires Python 3.10 or later.

```bash
git clone https://github.com/joogy06/Agent-Foundry-Converter.git
cd Agent-Foundry-Converter
pip install .
```

The `transfer-kit` command will be available on your PATH.

## Quick Start

```bash
# See what Claude Code config you have
transfer-kit scan

# Export everything to a bundle
transfer-kit export -o backup.tar.gz

# Import a bundle on another machine
transfer-kit import --from backup.tar.gz

# Convert your config for Gemini CLI
transfer-kit convert --target gemini -o ~/project/
```

## Commands Reference

### scan

Discover and display a summary of the current Claude Code environment.

```bash
transfer-kit scan
```

No additional flags. Outputs a table of categories, counts, and details.

### export

Bundle the Claude Code environment into a portable archive.

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output` | `transfer_kit_bundle.tar.gz` | Output file path |
| `--items` | `all` | Comma-separated categories: `skills`, `plugins`, `settings`, `projects`, `mcp`, `env`, `plans`, `teams`, `keybindings` |
| `--include-secrets` | off | Include secret values without redaction |

```bash
# Export only skills and MCP servers
transfer-kit export --items skills,mcp -o my_config.tar.gz

# Export everything including secrets
transfer-kit export --include-secrets -o full_backup.tar.gz
```

### import

Restore a transfer-kit bundle into the Claude Code environment.

| Flag | Default | Description |
|------|---------|-------------|
| `--from` | (required) | Path to the bundle file |
| `--merge` | -- | Merge: skip existing files |
| `--overwrite` | -- | Overwrite existing files |
| `--skip` | default | Skip existing files |
| `--compare` | off | After import, compare and interactively resolve differences |

```bash
# Import with default skip-on-conflict behavior
transfer-kit import --from backup.tar.gz

# Import and overwrite conflicts, then compare
transfer-kit import --from backup.tar.gz --overwrite --compare
```

### convert

Convert Claude Code config to another IDE's format.

| Flag | Default | Description |
|------|---------|-------------|
| `--target` | (required) | Target IDE: `copilot`, `gemini`, or `windsurf` |
| `-o`, `--output` | `transfer_kit_<target>_output` | Output directory |
| `--items` | `all` | Comma-separated categories to convert |

```bash
# Convert everything for GitHub Copilot
transfer-kit convert --target copilot -o ./copilot_config

# Convert only skills and env vars for Windsurf
transfer-kit convert --target windsurf --items skills,env
```

### compare

Compare two config directories and interactively resolve differences.

| Flag | Default | Description |
|------|---------|-------------|
| `-s`, `--source` | (required) | Source (incoming) directory |
| `-t`, `--target` | (required) | Target (existing) directory |

```bash
transfer-kit compare --source ./incoming_config --target ~/.claude
```

### sync

Synchronize Claude Code config with a git repository or copy between locations.

#### sync init

Initialize a sync repository.

```bash
transfer-kit sync init /path/to/repo
transfer-kit sync init /path/to/repo --remote git@github.com:user/dotfiles.git
```

#### sync push

Export local config and push it to the sync repository.

```bash
transfer-kit sync push /path/to/repo
```

#### sync pull

Pull config from the sync repository.

```bash
transfer-kit sync pull /path/to/repo
```

#### sync copy

Copy config between locations via file copy or rsync.

| Flag | Default | Description |
|------|---------|-------------|
| `--to` | -- | Destination path |
| `--from` | -- | Source path |
| `--execute` | off | Execute the copy immediately (dry-run by default) |
| `--on-conflict` | `skip` | Conflict strategy: `skip`, `overwrite`, or `fail` |

```bash
# Preview what would be copied
transfer-kit sync copy --to user@host:/path/to/config

# Execute the copy
transfer-kit sync copy --to /mnt/backup/claude --execute --on-conflict overwrite
```

### env

Manage environment variables in shell profiles using a managed block.

#### env show

List all managed environment variables across detected shell profiles.

```bash
transfer-kit env show
```

#### env set

Add or update a managed environment variable.

```bash
transfer-kit env set GEMINI_API_KEY=sk-abc123
```

#### env remove

Remove a managed environment variable.

```bash
transfer-kit env remove GEMINI_API_KEY
```

#### env apply

Write all managed variables to the current shell profile.

```bash
transfer-kit env apply
```

### prereqs

Check for required external tools and display install hints for your OS.

```bash
transfer-kit prereqs
```

### Interactive Mode

Run `transfer-kit` with no subcommand to launch a menu-driven interface:

```bash
transfer-kit
```

The interactive mode presents a questionary-based menu for scanning, exporting, importing, converting, syncing, managing env vars, and checking prerequisites.

## Global Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--verbose` | `-v` | Enable verbose (debug-level) output |
| `--quiet` | `-q` | Suppress non-essential output |
| `--yes` | `-y` | Auto-confirm all prompts (non-interactive) |
| `--dry-run` | -- | Show what would happen without making changes |
| `--no-color` | -- | Disable colored output |
| `--version` | -- | Show version and exit |

## Supported Targets

Conversion mappings from Claude Code tool references to target IDE equivalents:

| Claude Code | Gemini CLI | GitHub Copilot | Windsurf |
|-------------|------------|----------------|----------|
| `Read` | `read_file` | native | native |
| `Edit` | `edit_file` | native | native |
| `Write` | `write_file` | native | native |
| `Bash` | `run_shell_command` | `#terminal` | terminal |
| `Grep` | `search_files` | `#codebase` | native |
| `Glob` | `search_files` | `#codebase` | native |
| `Agent` | rewritten as instruction paragraph | rewritten as instruction paragraph | rewritten as instruction paragraph |

Output locations by target:

| Item | Copilot | Gemini CLI | Windsurf |
|------|---------|------------|----------|
| Skills | `.github/instructions/<name>.instructions.md` | `GEMINI.md` sections + skill files | `.windsurf/rules/<name>.md` |
| Project config | `.github/copilot-instructions.md` | `GEMINI.md` | `.windsurf/rules/project.md` |
| MCP servers | `.vscode/mcp.json` | `~/.gemini/settings.json` | `~/.codeium/windsurf/mcp_config.json` |
| Env vars | `.env` file | mapped equivalents | `.env` + documentation |

## Project Structure

```
transfer_kit/
    __init__.py          Package metadata and version
    __main__.py          Entry point for python -m transfer_kit
    cli.py               Click CLI group and all subcommands
    interactive.py       Questionary-based interactive menus
    models.py            Dataclasses for config items (Skill, Plugin, McpServer, etc.)
    prereqs.py           Prerequisite checker with install hints
    env.py               Shell profile environment variable management
    platform_utils.py    Cross-platform path resolution and OS detection
    core/
        scanner.py       Discovers Claude Code config from ~/.claude/
        exporter.py      Bundles selected items into a .tar.gz archive
        importer.py      Restores a bundle to a Claude Code installation
        comparator.py    Side-by-side config directory comparison
        crypto.py        Fernet/GPG encryption for synced secrets
        sync.py          Git repo and file copy sync logic
    converters/
        base.py          Abstract converter interface and tool mapping table
        copilot.py       GitHub Copilot converter
        gemini.py        Gemini CLI converter
        windsurf.py      Windsurf converter
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests run on Linux, macOS, and Windows via GitHub Actions (see
`.github/workflows/ci.yml`) across Python 3.10–3.13.

## Contributing

Bug reports, feature requests, and pull requests welcome. Please check
existing issues first and keep changes focused. Tests must stay green.

## License

MIT — see [`LICENSE`](LICENSE).
