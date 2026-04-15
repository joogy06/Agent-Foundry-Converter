"""transfer_kit/core/pull.py — End-to-end ``transfer-kit pull`` orchestrator.

Design spec §16 + §15. Implements the inverse flow:

    sanitise URL → clone (or use local path) → load foundry → filter via
    compat → resolve cross-refs → run converter → write idempotently.

Public entry points:

* :func:`run_pull` — full orchestration; callable from both the Click CLI
  and tests.
* :func:`PullResult` — structured return type with exit code, files
  written, archive paths, and the compat report.

Idempotency strategy (design spec §15):

* Files with ``<!-- tk:pull-managed-begin ... -->`` / ``...-end -->``
  markers are overwritten between the markers only.
* Files without markers are content-hashed. If the existing content hash
  matches, no write. If it differs, the pull aborts with a conflict list
  unless ``--force`` (overwrite) or ``--preserve`` (skip + .conflict
  sidecar) is set.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transfer_kit.converters.base import BaseConverter
from transfer_kit.converters.copilot import CopilotConverter
from transfer_kit.converters.copilot_cli import CopilotCliConverter
from transfer_kit.converters.gemini import GeminiConverter
from transfer_kit.converters.windsurf import WindsurfConverter
from transfer_kit.core.compat import CompatMatrix, filter_env
from transfer_kit.core.foundry_loader import FoundryLoader
from transfer_kit.core.url_sanitizer import sanitize_git_url
from transfer_kit.core.xref_resolver import XRefReport, resolve_refs, transitive_include
from transfer_kit.models import ClaudeEnvironment


# Mapping of ``--target`` value → converter class. Kept here rather than in
# a registry so new targets are a one-line add + an import.
TARGETS: dict[str, type[BaseConverter]] = {
    "copilot": CopilotConverter,
    "copilot-cli": CopilotCliConverter,
    "gemini": GeminiConverter,
    "windsurf": WindsurfConverter,
}

# Managed-block markers used for idempotent re-pull inside files that
# permit mid-file edits. Kept in sync with copilot_cli converter.
_BLOCK_BEGIN_PREFIX = "<!-- tk:pull-managed-begin"
_BLOCK_END = "<!-- tk:pull-managed-end -->"


@dataclass
class PullResult:
    """Structured result of a :func:`run_pull` invocation."""

    exit_code: int = 0
    files_written: list[Path] = field(default_factory=list)
    files_skipped: list[Path] = field(default_factory=list)
    conflicts: list[Path] = field(default_factory=list)
    archived: list[Path] = field(default_factory=list)
    compat_report: dict[str, Any] = field(default_factory=dict)
    xref_report: dict[str, Any] = field(default_factory=dict)
    had_credentials: bool = False
    dry_run: bool = False

    def summary(self) -> str:
        return (
            f"pull result: exit={self.exit_code} "
            f"written={len(self.files_written)} "
            f"skipped={len(self.files_skipped)} "
            f"conflicts={len(self.conflicts)} "
            f"archived={len(self.archived)}"
        )


# ---------------------------------------------------------------------------
# Target auto-detection (design spec §16)
# ---------------------------------------------------------------------------


def auto_detect_target() -> str | None:
    """Return a target name based on environment variables, or ``None``."""
    if os.environ.get("COPILOT_CLI_VERSION"):
        return "copilot-cli"
    if os.environ.get("GEMINI_CLI"):
        return "gemini"
    if os.environ.get("VSCODE_PID"):
        # We can't tell from VSCODE_PID alone whether Copilot is installed;
        # assume yes when the user is inside VS Code and hasn't pointed us
        # at a different target.
        return "copilot"
    return None


# ---------------------------------------------------------------------------
# Source acquisition
# ---------------------------------------------------------------------------


def _acquire_source(source: str, ref: str | None, workdir: Path) -> tuple[Path, bool]:
    """Return ``(foundry_root, used_clone)``.

    If ``source`` looks like a URL, clone shallow into ``workdir`` and
    return the clone path with ``used_clone=True``. If it's a local path,
    return it directly with ``used_clone=False``.

    The clone uses ``--config core.autocrlf=false`` so Windows doesn't
    corrupt text files on checkout (design spec §19).
    """
    # URL vs path heuristic — URL iff it contains ``://`` or starts with
    # ``git@``. Local paths always win otherwise.
    if "://" in source or source.startswith("git@"):
        dest = workdir / "foundry"
        cmd = ["git", "clone", "--depth", "1", "--config", "core.autocrlf=false"]
        if ref:
            cmd.extend(["--branch", ref])
        cmd.extend([source, str(dest)])
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {proc.stderr.strip()}")
        return dest, True
    # Local path — use in place. The caller is responsible for making
    # sure it's really a foundry-shaped tree.
    p = Path(source).expanduser().resolve()
    if not p.is_dir():
        raise RuntimeError(f"local source path does not exist or is not a directory: {p}")
    return p, False


# ---------------------------------------------------------------------------
# Idempotent write
# ---------------------------------------------------------------------------


def _sha1(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()


def _extract_managed_block(content: str) -> tuple[str, str, str] | None:
    """Return ``(prefix, block, suffix)`` if the file contains a managed block."""
    begin = content.find(_BLOCK_BEGIN_PREFIX)
    if begin == -1:
        return None
    end = content.find(_BLOCK_END, begin)
    if end == -1:
        return None
    end += len(_BLOCK_END)
    return content[:begin], content[begin:end], content[end:]


def _merge_managed(existing: str, incoming: str) -> str:
    """Replace the managed block in ``existing`` with the one from ``incoming``.

    If either side lacks a managed block the function returns ``incoming``
    unchanged — caller falls back to the normal conflict path.
    """
    ex = _extract_managed_block(existing)
    inc = _extract_managed_block(incoming)
    if not ex or not inc:
        return incoming
    prefix, _old_block, suffix = ex
    _, new_block, _ = inc
    return prefix + new_block + suffix


def _write_file(
    dest: Path,
    content: str,
    *,
    force: bool,
    preserve: bool,
    dry_run: bool,
    result: PullResult,
) -> None:
    """Write ``content`` to ``dest`` honouring idempotence + conflict rules."""
    if dest.is_file():
        existing = dest.read_text(encoding="utf-8", errors="replace")
        if existing == content:
            return  # idempotent no-op
        # Managed-block path — replace only inside the block if both sides
        # are marked.
        merged = _merge_managed(existing, content)
        if merged == existing:
            return
        if merged != content and merged != existing:
            # Successfully merged managed block — write merged
            if dry_run:
                result.files_written.append(dest)
                return
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(merged, encoding="utf-8")
            result.files_written.append(dest)
            return
        # Plain full-file replacement — content differs.
        if force:
            if dry_run:
                result.files_written.append(dest)
                return
            dest.write_text(content, encoding="utf-8")
            result.files_written.append(dest)
            return
        if preserve:
            sidecar = dest.with_suffix(dest.suffix + ".conflict")
            if not dry_run:
                sidecar.write_text(content, encoding="utf-8")
            result.files_skipped.append(dest)
            result.conflicts.append(sidecar)
            return
        # Default — report conflict, do not write.
        result.conflicts.append(dest)
        return
    # New file.
    if dry_run:
        result.files_written.append(dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):  # pragma: no cover — write layer formats first
        import json as _json
        dest.write_text(_json.dumps(content, indent=2) + "\n", encoding="utf-8")
    else:
        dest.write_text(content, encoding="utf-8")
    result.files_written.append(dest)


def _archive_dropped(
    output_dir: Path,
    current_files: set[Path],
    incoming_rels: set[str],
    *,
    no_archive: bool,
    dry_run: bool,
    result: PullResult,
) -> None:
    """Move files present in previous run but absent from the new emission.

    Design spec §15.1 (tier-change semantics): archive, don't delete.
    """
    if not output_dir.is_dir():
        return
    # Only consider files that transfer-kit owns — identified by the path
    # prefix patterns it emits. Walk under known tk-managed subdirs to
    # avoid trampling unrelated user files.
    tk_owned_prefixes = (
        ".github/instructions/",
        ".github/agents/",
        "docs/agent-foundry/_meta/",
        ".gemini/",
        ".windsurf/",
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_root = output_dir / ".tk-pull-archive" / timestamp
    for prefix in tk_owned_prefixes:
        prefix_dir = output_dir / prefix
        if not prefix_dir.is_dir():
            continue
        for existing in prefix_dir.rglob("*"):
            if not existing.is_file():
                continue
            rel = existing.relative_to(output_dir).as_posix()
            if rel in incoming_rels:
                continue
            if rel.startswith(".tk-pull-archive/"):
                continue
            if no_archive:
                if not dry_run:
                    existing.unlink()
                result.archived.append(existing)
                continue
            target = archive_root / rel
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(existing), str(target))
            result.archived.append(target)


# ---------------------------------------------------------------------------
# Dependencies rendering
# ---------------------------------------------------------------------------


def _render_dependencies_md(
    dependency_docs: dict[str, str],
    compat_report: dict[str, Any],
    xref_report: dict[str, Any],
) -> str:
    """Compose ``DEPENDENCIES.md`` from passthrough docs + compat annotations."""
    out = [
        "# Dependencies (generated by transfer-kit pull)",
        "",
        f"Target: `{compat_report.get('target', 'unknown')}`  ",
        f"Tier: `{compat_report.get('tier', 'unknown')}`",
        "",
        "## Compatibility report",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for k, v in (compat_report.get("counts") or {}).items():
        out.append(f"| {k} | {v} |")
    if compat_report.get("gates_g2_shim_emit"):
        out.append("")
        out.append("The G2 schema-validator shim has been emitted at "
                   "`docs/agent-foundry/_meta/gates_g2_shim.py`.")
    if xref_report and xref_report.get("dangling_count"):
        out.append("")
        out.append("## Dangling cross-references")
        out.append("")
        for d in xref_report.get("dangling", []):
            out.append(f"* `{d['holder']}` references `{d['ref']}` — not in this tier.")

    out.append("")
    out.append("## Upstream dependency docs (passthrough)")
    for name, body in sorted(dependency_docs.items()):
        out.append("")
        out.append(f"### `{name}`")
        out.append("")
        out.append("```markdown")
        out.extend(body.splitlines())
        out.append("```")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_pull(
    source: str,
    target: str | None,
    *,
    tier: str = "standard",
    output: str | Path = "./pulled-foundry",
    ref: str | None = None,
    resolve_refs_flag: bool = False,
    force: bool = False,
    preserve: bool = False,
    dry_run: bool = False,
    no_archive: bool = False,
    verbose: bool = False,
    stderr=None,
) -> PullResult:
    """Execute the end-to-end pull flow. Returns a :class:`PullResult`.

    Parameters follow the CLI one-for-one. ``stderr`` defaults to
    ``sys.stderr``; callers may pass a stream to capture warnings during
    tests. The function raises no exceptions for invariant failures;
    instead it sets ``PullResult.exit_code`` and includes a summary.
    """
    err = stderr or sys.stderr
    result = PullResult(dry_run=dry_run)
    output_dir = Path(output).expanduser().resolve()

    # 1. Sanitise URL
    try:
        sanitized, had_creds = sanitize_git_url(source)
    except ValueError as e:
        err.write(f"ERROR: {e}\n")
        result.exit_code = 2
        return result
    result.had_credentials = had_creds
    if had_creds:
        err.write("WARNING: credentials were present in source URL and have been stripped.\n")

    # 2. Target resolve / auto-detect
    if target is None:
        target = auto_detect_target()
        if target is None:
            err.write("ERROR: --target not set and auto-detection failed. "
                      "Set COPILOT_CLI_VERSION / GEMINI_CLI / VSCODE_PID or pass --target.\n")
            result.exit_code = 2
            return result
    if target not in TARGETS:
        err.write(f"ERROR: unknown target {target!r}. Choices: {sorted(TARGETS)}\n")
        result.exit_code = 2
        return result

    # 3. Acquire source (clone or local path)
    with tempfile.TemporaryDirectory(prefix="tk_pull_") as tmp:
        tmp_path = Path(tmp)
        try:
            foundry_root, used_clone = _acquire_source(sanitized, ref, tmp_path)
        except RuntimeError as e:
            err.write(f"ERROR: {e}\n")
            result.exit_code = 2
            return result
        if verbose:
            err.write(f"foundry root: {foundry_root} (clone={used_clone})\n")

        # 4. Load foundry
        env = FoundryLoader(foundry_root).load()

        # 5. Compat filter
        matrix = CompatMatrix.load()
        filtered_env, compat_report = filter_env(env, target=target, tier=tier, matrix=matrix)
        result.compat_report = compat_report

        # 6. Cross-ref resolution
        xref = resolve_refs(filtered_env, env, tier=tier)
        if resolve_refs_flag and xref.dangling:
            filtered_env, added = transitive_include(filtered_env, env)
            compat_report["transitively_included"] = added
            xref = resolve_refs(filtered_env, env, tier=tier)
        result.xref_report = xref.to_dict()
        if xref.dangling and not resolve_refs_flag:
            err.write(f"WARNING: {len(xref.dangling)} dangling cross-references under tier={tier!r}. "
                      f"Re-run with --resolve-refs to include them transitively.\n")

        # 7. Convert
        converter_cls = TARGETS[target]
        converter = converter_cls(filtered_env)
        # Let the converter know the workspace path so path_rewriter
        # substitutions are accurate. Only CopilotCliConverter exposes this.
        if hasattr(converter, "workspace"):
            converter.workspace = str(output_dir)
        results = converter.convert_all(filtered_env)

        # 8. Render DEPENDENCIES.md (all targets that have dependency_docs
        # benefit — we render it once, pull emits it.)
        if filtered_env.dependency_docs:
            results["DEPENDENCIES.md"] = _render_dependencies_md(
                filtered_env.dependency_docs, compat_report, result.xref_report
            )

    # 9. Archive previously-present files that are no longer in results
    incoming_rels = {rel for rel in results.keys()}
    current_files: set[Path] = set()
    _archive_dropped(
        output_dir, current_files, incoming_rels,
        no_archive=no_archive, dry_run=dry_run, result=result,
    )

    # 10. Write
    for rel, content in sorted(results.items()):
        dest = output_dir / rel
        if isinstance(content, (dict, list)):
            import json as _json
            serialised = _json.dumps(content, indent=2) + "\n"
        else:
            serialised = str(content)
        _write_file(
            dest, serialised,
            force=force, preserve=preserve, dry_run=dry_run, result=result,
        )

    # 11. Exit-code semantics: conflict-with-no-resolution → non-zero
    if result.conflicts and not (force or preserve):
        result.exit_code = 2
        err.write(
            f"ERROR: {len(result.conflicts)} content conflicts detected. "
            f"Re-run with --force to overwrite or --preserve to write .conflict sidecars.\n"
        )

    return result


__all__ = ["PullResult", "run_pull", "auto_detect_target", "TARGETS"]
