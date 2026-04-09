#!/usr/bin/env python3
"""
Rename files for Obsidian graph readability:
1. Strip numeric prefixes (00-cpu.md → cpu.md)
2. Rename index.md to parent-dir-name.md (with collision overrides)
3. Update all markdown links across the repository
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Override names for index.md files where parent-dir-name would collide
INDEX_OVERRIDES = {
    "databases/sql/postgresql/index.md": "pg-extensions.md",
    "rails/redis/index.md": "redis-in-rails.md",
    "ruby/internal/index.md": "internals.md",
}

# Directories to skip entirely
SKIP_DIRS = {".obsidian", ".claude", ".codex", ".git", "node_modules", "scripts"}

# Files that should never be renamed
SKIP_FILES = {"CLAUDE.md", "AGENTS.md", "styleguide.md", "structure-guide.md", "computer.md"}


def build_rename_map() -> dict[Path, Path]:
    """Build old_path → new_path mapping for all files to rename."""
    rename_map: dict[Path, Path] = {}

    for md_file in sorted(REPO_ROOT.rglob("*.md")):
        rel = md_file.relative_to(REPO_ROOT)

        # Skip hidden/system dirs
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        # Skip specific files
        if rel.name in SKIP_FILES and len(rel.parts) == 1:
            continue

        # Skip wip/ files themselves (but their links will be updated)
        if rel.parts[0] == "wip":
            continue

        name = rel.name

        # Case 1: index.md → parent-dir-name.md (or override)
        if name == "index.md":
            rel_str = str(rel).replace("\\", "/")
            if rel_str in INDEX_OVERRIDES:
                new_name = INDEX_OVERRIDES[rel_str]
            else:
                parent_dir = rel.parent.name
                new_name = f"{parent_dir}.md"
            new_path = md_file.parent / new_name
            rename_map[md_file] = new_path

        # Case 2: NN-name.md → name.md
        elif re.match(r"^\d{2}-", name):
            new_name = re.sub(r"^\d{2}-", "", name)
            new_path = md_file.parent / new_name
            rename_map[md_file] = new_path

    return rename_map


def git_mv_all(rename_map: dict[Path, Path], dry_run: bool) -> None:
    """Execute git mv for all renames."""
    for old, new in sorted(rename_map.items()):
        old_rel = old.relative_to(REPO_ROOT)
        new_rel = new.relative_to(REPO_ROOT)
        if dry_run:
            print(f"  git mv {old_rel} → {new_rel}")
        else:
            subprocess.run(
                ["git", "mv", str(old), str(new)],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )


def build_basename_map(rename_map: dict[Path, Path]) -> dict[Path, dict[str, str]]:
    """Build per-directory old_basename → new_basename mapping."""
    dir_map: dict[Path, dict[str, str]] = {}
    for old, new in rename_map.items():
        d = old.parent
        if d not in dir_map:
            dir_map[d] = {}
        dir_map[d][old.name] = new.name
    return dir_map


def resolve_link_target(source_file: Path, link_path: str) -> Path | None:
    """Resolve a relative link path to an absolute filesystem path."""
    # Strip anchor
    path_part = link_path.split("#")[0]
    if not path_part:
        return None
    if not path_part.endswith(".md"):
        return None

    target = (source_file.parent / path_part).resolve()
    return target


def update_links_in_content(
    content: str,
    source_file: Path,
    rename_map: dict[Path, Path],
) -> str:
    """Update all markdown links in content, skipping fenced code blocks."""

    # Split content into code blocks and non-code blocks
    parts = re.split(r"(```[^`]*```)", content, flags=re.DOTALL)

    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside a fenced code block — don't touch
            result.append(part)
            continue

        # Update markdown links: [text](path) and [text](path#anchor)
        def replace_link(match: re.Match) -> str:
            full = match.group(0)
            text = match.group(1)
            link = match.group(2)

            # Skip external links
            if link.startswith(("http://", "https://", "mailto:")):
                return full

            # Split path and anchor
            if "#" in link:
                path_part, anchor = link.split("#", 1)
                anchor = "#" + anchor
            else:
                path_part = link
                anchor = ""

            if not path_part or not path_part.endswith(".md"):
                return full

            # Resolve to absolute path (using pre-rename locations)
            target = (source_file.parent / path_part).resolve()

            if target not in rename_map:
                return full

            # Get new filename
            new_target = rename_map[target]
            new_name = new_target.name

            # Replace only the basename in the link path
            # path_part might be "../concurrency/00-mvcc.md"
            # We need to replace the last component
            last_slash = path_part.rfind("/")
            if last_slash >= 0:
                new_path = path_part[: last_slash + 1] + new_name
            else:
                new_path = new_name

            return f"[{text}]({new_path}{anchor})"

        updated = re.sub(r"\[([^\]]*)\]\(([^)]+)\)", replace_link, part)

        # Also update wikilinks: [[path]] and [[path|display]]
        def replace_wikilink(match: re.Match) -> str:
            inner = match.group(1)
            # Split display text
            if "|" in inner:
                path_part, display = inner.split("|", 1)
                display = "|" + display
            else:
                path_part = inner
                display = ""

            # Strip anchor for resolution
            if "#" in path_part:
                file_part, anchor = path_part.split("#", 1)
                anchor = "#" + anchor
            else:
                file_part = path_part
                anchor = ""

            # Try to resolve
            if file_part.endswith(".md"):
                target = (source_file.parent / file_part).resolve()
            else:
                target = (source_file.parent / (file_part + ".md")).resolve()

            if target not in rename_map:
                return match.group(0)

            new_target = rename_map[target]
            new_name = new_target.stem  # wikilinks typically use name without .md

            last_slash = file_part.rfind("/")
            if last_slash >= 0:
                new_file = file_part[: last_slash + 1] + new_name
            else:
                new_file = new_name

            return f"[[{new_file}{anchor}{display}]]"

        updated = re.sub(r"\[\[([^\]]+)\]\]", replace_wikilink, updated)
        result.append(updated)

    return "".join(result)


def update_all_links(rename_map: dict[Path, Path], dry_run: bool) -> int:
    """Update links in all .md files. Returns count of changed files.

    IMPORTANT: Must be called BEFORE git mv, because link resolution
    uses the original file locations.
    """
    changed = 0

    # Collect all .md files (including wip/, excluding system dirs)
    all_md = sorted(
        p
        for p in REPO_ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.relative_to(REPO_ROOT).parts)
    )

    for md_file in all_md:
        original = md_file.read_text(encoding="utf-8")
        updated = update_links_in_content(original, md_file, rename_map)

        if updated != original:
            changed += 1
            rel = md_file.relative_to(REPO_ROOT)
            if dry_run:
                print(f"  LINKS: {rel}")
            else:
                md_file.write_text(updated, encoding="utf-8")

    return changed


def verify_no_collisions(rename_map: dict[Path, Path]) -> list[str]:
    """Check that no two files would get the same new path."""
    seen: dict[Path, Path] = {}
    errors = []
    for old, new in rename_map.items():
        if new in seen:
            errors.append(
                f"COLLISION: {old.relative_to(REPO_ROOT)} and "
                f"{seen[new].relative_to(REPO_ROOT)} both → {new.relative_to(REPO_ROOT)}"
            )
        seen[new] = old
    return errors


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN (no files will be modified) ===\n")

    # Build rename map
    rename_map = build_rename_map()
    index_count = sum(1 for p in rename_map if p.name == "index.md")
    numbered_count = len(rename_map) - index_count

    print(f"Rename map: {len(rename_map)} files ({index_count} index, {numbered_count} numbered)\n")

    # Verify no collisions
    errors = verify_no_collisions(rename_map)
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    # Phase 1: Update links FIRST (before renaming, so paths resolve correctly)
    print("Phase 1: Updating links...")
    link_changes = update_all_links(rename_map, dry_run)
    print(f"  → {link_changes} files with updated links\n")

    # Phase 2: Rename files
    print("Phase 2: Renaming files...")
    git_mv_all(rename_map, dry_run)
    print(f"  → {len(rename_map)} files renamed\n")

    if dry_run:
        print("=== DRY RUN COMPLETE ===")
    else:
        print("=== DONE ===")
        print(f"Total: {len(rename_map)} files renamed, {link_changes} files with link updates")


if __name__ == "__main__":
    main()
