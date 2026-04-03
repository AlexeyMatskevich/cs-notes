# Repository Guidelines

This repository is a collection of technical notes. Contributions should optimize for clarity, correctness, and future recall.

## Repository Structure

See `CLAUDE.md` → "Repository Structure" for the domain map. Use `tree -L 2` for the actual file list.

## Build, Test, and Development Commands

There is no build step or runtime for this repo.

- Quick sanity checks: `rg "TODO|FIXME" .` and `wc -w *.md` to keep notes focused.

## Coding Style & Naming Conventions

- Follow `styleguide.md` for note-writing principles: pedagogy of understanding, `Предпосылки` contract, dependency order, narrative/scenario guidance, and self-check.
- Follow `structure-guide.md` for file structure, navigation, `<details>`, tables, and other markup patterns.
- Notes must not “leak” the prompt/session: the final text should read as standalone subject matter, without “author intent” phrasing that exists only because of the current chat (e.g., headings like “Чтобы почувствовать…” or “по просьбе…”).
- Use a single `#` title per note; use `##` for major sections; keep headings descriptive.
- Use fenced code blocks with language tags (e.g. ```sql, ```rust) and keep examples minimal but runnable.
- File names: prefer `kebab-case.md` for new notes (existing `_` names are fine).
- **ASCII diagrams — no wide Unicode arrows:** Do not use `▼`, `▲`, `►`, `◄`, `▶` — they render wider than a monospace character and break alignment. Use `v`, `^`, `>`, `<` instead.

## Testing Guidelines

No automated tests. If you add executable snippets, include a short “How to run” section near the snippet.

## Commit & Pull Request Guidelines

This folder is not currently a Git work tree, so there is no existing commit style to follow.

- If/when Git is used, prefer Conventional Commits: `docs(postgresql): explain MVCC snapshots`.
- PRs (or review requests) should include: a short summary, sources/links, and any renamed/moved files called out explicitly.

## Security & References

- Never include secrets, private endpoints, or internal credentials in notes.
- For non-obvious claims, add a short “Sources” section with links and relevant version numbers.
