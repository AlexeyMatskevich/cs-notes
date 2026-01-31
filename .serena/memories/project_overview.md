# Project overview: `technical`

## Purpose
Personal technical knowledge repository (Markdown notes), primarily in Russian. Notes optimize for clarity, correctness, and long-term recall.

## Tech stack / tooling
- Content: `*.md` notes (UTF-8)
- No build step / runtime
- Optional dev environment via Devbox: `python312` and `uv` (see `devbox.json`)

## Repo structure (high level)
- Top-level `*.md` files are standalone notes
- Larger topics live in directories (examples in this repo: `algorithms-and-data-structures/`, `databases/`, `rails/`, `ruby/`, `wip/`)
- Large reference files (PDFs/images) should go in `assets/` and be linked from notes

## Key guidance docs
- `styleguide.md`: writing methodology + terminology rules (must not leak into notes)
- `AGENTS.md`: repo-specific guidelines
- `CLAUDE.md`: additional writing requirements (aligns with `styleguide.md`)
