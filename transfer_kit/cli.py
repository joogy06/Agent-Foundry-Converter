"""transfer_kit/cli.py — Click CLI for Transfer Kit."""

from __future__ import annotations

from pathlib import Path

import click
import questionary
from rich.console import Console
from rich.table import Table

import transfer_kit


console = Console()


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output.")
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm prompts.")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes.")
@click.option("--no-color", is_flag=True, help="Disable coloured output.")
@click.version_option(version=transfer_kit.__version__, prog_name="transfer-kit")
@click.pass_context
def main(ctx: click.Context, verbose: bool, quiet: bool, yes: bool, dry_run: bool, no_color: bool) -> None:
    """Transfer Kit — migrate Claude Code config to new machines and other IDEs."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["yes"] = yes
    ctx.obj["dry_run"] = dry_run
    ctx.obj["no_color"] = no_color

    if no_color:
        console.no_color = True

    if ctx.invoked_subcommand is None:
        # Launch interactive mode when no subcommand is given.
        from transfer_kit.interactive import run_interactive

        run_interactive(ctx)


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


@main.command()
@click.pass_context
def scan(ctx: click.Context) -> None:
    """Scan the current Claude Code environment and display a summary."""
    from transfer_kit.core.scanner import Scanner

    scanner = Scanner()
    env = scanner.scan()

    table = Table(title="Claude Code Environment Scan")
    table.add_column("Category", style="bold cyan")
    table.add_column("Count", justify="right")
    table.add_column("Details")

    categories = [
        ("Skills", env.skills, lambda items: ", ".join(s.name for s in items)),
        ("Plugins", env.plugins, lambda items: ", ".join(p.name for p in items)),
        ("MCP Servers", env.mcp_servers, lambda items: ", ".join(s.name for s in items)),
        ("Projects", env.projects, lambda items: ", ".join(p.project_path for p in items)),
        ("Env Vars", env.env_vars, lambda items: ", ".join(v.name for v in items)),
        ("Plans", env.plans, lambda items: ", ".join(p.name for p in items)),
        ("Teams", env.teams, lambda items: ", ".join(t.name for t in items)),
        ("Keybindings", [env.keybindings] if env.keybindings else [], lambda items: "custom" if items else "default"),
    ]

    for name, items, detail_fn in categories:
        details = detail_fn(items) if items else "-"
        table.add_row(name, str(len(items)), details)

    console.print(table)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@main.command(name="export")
@click.option("-o", "--output", default="transfer_kit_bundle.tar.gz", help="Output file path.")
@click.option("--items", default="all", help="Comma-separated list of item categories, or 'all'.")
@click.option("--include-secrets", is_flag=True, help="Include secret values without redaction.")
@click.pass_context
def export_cmd(ctx: click.Context, output: str, items: str, include_secrets: bool) -> None:
    """Export the Claude Code environment to a portable bundle."""
    from transfer_kit.core.scanner import Scanner
    from transfer_kit.core.exporter import Exporter

    scanner = Scanner()
    env = scanner.scan()

    item_list = None if items == "all" else [i.strip() for i in items.split(",")]

    exporter = Exporter(env, include_secrets=include_secrets)

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would export to {output}[/dim]")
        return

    path = exporter.export(output, items=item_list)
    console.print(f"[green]Exported to {path}[/green]")


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


@main.command(name="import")
@click.option("--from", "from_path", required=True, help="Path to the bundle to import.")
@click.option("--merge", "conflict", flag_value="skip", help="Merge: skip existing files.")
@click.option("--overwrite", "conflict", flag_value="overwrite", help="Overwrite existing files.")
@click.option("--skip", "conflict", flag_value="skip", default=True, help="Skip existing files (default).")
@click.option("--compare", "run_compare", is_flag=True, default=False,
              help="After restoring, compare the extracted bundle with the target and interactively resolve differences.")
@click.pass_context
def import_cmd(ctx: click.Context, from_path: str, conflict: str, run_compare: bool) -> None:
    """Import a transfer-kit bundle into the Claude Code environment."""
    from transfer_kit.core.importer import Importer
    from transfer_kit.platform_utils import get_claude_home

    importer = Importer(from_path)

    if ctx.obj.get("dry_run"):
        manifest = importer.read_manifest()
        console.print(f"[dim]Dry run: would import {manifest.get('items', [])} from {from_path}[/dim]")
        return

    target = get_claude_home()
    importer.restore(target, on_conflict=conflict)
    console.print(f"[green]Imported bundle from {from_path}[/green]")

    if run_compare:
        import tempfile
        from transfer_kit.core.comparator import ConfigComparator

        with tempfile.TemporaryDirectory(prefix="transfer_kit_compare_") as compare_dir:
            importer.extract_to(compare_dir)
            comp = ConfigComparator(Path(compare_dir), Path(target))
            diffs = comp.compare()

            if not diffs:
                console.print("[green]No differences found after import.[/]")
                return

            console.print(f"\n[cyan]Found {len(diffs)} difference(s) after import:[/]\n")

            selections = {}
            for i, diff in enumerate(diffs):
                _display_diff(diff)

                if not ctx.obj.get("yes"):
                    if diff.item_type == "removed":
                        console.print("  [dim](informational — no action required)[/]\n")
                        continue

                    action_label = "Add" if diff.item_type == "new" else "Use incoming"
                    choice = questionary.select(
                        "Action:",
                        choices=[
                            questionary.Choice("Keep current", value="keep"),
                            questionary.Choice(action_label, value="incoming"),
                            questionary.Choice("Skip", value="skip"),
                        ] if diff.item_type != "new" else [
                            questionary.Choice("Add", value="incoming"),
                            questionary.Choice("Skip", value="skip"),
                        ],
                    ).ask()
                    selections[i] = choice or "skip"
                else:
                    selections[i] = "incoming"

            written = comp.apply_selections(diffs, selections)
            if written:
                console.print(f"\n[green]Updated {len(written)} file(s) after compare.[/]")
            else:
                console.print("\n[yellow]No additional changes applied.[/]")


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def _display_diff(diff):
    """Display a single DiffItem as a side-by-side rich table."""
    from rich.table import Table
    from rich.panel import Panel

    title_style = {"new": "green", "modified": "yellow", "removed": "red"}
    label = diff.item_type.upper()
    title = f"[{title_style[diff.item_type]}]{label}[/]: {diff.path} :: {diff.section}"

    table = Table(show_header=True, title=title, show_lines=True, expand=True)
    table.add_column("Current", style="red", ratio=1)
    table.add_column("Incoming", style="green", ratio=1)

    current_text = diff.current or "(does not exist)"
    incoming_text = diff.incoming or "(not in incoming)"

    # Truncate long content for display
    max_lines = 20
    current_lines = current_text.splitlines()
    incoming_lines = incoming_text.splitlines()
    if len(current_lines) > max_lines:
        current_text = "\n".join(current_lines[:max_lines]) + f"\n... ({len(current_lines) - max_lines} more lines)"
    if len(incoming_lines) > max_lines:
        incoming_text = "\n".join(incoming_lines[:max_lines]) + f"\n... ({len(incoming_lines) - max_lines} more lines)"

    table.add_row(current_text, incoming_text)
    console.print(table)


@main.command()
@click.option("--source", "-s", type=click.Path(exists=True), required=True, help="Source (incoming) directory")
@click.option("--target", "-t", type=click.Path(exists=True), required=True, help="Target (existing) directory")
@click.pass_context
def compare(ctx, source, target):
    """Compare two config directories and show differences."""
    from transfer_kit.core.comparator import ConfigComparator

    comp = ConfigComparator(Path(source), Path(target))
    diffs = comp.compare()

    if not diffs:
        console.print("[green]No differences found.[/]")
        return

    console.print(f"[cyan]Found {len(diffs)} difference(s):[/]\n")

    selections = {}
    for i, diff in enumerate(diffs):
        _display_diff(diff)

        if not ctx.obj.get("yes"):
            if diff.item_type == "removed":
                console.print("  [dim](informational — no action required)[/]\n")
                continue

            action_label = "Add" if diff.item_type == "new" else "Use incoming"
            choice = questionary.select(
                "Action:",
                choices=[
                    questionary.Choice("Keep current", value="keep"),
                    questionary.Choice(action_label, value="incoming"),
                    questionary.Choice("Skip", value="skip"),
                ] if diff.item_type != "new" else [
                    questionary.Choice("Add", value="incoming"),
                    questionary.Choice("Skip", value="skip"),
                ],
            ).ask()
            selections[i] = choice or "skip"
        else:
            selections[i] = "incoming"

    if ctx.obj.get("dry_run"):
        console.print("[yellow]Dry run — no files written.[/]")
        return

    written = comp.apply_selections(diffs, selections)
    if written:
        console.print(f"\n[green]Updated {len(written)} file(s).[/]")
    else:
        console.print("\n[yellow]No changes applied.[/]")


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


@main.command()
@click.option("--target", required=True, type=click.Choice(["copilot", "gemini", "windsurf"]),
              help="Target IDE to convert to.")
@click.option("-o", "--output", default=None, help="Output directory.")
@click.option("--items", default="all", help="Comma-separated list of item categories, or 'all'.")
@click.pass_context
def convert(ctx: click.Context, target: str, output: str | None, items: str) -> None:
    """Convert Claude Code config to another IDE's format."""
    from transfer_kit.core.scanner import Scanner
    from transfer_kit.converters.copilot import CopilotConverter
    from transfer_kit.converters.gemini import GeminiConverter
    from transfer_kit.converters.windsurf import WindsurfConverter

    converter_map = {
        "copilot": CopilotConverter,
        "gemini": GeminiConverter,
        "windsurf": WindsurfConverter,
    }

    scanner = Scanner()
    env = scanner.scan()

    converter_cls = converter_map[target]
    converter = converter_cls(env)
    results = converter.convert_all()

    output_dir = output or f"transfer_kit_{target}_output"

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would write {len(results)} files to {output_dir}[/dim]")
        return

    written = converter.write_output(output_dir, results)
    console.print(f"[green]Wrote {len(written)} files to {output_dir}[/green]")
    for p in written:
        console.print(f"  {p}")


