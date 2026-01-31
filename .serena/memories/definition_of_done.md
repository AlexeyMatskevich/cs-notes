# Definition of done (notes work)

Before considering a note edit “done”:
- Headings: exactly one `#` title; `##` for major sections; headings describe the subject.
- Content: no styleguide meta-terms; no self-referential “document about itself” phrasing; no prompt/session leakage.
- Dependencies: terms introduced before use; add “Предпосылки” if the reader must know prerequisites.
- Examples: fenced code blocks with language tags; minimal + runnable; include “How to run” when execution is expected.
- References: add a short “Sources” section for non-obvious claims (include versions when relevant).
- Assets: put large PDFs/images in `assets/` and link them.
- Quick checks: run `rg "TODO|FIXME" .` and (optionally) `wc -w *.md`.
