# File Index

## Source (`transfer_kit/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package init, version |
| `__main__.py` | `python -m` entry point |
| `cli.py` | Click CLI subcommands |
| `interactive.py` | Questionary interactive menus |
| `models.py` | Dataclasses (Skill, Plugin, McpServer, etc.) |
| `platform_utils.py` | OS detection, path resolution |
| `prereqs.py` | Prerequisite checker |
| `env.py` | Shell profile env var management |
| `core/__init__.py` | Core subpackage init |
| `core/scanner.py` | Discovers Claude Code config |
| `core/exporter.py` | Bundles config to tar.gz |
| `core/importer.py` | Restores from bundle |
| `core/sync.py` | Git repo + file copy sync |
| `core/crypto.py` | Fernet + GPG encryption |
| `core/comparator.py` | Config diff + merge engine |
| `converters/__init__.py` | Converters subpackage init |
| `converters/base.py` | ABC + tool name mapping |
| `converters/gemini.py` | Gemini CLI converter |
| `converters/copilot.py` | GitHub Copilot converter |
| `converters/windsurf.py` | Windsurf converter |

## Tests (`tests/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Test package init |
| `conftest.py` | Shared fixtures and test configuration |
| `test_cli.py` | Tests for Click CLI subcommands |
| `test_comparator.py` | Tests for config diff + merge engine |
| `test_converter_copilot.py` | Tests for GitHub Copilot converter |
| `test_converter_gemini.py` | Tests for Gemini CLI converter |
| `test_converters_base.py` | Tests for converter ABC + base logic |
| `test_converter_windsurf.py` | Tests for Windsurf converter |
| `test_crypto.py` | Tests for Fernet + GPG encryption |
| `test_env.py` | Tests for shell env var management |
| `test_exporter.py` | Tests for bundle export |
| `test_importer.py` | Tests for bundle import/restore |
| `test_integration.py` | End-to-end integration tests |
| `test_interactive.py` | Tests for interactive menus |
| `test_models.py` | Tests for dataclass models |
| `test_platform_utils.py` | Tests for OS detection + paths |
| `test_prereqs.py` | Tests for prerequisite checker |
| `test_scanner.py` | Tests for config discovery |
| `test_sync.py` | Tests for git repo + file sync |

## Project Root

| File | Purpose |
|------|---------|
| `README.md` | Installation, usage, commands reference |
| `history.md` | Project timeline and milestones |
| `index.md` | This file — module/file index |
| `PROJECT.md` | Architecture overview, component map, data flow |
| `CHANGELOG.md` | Keep-a-Changelog format release notes |
| `LICENSE` | MIT license |
| `pyproject.toml` | Package config, dependencies, entry point |
| `.gitignore` | Git ignore rules |

## CI/CD (`.github/`)

| File | Purpose |
|------|---------|
| `workflows/ci.yml` | Pytest matrix: ubuntu/windows/macos × Python 3.10–3.13 |

## Test Fixtures (`tests/fixtures/`)

| File | Purpose |
|------|---------|
| `claude_home/settings.json` | Fixture: global settings |
| `claude_home/settings.local.json` | Fixture: local settings |
| `claude_home/plugins/installed_plugins.json` | Fixture: installed plugins |
| `claude_home/skills/test-skill/test-skill.md` | Fixture: custom skill |
| `claude_home/projects/-test-project/CLAUDE.md` | Fixture: project instructions |
| `claude_home/projects/-test-project/settings.json` | Fixture: project settings |
| `claude_home/projects/-test-project/memory/MEMORY.md` | Fixture: project memory index |
| `claude_home/projects/-test-project/memory/project_notes.md` | Fixture: project memory notes |
| `claude_home/plans/test-plan.md` | Fixture: saved plan |
| `claude_home/teams/test-team/config.json` | Fixture: team config |