# ---------------------------------------------------------------------------
# prereqs
# ---------------------------------------------------------------------------


@main.command()
@click.pass_context
def prereqs(ctx: click.Context) -> None:
    """Check for required external tools and display install hints."""
    from transfer_kit.prereqs import check_prereqs, INSTALL_HINTS
    from transfer_kit.platform_utils import detect_package_manager

    results = check_prereqs()
    pkg_mgr = detect_package_manager()

    table = Table(title="Prerequisites")
    table.add_column("Tool", style="bold")
    table.add_column("Found", justify="center")
    table.add_column("Version")
    table.add_column("Required For")
    table.add_column("Install Hint")

    for prereq in results:
        found_str = "[green]yes[/green]" if prereq.found else "[red]no[/red]"
        version = prereq.version or "-"
        hint = ""
        if not prereq.found and pkg_mgr:
            hints = INSTALL_HINTS.get(prereq.name, {})
            hint = hints.get(pkg_mgr, "")
        table.add_row(prereq.name, found_str, version, prereq.required_for, hint)

    console.print(table)


# ---------------------------------------------------------------------------
# env group
# ---------------------------------------------------------------------------


@main.group()
@click.pass_context
def env(ctx: click.Context) -> None:
    """Manage environment variables in shell profiles."""
    pass


