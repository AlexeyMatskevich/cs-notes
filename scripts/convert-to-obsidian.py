#!/usr/bin/env python3
"""
Convert repository markdown to Obsidian-compatible format.

Conversions:
1. <details><summary>Title</summary> ... </details> → > [!info]- Title callouts
2. <br> / <br/> inside Mermaid diagrams → \\n (Mermaid newline)
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def convert_details_to_callout(content: str) -> str:
    """Convert <details><summary>...</summary>...</details> to Obsidian callouts."""

    # Pattern: <details>\n<summary>TITLE</summary>\n\nCONTENT\n</details>
    # The content between summary close and </details> can be multiline with code blocks etc.

    def replace_details(match: re.Match) -> str:
        title = match.group(1).strip()
        body = match.group(2)

        # Strip leading/trailing blank lines from body
        body = body.strip("\n")

        # Convert body lines to blockquote format
        lines = body.split("\n")
        quoted_lines = []
        for line in lines:
            if line == "":
                quoted_lines.append(">")
            else:
                quoted_lines.append(f"> {line}")

        quoted_body = "\n".join(quoted_lines)
        return f"> [!info]- {title}\n{quoted_body}"

    # Match <details> with optional whitespace, then <summary>...</summary>, then content, then </details>
    pattern = re.compile(
        r"<details>\s*\n\s*<summary>(.*?)</summary>\s*\n"  # opening tags
        r"(.*?)"  # body (non-greedy)
        r"\n\s*</details>",  # closing tag
        re.DOTALL,
    )

    return pattern.sub(replace_details, content)


def convert_mermaid_br(content: str) -> str:
    """Normalize <br/> and <br /> to <br> inside mermaid blocks (Obsidian compatible)."""

    def normalize_br_in_mermaid(match: re.Match) -> str:
        mermaid_content = match.group(1)
        # Normalize <br/> and <br /> to <br> (Obsidian Mermaid supports <br>)
        fixed = re.sub(r"<br\s*/>", "<br>", mermaid_content)
        return f"```mermaid{fixed}```"

    pattern = re.compile(r"```mermaid(.*?)```", re.DOTALL)
    return pattern.sub(normalize_br_in_mermaid, content)


def convert_file(path: Path, dry_run: bool = False) -> bool:
    """Convert a single file. Returns True if changes were made."""
    original = path.read_text(encoding="utf-8")
    converted = original

    converted = convert_details_to_callout(converted)
    converted = convert_mermaid_br(converted)

    if converted != original:
        if dry_run:
            print(f"  WOULD CHANGE: {path.relative_to(REPO_ROOT)}")
        else:
            path.write_text(converted, encoding="utf-8")
            print(f"  CHANGED: {path.relative_to(REPO_ROOT)}")
        return True
    return False


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN (no files will be modified) ===\n")

    # Find all .md files, skip hidden dirs and scripts/
    md_files = sorted(
        p
        for p in REPO_ROOT.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(REPO_ROOT).parts)
        and not str(p.relative_to(REPO_ROOT)).startswith("scripts/")
    )

    changed = 0
    for path in md_files:
        if convert_file(path, dry_run=dry_run):
            changed += 1

    print(f"\n{'Would change' if dry_run else 'Changed'}: {changed} files")
    print(f"Total scanned: {len(md_files)} files")


if __name__ == "__main__":
    main()
