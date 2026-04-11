#!/usr/bin/env python3
"""
Convert repository markdown to Obsidian-compatible format.

Conversions:
1. <details><summary>Title</summary> ... </details> → > [!info]- Title callouts
2. <br> / <br/> inside Mermaid diagrams → \\n (Mermaid newline)
3. Markdown links with heading anchors → Obsidian wikilinks
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\n]+)\)")


def split_fenced_code_blocks(content: str) -> list[tuple[bool, str]]:
    """Split content into (is_code_block, text) chunks."""

    chunks: list[tuple[bool, str]] = []
    current: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in content.splitlines(keepends=True):
        if not in_fence:
            match = re.match(r"^[ \t]*(`{3,}|~{3,})", line)
            if match:
                if current:
                    chunks.append((False, "".join(current)))
                    current = []
                fence_marker = match.group(1)
                fence_char = fence_marker[0]
                fence_len = len(fence_marker)
                in_fence = True
                current.append(line)
                continue

            current.append(line)
            continue

        current.append(line)
        if re.match(rf"^[ \t]*{re.escape(fence_char)}{{{fence_len},}}\s*$", line):
            chunks.append((True, "".join(current)))
            current = []
            in_fence = False
            fence_char = ""
            fence_len = 0

    if current:
        chunks.append((in_fence, "".join(current)))

    return chunks


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


def convert_anchor_links_to_obsidian(content: str, source_file: Path) -> str:
    """Convert markdown links with heading anchors to Obsidian wikilinks."""

    def replace_link(match: re.Match) -> str:
        full = match.group(0)
        text = match.group(1)
        target = match.group(2).strip()

        if "#" not in target:
            return full

        if target.startswith(("http://", "https://", "mailto:", "obsidian://", "/")):
            return full

        path_part, anchor = target.split("#", 1)
        if not anchor:
            return full

        alias = text.replace("|", r"\|")

        if not path_part:
            return f"[[#{anchor}|{alias}]]"

        if not path_part.endswith(".md"):
            return full

        resolved_target = (source_file.parent / path_part).resolve()
        if not resolved_target.is_file():
            return full

        try:
            repo_relative = resolved_target.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return full

        if resolved_target == source_file.resolve():
            return f"[[#{anchor}|{alias}]]"

        vault_path = repo_relative[:-3] if repo_relative.endswith(".md") else repo_relative
        return f"[[{vault_path}#{anchor}|{alias}]]"

    converted_chunks: list[str] = []
    for is_code_block, chunk in split_fenced_code_blocks(content):
        if is_code_block:
            converted_chunks.append(chunk)
            continue
        converted_chunks.append(MARKDOWN_LINK_RE.sub(replace_link, chunk))

    return "".join(converted_chunks)


def convert_file(
    path: Path,
    dry_run: bool = False,
    anchor_links_only: bool = False,
) -> bool:
    """Convert a single file. Returns True if changes were made."""
    original = path.read_text(encoding="utf-8")
    converted = original

    if not anchor_links_only:
        converted = convert_details_to_callout(converted)
        converted = convert_mermaid_br(converted)

    converted = convert_anchor_links_to_obsidian(converted, path)

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
    anchor_links_only = "--anchor-links-only" in sys.argv

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
        if convert_file(path, dry_run=dry_run, anchor_links_only=anchor_links_only):
            changed += 1

    print(f"\n{'Would change' if dry_run else 'Changed'}: {changed} files")
    print(f"Total scanned: {len(md_files)} files")


if __name__ == "__main__":
    main()
