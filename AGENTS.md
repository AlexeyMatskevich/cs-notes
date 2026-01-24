# Repository Guidelines

This repository is a collection of technical notes. Contributions should optimize for clarity, correctness, and future recall.

## Project Structure & Module Organization

- Top-level `*.md` files are standalone notes (e.g. `postgresql.md`, `redis_notes.md`, `b-tree.md`).
- Large reference files (PDFs, images) should go in `assets/` (create if needed) and be linked from notes.
- Prefer one topic per file; cross-link related notes using relative links.

## Build, Test, and Development Commands

There is no build step or runtime for this repo.

- Preview Markdown in your editor, or serve locally: `python -m http.server` (open `http://localhost:8000/`).
- Quick sanity checks: `rg "TODO|FIXME" .` and `wc -w *.md` to keep notes focused.

## Coding Style & Naming Conventions

- Follow `styleguide.md` for the writing “story” pattern (goal → problem → solution → result) and terminology rules.
- Use a single `#` title per note; use `##` for major sections; keep headings descriptive.
- Use fenced code blocks with language tags (e.g. ```sql, ```rust) and keep examples minimal but runnable.
- File names: prefer `kebab-case.md` for new notes (existing `_` names are fine).

## Testing Guidelines

No automated tests. If you add executable snippets, include a short “How to run” section near the snippet.

## Commit & Pull Request Guidelines

This folder is not currently a Git work tree, so there is no existing commit style to follow.

- If/when Git is used, prefer Conventional Commits: `docs(postgresql): explain MVCC snapshots`.
- PRs (or review requests) should include: a short summary, sources/links, and any renamed/moved files called out explicitly.

## Security & References

- Never include secrets, private endpoints, or internal credentials in notes.
- For non-obvious claims, add a short “Sources” section with links and relevant version numbers.
