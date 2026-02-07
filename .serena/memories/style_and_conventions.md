# Style and Conventions

Full rules: `styleguide.md`. Key points below.

## Writing (all notes are in Russian)

1. **Narrative, not reference.** Every doc is a connected story. Choose an axis: goal→problem→solution→result, trade-off chain, entity lifecycle, request path, or system layers.
2. **No styleguide meta-terms in notes.** Banned: «нарратив», «мостик», «нить повествования», «граф зависимостей», «конечный эффект» (as methodology), «атомарное понятие», «уровень 0/1/2/3». Technical terms and normal Russian transitions are fine.
3. **No self-referential commentary.** Text talks about the topic, not about itself.
4. **Layered disclosure.** 3+ interdependent components → abstract mental model first (Layer 0), then details (Layer 1), then edge cases (Layer 2).
5. **Dependency order.** Never use a term before defining it.
6. **Prerequisites section.** Start with explicit "Предпосылки".
7. **Concrete effects.** Trace to observable outcomes (latency, memory, OOM, CPU).
8. **Code anchors.** Bind implementation names to human concepts: "страница кучи (`struct heap_page`)".
9. **Prose over lists.** Bullet points break narrative flow.
10. **No prompt/session leakage.** No "author intent" framing.
11. **Scenario-driven.** Each note built around a realistic scenario. Details introduced when scenario demands them.
12. **Cross-layer linking.** Concepts belong to their abstraction layer. Lower levels link up, don't re-explain.

## Content Restrictions
- **No interview framing.** Words like «собеседование», «интервью» must not appear.
- **Classical CS examples.** Cities: SF, NY, London, Tokyo. Companies: Amazon, Netflix, Google. People: Alice, Bob, Charlie. No personal references.

## File Naming
- kebab-case: `query-processing.md`, `data-structures/`
- Numbered prefix = dependency order: `00-acid.md`, `01-pages-and-tuples.md`
- One `#` title, `##` for major sections

## Cross-references
- Relative paths from current file
- Link at point of first mention
- Shared theory → parent level file (e.g. `databases/distribution.md`)
