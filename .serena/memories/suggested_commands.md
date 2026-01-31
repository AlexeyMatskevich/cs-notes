# Suggested commands

## Quick repo sanity checks
- Find unfinished items: `rg "TODO|FIXME" .`
- Check note sizes (top-level): `wc -w *.md`

## Navigation / search
- List structure: `ls` / `ls -la`
- Find files: `find . -maxdepth 2 -type f -name "*.md"`
- Search text: `rg "pattern" .`

## Optional devbox environment
- Enter devbox shell (if needed): `devbox shell`
  - Provides `python312` and `uv` (see `devbox.json`).