@env.command(name="show")
@click.pass_context
def env_show(ctx: click.Context) -> None:
    """Show managed environment variables."""
    from transfer_kit.env import EnvManager
    from transfer_kit.platform_utils import get_shell_profile_paths

    profiles = get_shell_profile_paths()
    if not profiles:
        console.print("[yellow]No shell profiles found.[/yellow]")
        return

    for profile in profiles:
        mgr = EnvManager(profile)
        managed = mgr.get_managed_vars()
        if managed:
            console.print(f"\n[bold]{profile}[/bold]")
            for key, value in managed.items():
                console.print(f"  {key}={value}")
        else:
            console.print(f"\n[dim]{profile}: no managed variables[/dim]")


@env.command(name="set")
@click.argument("key_value")
@click.pass_context
def env_set(ctx: click.Context, key_value: str) -> None:
    """Set a managed environment variable (KEY=VALUE)."""
    from transfer_kit.env import EnvManager
    from transfer_kit.platform_utils import get_shell_profile_paths

    if "=" not in key_value:
        raise click.BadParameter("Expected KEY=VALUE format.", param_hint="KEY_VALUE")

    key, _, value = key_value.partition("=")

    import re as _re
    if not _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        console.print(f"[red]Invalid variable name: {key!r}[/red]")
        raise SystemExit(1)

    profiles = get_shell_profile_paths()
    if not profiles:
        console.print("[yellow]No shell profiles found.[/yellow]")
        return

    profile = profiles[0]
    mgr = EnvManager(profile)
    managed = mgr.get_managed_vars()
    managed[key] = value

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would set {key}={value} in {profile}[/dim]")
        return

    mgr.apply(managed)
    console.print(f"[green]Set {key} in {profile}[/green]")


