"""transfer_kit/interactive.py — Questionary-based interactive menus."""

from __future__ import annotations

import click
from rich.console import Console

console = Console()

MENU_CHOICES = [
    "Scan environment",
    "Export bundle",
    "Import bundle",
    "Convert to another IDE",
    "Sync config",
    "Environment variables",
    "Check prerequisites",
    "Compare — Compare two config directories",
    "Exit",
]

EXPORT_ITEM_CHOICES = [
    "all",
    "skills",
    "plugins",
    "settings",
    "projects",
    "mcp",
    "env_vars",
    "plans",
    "teams",
    "keybindings",
]

CONVERT_TARGET_CHOICES = [
    "copilot",
    "gemini",
    "windsurf",
]


def run_interactive(ctx: click.Context) -> None:
    """Launch the interactive menu loop."""
    import questionary

    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=MENU_CHOICES,
        ).ask()

        if choice is None or choice == "Exit":
            break
        elif choice == "Scan environment":
            ctx.invoke(_get_scan_command())
        elif choice == "Export bundle":
            _interactive_export(ctx)
        elif choice == "Import bundle":
            _interactive_import(ctx)
        elif choice == "Convert to another IDE":
            _interactive_convert(ctx)
        elif choice == "Sync config":
            _interactive_sync(ctx)
        elif choice == "Environment variables":
            _interactive_env(ctx)
        elif choice == "Check prerequisites":
            ctx.invoke(_get_prereqs_command())
        elif choice == "Compare — Compare two config directories":
            _interactive_compare(ctx)


def _get_scan_command():
    """Lazy import to avoid circular dependency."""
    from transfer_kit.cli import scan
    return scan


def _get_prereqs_command():
    """Lazy import to avoid circular dependency."""
    from transfer_kit.cli import prereqs
    return prereqs


def _interactive_export(ctx: click.Context) -> None:
    """Prompt the user for export options and run the export."""
    import questionary
    from transfer_kit.cli import export_cmd

    items = questionary.checkbox(
        "Select items to export:",
        choices=EXPORT_ITEM_CHOICES,
        default=["all"],
    ).ask()

    if items is None:
        return

    output = questionary.text(
        "Output file path:",
        default="transfer_kit_bundle.tar.gz",
    ).ask()

    if output is None:
        return

    include_secrets = questionary.confirm(
        "Include secrets (unredacted)?",
        default=False,
    ).ask()

    if include_secrets is None:
        return

    items_str = ",".join(items) if items and "all" not in items else "all"
    ctx.invoke(export_cmd, output=output, items=items_str, include_secrets=include_secrets)


def _interactive_import(ctx: click.Context) -> None:
    """Prompt the user for import options and run the import."""
    import questionary
    from transfer_kit.cli import import_cmd

    from_path = questionary.path(
        "Path to bundle file:",
    ).ask()

    if from_path is None:
        return

    conflict = questionary.select(
        "On conflict:",
        choices=["skip", "overwrite"],
    ).ask()

    if conflict is None:
        return

    ctx.invoke(import_cmd, from_path=from_path, conflict=conflict)


def _interactive_convert(ctx: click.Context) -> None:
    """Prompt the user for conversion options and run the convert."""
    import questionary
    from transfer_kit.cli import convert

    target = questionary.select(
        "Target IDE:",
        choices=CONVERT_TARGET_CHOICES,
    ).ask()

    if target is None:
        return

    output = questionary.text(
        "Output directory:",
        default=f"transfer_kit_{target}_output",
    ).ask()

    if output is None:
        return

    ctx.invoke(convert, target=target, output=output, items="all")


def _interactive_sync(ctx: click.Context) -> None:
    """Prompt the user for sync action."""
    import questionary

    action = questionary.select(
        "Sync action:",
        choices=["init", "push", "pull", "cancel"],
    ).ask()

    if action is None or action == "cancel":
        return

    path = questionary.path("Repository path:").ask()
    if path is None:
        return

    if action == "init":
        from transfer_kit.cli import sync_init
        remote = questionary.text("Remote URL (leave empty for none):", default="").ask()
        ctx.invoke(sync_init, path=path, remote=remote or None)
    elif action == "push":
        from transfer_kit.cli import sync_push
        ctx.invoke(sync_push, path=path)
    elif action == "pull":
        from transfer_kit.cli import sync_pull
        ctx.invoke(sync_pull, path=path)


def _interactive_env(ctx: click.Context) -> None:
    """Prompt the user for environment variable management."""
    import questionary
    from transfer_kit.cli import env_show, env_set, env_remove, env_apply

    action = questionary.select(
        "Environment action:",
        choices=["show", "set", "remove", "apply", "cancel"],
    ).ask()

    if action is None or action == "cancel":
        return

    if action == "show":
        ctx.invoke(env_show)
    elif action == "set":
        key_value = questionary.text("KEY=VALUE:").ask()
        if key_value:
            ctx.invoke(env_set, key_value=key_value)
    elif action == "remove":
        key = questionary.text("Variable name to remove:").ask()
        if key:
            ctx.invoke(env_remove, key=key)
    elif action == "apply":
        ctx.invoke(env_apply)


def _interactive_compare(ctx: click.Context) -> None:
    """Prompt the user for compare options and run the compare."""
    import questionary

    source = questionary.path("Source (incoming) directory:").ask()
    target = questionary.path("Target (existing) directory:").ask()
    if not source or not target:
        return
    from transfer_kit.cli import compare
    ctx.invoke(compare, source=source, target=target)
