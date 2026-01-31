# Writing style & conventions

## Core writing pattern
- Use a narrative “story” flow: goal → problem → solution → result.
- Prefer prose over long bullet lists; bullets can break narrative flow.

## Strict bans (must not appear in final notes)
- **No styleguide meta-terms** like: «мостик», «нить повествования», «скелет» (as a methodology axis), «граф зависимостей» (as a writing outline), «конечный эффект» (as a methodology concept), «атомарное понятие», «уровень 0/1/2/3».
- **No self-referential commentary** about how the document is structured/assembled (e.g., “в этой части мы прошли…”, “следующий кусок пазла…”).
- **No prompt/session leakage**: don’t include headings or phrasing that exists only because of the current chat/prompt (e.g., “по просьбе…”, “Чтобы почувствовать…”, “Дадим ментальную модель…”).

## Terminology & dependencies
- Never use a term before defining it.
- Add an explicit “Предпосылки” section when appropriate to state assumed knowledge.
- Trace mechanisms to concrete observable outcomes (latency, memory, CPU, OOM, etc.).

## Formatting rules
- One topic per file; cross-link related notes with relative links.
- New files: prefer `kebab-case.md` (existing names may differ).
- Use a single `#` title per note; use `##` for major sections.
- Use fenced code blocks with language tags (e.g. `sql`, `bash`, `ruby`). Keep examples minimal and runnable.
- If adding executable snippets, include a short “How to run” section near the snippet.

## References / safety
- Don’t include secrets or private endpoints.
- For non-obvious claims, add a short “Sources” section with links and relevant version numbers.