@env.command(name="remove")
@click.argument("key")
@click.pass_context
def env_remove(ctx: click.Context, key: str) -> None:
    """Remove a managed environment variable."""
    from transfer_kit.env import EnvManager
    from transfer_kit.platform_utils import get_shell_profile_paths

    profiles = get_shell_profile_paths()
    if not profiles:
        console.print("[yellow]No shell profiles found.[/yellow]")
        return

    profile = profiles[0]
    mgr = EnvManager(profile)
    managed = mgr.get_managed_vars()

    if key not in managed:
        console.print(f"[yellow]{key} not found in managed variables.[/yellow]")
        return

    del managed[key]

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would remove {key} from {profile}[/dim]")
        return

    mgr.apply(managed)
    console.print(f"[green]Removed {key} from {profile}[/green]")


@env.command(name="apply")
@click.pass_context
def env_apply(ctx: click.Context) -> None:
    """Apply managed environment variables to the current shell profile."""
    from transfer_kit.env import EnvManager
    from transfer_kit.platform_utils import get_shell_profile_paths

    profiles = get_shell_profile_paths()
    if not profiles:
        console.print("[yellow]No shell profiles found.[/yellow]")
        return

    profile = profiles[0]
    mgr = EnvManager(profile)
    managed = mgr.get_managed_vars()

    if not managed:
        console.print("[yellow]No managed variables to apply.[/yellow]")
        return

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would apply {len(managed)} variables to {profile}[/dim]")
        return

    mgr.apply(managed)
    console.print(f"[green]Applied {len(managed)} variables to {profile}[/green]")


# ---------------------------------------------------------------------------
# sync group
# ---------------------------------------------------------------------------


@main.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Synchronise Claude Code config with a git repository."""
    pass


@sync.command(name="init")
@click.argument("path")
@click.option("--remote", default=None, help="Remote git URL to add as origin.")
@click.pass_context
def sync_init(ctx: click.Context, path: str, remote: str | None) -> None:
    """Initialise a sync repository at PATH."""
    from transfer_kit.core.sync import SyncManager

    mgr = SyncManager(Path(path))

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would initialise sync repo at {path}[/dim]")
        return

    mgr.init_repo(remote_url=remote)
    console.print(f"[green]Initialised sync repository at {path}[/green]")


@sync.command(name="push")
@click.argument("path")
@click.pass_context
def sync_push(ctx: click.Context, path: str) -> None:
    """Push local config to the sync repository at PATH."""
    import tempfile
    import tarfile
    from transfer_kit.core.sync import SyncManager
    from transfer_kit.core.scanner import Scanner
    from transfer_kit.core.exporter import Exporter

    mgr = SyncManager(Path(path))

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would push to {path}[/dim]")
        return

    # Scan, export to a temp archive, extract, then push the extracted dir.
    scanner = Scanner()
    env = scanner.scan()
    exporter = Exporter(env)

    with tempfile.TemporaryDirectory(prefix="transfer_kit_push_") as tmpdir:
        archive_path = Path(tmpdir) / "bundle.tar.gz"
        exporter.export(archive_path)

        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        # The exporter writes files under "transfer_kit_bundle/" prefix
        bundle_dir = extract_dir / "transfer_kit_bundle"
        if not bundle_dir.is_dir():
            # Fallback: use extract_dir directly if no prefix subdir
            bundle_dir = extract_dir

        mgr.push(bundle_dir=bundle_dir)

    console.print(f"[green]Pushed config to {path}[/green]")


@sync.command(name="pull")
@click.argument("path")
@click.pass_context
def sync_pull(ctx: click.Context, path: str) -> None:
    """Pull config from the sync repository at PATH."""
    from transfer_kit.core.sync import SyncManager

    mgr = SyncManager(Path(path))

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would pull from {path}[/dim]")
        return

    mgr.pull()
    console.print(f"[green]Pulled config from {path}[/green]")


@sync.command(name="copy")
@click.option("--to", "to_path", default=None, help="Destination path.")
@click.option("--from", "from_path", default=None, help="Source path.")
@click.option("--execute", is_flag=True, help="Execute the copy immediately.")
@click.option("--on-conflict", type=click.Choice(["skip", "overwrite", "fail"]),
              default="skip", help="Conflict resolution strategy.")
@click.pass_context
def sync_copy(ctx: click.Context, to_path: str | None, from_path: str | None,
              execute: bool, on_conflict: str) -> None:
    """Copy config between locations."""
    from transfer_kit.core.sync import SyncManager

    if not to_path and not from_path:
        raise click.UsageError("At least one of --to or --from is required.")

    path = from_path or to_path
    mgr = SyncManager(Path(path))

    if ctx.obj.get("dry_run"):
        console.print(f"[dim]Dry run: would copy from={from_path} to={to_path}[/dim]")
        return

    mgr.copy_to(dest=Path(to_path), execute=execute, on_conflict=on_conflict)
    console.print("[green]Copy complete.[/green]")
