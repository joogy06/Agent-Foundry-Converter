"""transfer_kit/core/comparator.py — Generic config comparator with per-section merge."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DiffItem:
    """A single differing section between source and target."""
    path: Path              # relative file path
    section: str            # section name or key
    current: str | None     # existing content (None = new item)
    incoming: str | None    # incoming content (None = removed item)
    item_type: str          # "new" | "modified" | "removed"


class ConfigComparator:
    """Compare two config directories and produce per-section diffs."""

    def __init__(self, source_dir: Path, target_dir: Path):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)

    def compare(self) -> list[DiffItem]:
        """Scan both directories and return only differences."""
        diffs: list[DiffItem] = []

        source_files = self._scan_files(self.source_dir)
        target_files = self._scan_files(self.target_dir)

        all_rels = sorted(set(source_files) | set(target_files))

        for rel in all_rels:
            src = self.source_dir / rel
            tgt = self.target_dir / rel

            if rel in source_files and rel not in target_files:
                # New file
                content = src.read_text(errors="replace")
                diffs.append(DiffItem(
                    path=Path(rel), section=rel,
                    current=None, incoming=content, item_type="new",
                ))
            elif rel not in source_files and rel in target_files:
                # Removed file
                content = tgt.read_text(errors="replace")
                diffs.append(DiffItem(
                    path=Path(rel), section=rel,
                    current=content, incoming=None, item_type="removed",
                ))
            else:
                # Both exist — check for differences
                src_content = src.read_text(errors="replace")
                tgt_content = tgt.read_text(errors="replace")
                if src_content == tgt_content:
                    continue  # identical, skip
                # Split into sections and diff
                diffs.extend(self._diff_file(Path(rel), tgt_content, src_content))

        return diffs

    def apply_selections(
        self,
        diffs: list[DiffItem],
        selections: dict[int, str],
    ) -> list[Path]:
        """Apply user selections and write merged files.

        selections maps DiffItem index to "keep" | "incoming" | "skip".
        Returns list of files written.
        """
        # Group diffs by file path
        by_file: dict[Path, list[tuple[int, DiffItem]]] = {}
        for idx, diff in enumerate(diffs):
            by_file.setdefault(diff.path, []).append((idx, diff))

        written: list[Path] = []
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")

        for rel_path, items in by_file.items():
            target_file = self.target_dir / rel_path
            source_file = self.source_dir / rel_path

            # Check if any item in this file has "incoming" selected
            any_incoming = any(
                selections.get(idx) == "incoming"
                for idx, _ in items
            )
            if not any_incoming:
                continue  # nothing to write for this file

            # Backup existing file if it exists
            if target_file.exists():
                backup_dir = self.target_dir / "backups" / f"compare_{ts}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_file, backup_path)

            # Determine file type and merge
            suffix = rel_path.suffix.lower()
            if suffix == ".json":
                merged = self._merge_json(target_file, source_file, items, selections)
            elif suffix in (".md", ".markdown"):
                merged = self._merge_markdown(target_file, source_file, items, selections)
            elif suffix in (".sh", ".env", "") and self._is_env_file(rel_path):
                merged = self._merge_env(target_file, source_file, items, selections)
            else:
                # Whole-file: if incoming selected, use source
                merged = source_file.read_text(errors="replace")

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(merged)
            written.append(target_file)

        return written

    # ------------------------------------------------------------------
    # Section splitting
    # ------------------------------------------------------------------

    def _diff_file(self, rel_path: Path, current: str, incoming: str) -> list[DiffItem]:
        """Split a file into sections and return diffs for changed sections only."""
        suffix = rel_path.suffix.lower()

        if suffix == ".json":
            return self._diff_json(rel_path, current, incoming)
        elif suffix in (".md", ".markdown"):
            return self._diff_markdown(rel_path, current, incoming)
        elif suffix in (".sh", ".env", "") and self._is_env_content(current, incoming):
            return self._diff_env(rel_path, current, incoming)
        else:
            # Whole file diff
            return [DiffItem(
                path=rel_path, section=str(rel_path),
                current=current, incoming=incoming, item_type="modified",
            )]

    def _diff_json(self, rel_path: Path, current: str, incoming: str) -> list[DiffItem]:
        """Diff JSON files per top-level key."""
        diffs: list[DiffItem] = []
        try:
            cur_obj = json.loads(current)
            inc_obj = json.loads(incoming)
        except json.JSONDecodeError:
            return [DiffItem(
                path=rel_path, section=str(rel_path),
                current=current, incoming=incoming, item_type="modified",
            )]

        if not isinstance(cur_obj, dict) or not isinstance(inc_obj, dict):
            if cur_obj != inc_obj:
                return [DiffItem(
                    path=rel_path, section=str(rel_path),
                    current=current, incoming=incoming, item_type="modified",
                )]
            return []

        all_keys = sorted(set(cur_obj) | set(inc_obj))
        for key in all_keys:
            cur_val = cur_obj.get(key)
            inc_val = inc_obj.get(key)
            if cur_val == inc_val:
                continue

            cur_str = json.dumps(cur_val, indent=2) if cur_val is not None else None
            inc_str = json.dumps(inc_val, indent=2) if inc_val is not None else None

            if cur_val is None:
                item_type = "new"
            elif inc_val is None:
                item_type = "removed"
            else:
                item_type = "modified"

            diffs.append(DiffItem(
                path=rel_path, section=key,
                current=cur_str, incoming=inc_str, item_type=item_type,
            ))
        return diffs

    def _diff_markdown(self, rel_path: Path, current: str, incoming: str) -> list[DiffItem]:
        """Diff markdown files per ## heading section."""
        cur_sections = self._split_markdown(current)
        inc_sections = self._split_markdown(incoming)
        diffs: list[DiffItem] = []

        all_names = list(dict.fromkeys(list(cur_sections) + list(inc_sections)))
        for name in all_names:
            cur_val = cur_sections.get(name)
            inc_val = inc_sections.get(name)
            if cur_val == inc_val:
                continue

            if cur_val is None:
                item_type = "new"
            elif inc_val is None:
                item_type = "removed"
            else:
                item_type = "modified"

            diffs.append(DiffItem(
                path=rel_path, section=name,
                current=cur_val, incoming=inc_val, item_type=item_type,
            ))
        return diffs

    def _diff_env(self, rel_path: Path, current: str, incoming: str) -> list[DiffItem]:
        """Diff env/shell files per variable."""
        cur_vars = self._parse_env_vars(current)
        inc_vars = self._parse_env_vars(incoming)
        diffs: list[DiffItem] = []

        all_names = list(dict.fromkeys(list(cur_vars) + list(inc_vars)))
        for name in all_names:
            cur_val = cur_vars.get(name)
            inc_val = inc_vars.get(name)
            if cur_val == inc_val:
                continue

            if cur_val is None:
                item_type = "new"
            elif inc_val is None:
                item_type = "removed"
            else:
                item_type = "modified"

            diffs.append(DiffItem(
                path=rel_path, section=name,
                current=cur_val, incoming=inc_val, item_type=item_type,
            ))
        return diffs

    # ------------------------------------------------------------------
    # Section parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_markdown(content: str) -> dict[str, str]:
        """Split markdown into sections by ## headings."""
        sections: dict[str, str] = {}
        # Handle frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                sections["frontmatter"] = f"---{parts[1]}---"
                content = parts[2]

        # Split by ## headings
        pattern = r'^(#{1,3}\s+.+)$'
        chunks = re.split(pattern, content, flags=re.MULTILINE)

        if chunks[0].strip():
            sections["(preamble)"] = chunks[0].strip()

        i = 1
        while i < len(chunks):
            heading = chunks[i].strip()
            body = chunks[i + 1] if i + 1 < len(chunks) else ""
            sections[heading] = (heading + "\n" + body).strip()
            i += 2

        return sections

    @staticmethod
    def _parse_env_vars(content: str) -> dict[str, str]:
        """Parse env file into {VAR_NAME: full_line} dict."""
        env_vars: dict[str, str] = {}
        comment_buffer: list[str] = []

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                comment_buffer.append(line)
                continue
            match = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)=(.*)$', stripped)
            if match:
                name = match.group(1)
                full = "\n".join(comment_buffer + [line])
                env_vars[name] = full
                comment_buffer = []
            else:
                comment_buffer = []

        return env_vars

    @staticmethod
    def _is_env_file(rel_path: Path) -> bool:
        name = rel_path.name.lower()
        return name in (".env", "env") or name.endswith(".sh") or name.endswith(".env")

    @staticmethod
    def _is_env_content(current: str, incoming: str) -> bool:
        """Heuristic: looks like env file if most lines are export/assignment."""
        for content in (current, incoming):
            lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
            if not lines:
                continue
            env_lines = sum(1 for l in lines if re.match(r'^(?:export\s+)?[A-Za-z_]\w*=', l))
            if env_lines / len(lines) > 0.5:
                return True
        return False

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def _merge_json(self, target_file, source_file, items, selections) -> str:
        cur_obj = json.loads(target_file.read_text()) if target_file.exists() else {}
        inc_obj = json.loads(source_file.read_text()) if source_file.exists() else {}

        result = dict(cur_obj)
        for idx, diff in items:
            action = selections.get(idx, "keep")
            if action == "incoming":
                if diff.incoming is not None:
                    result[diff.section] = inc_obj.get(diff.section)
                else:
                    result.pop(diff.section, None)

        return json.dumps(result, indent=2) + "\n"

    def _merge_markdown(self, target_file, source_file, items, selections) -> str:
        cur_sections = self._split_markdown(
            target_file.read_text() if target_file.exists() else ""
        )
        inc_sections = self._split_markdown(
            source_file.read_text() if source_file.exists() else ""
        )

        result = dict(cur_sections)
        for idx, diff in items:
            action = selections.get(idx, "keep")
            if action == "incoming":
                if diff.incoming is not None:
                    result[diff.section] = diff.incoming
                else:
                    result.pop(diff.section, None)

        return "\n\n".join(result.values()) + "\n"

    def _merge_env(self, target_file, source_file, items, selections) -> str:
        cur_vars = self._parse_env_vars(
            target_file.read_text() if target_file.exists() else ""
        )
        inc_vars = self._parse_env_vars(
            source_file.read_text() if source_file.exists() else ""
        )

        result = dict(cur_vars)
        for idx, diff in items:
            action = selections.get(idx, "keep")
            if action == "incoming":
                if diff.incoming is not None:
                    result[diff.section] = diff.incoming
                else:
                    result.pop(diff.section, None)

        return "\n".join(result.values()) + "\n"

    # ------------------------------------------------------------------
    # File scanning
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_files(directory: Path) -> set[str]:
        """Return set of relative file paths in directory, excluding backups and hidden dirs."""
        if not directory.is_dir():
            return set()
        files = set()
        for f in directory.rglob("*"):
            if f.is_file():
                rel = f.relative_to(directory).as_posix()
                # Skip backup dirs, .git, __pycache__
                if any(part.startswith(".") or part == "__pycache__" or part == "backups"
                       for part in f.relative_to(directory).parts):
                    continue
                files.add(rel)
        return files
