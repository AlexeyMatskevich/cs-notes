# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal technical knowledge repository containing deep technical notes in Russian. Notes follow a narrative "story" pattern designed for understanding and retention, not reference lookup.

## Commands

No build step or runtime. Quick checks:
- Find unfinished items: `rg "TODO|FIXME" .`
- Note lengths: `wc -w *.md`

## Writing Style Requirements

**Read `styleguide.md` before writing or editing notes.** Key rules:

1. **Narrative pattern:** goal → problem → solution → result. Each concept answers a question raised by the previous one.

2. **No styleguide vocabulary in final text:** The styleguide uses its own methodology terms internally ("мостик", "нить повествования", "граф зависимостей", "конечный эффект" as a methodology concept, "атомарное понятие", "уровень 0/1/2/3"). These terms must never leak into the notes. Technical terms ("массив", "B-tree", "транзакция") are fine. Normal Russian transitional phrases ("сначала разберём", "перейдём к", "выше мы говорили", "позже увидим") are also fine — they are natural language, not meta-language.

3. **No self-referential commentary about the document structure:** Avoid sentences that describe what the document/section is doing instead of explaining the subject matter (e.g. "В этой части мы прошли по цепочке компромиссов", "Следующий кусок пазла"). The text should talk about the topic, not about itself. This does NOT mean removing ordinary transitions — phrases like "сначала разберём X, потом перейдём к Y" are normal and improve readability.

4. **Dependency order:** Never use a term before defining it. Before writing a section, list its dependencies and ensure each is either already explained, in prerequisites, or explained right now.

5. **Prerequisites section:** Start documents/parts with explicit "Предпосылки" stating what reader should already know.

6. **Concrete effects:** Trace every mechanism to observable outcomes (latency, memory, OOM, CPU), not abstract statements.

7. **Code anchors:** When introducing implementation names (`heap_page`, `rb_heap_t`), bind them to human concepts: "страница кучи (`struct heap_page`)". Include what it is, where it lives, and why it matters now.

8. **Prose over lists:** Bullet points break narrative flow. Use prose when possible.

## File Organization

- One topic per file, kebab-case naming (`postgresql.md`, `indexes.md`)
- Cross-link related notes with relative links
- Large assets (PDFs, images) go in `assets/` directory
- Single `#` title per note; `##` for major sections

## Commits

Conventional commits when needed: `docs(postgresql): explain MVCC snapshots`
