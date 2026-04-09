# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal technical knowledge repository containing deep technical notes in Russian. Notes optimize for understanding and retention through linked facts, explicit dependencies, and causal explanation; index and overview files may be more map-like.

## Repository Structure

Each domain has a domain-named overview file (e.g. `postgresql.md`, `linux.md`) with study order, cross-links, and trade-offs. Use `tree -L 2` or `ls` for the actual file list.

| Directory | What's inside |
|-----------|--------------|
| `styleguide.md` | Writing guide: pedagogy of understanding, design before writing, self-check |
| `structure-guide.md` | File structure: naming, navigation, markup patterns, cascade rules |
| `foundations/` | Bits, bytes, binary, integers, bitwise ops, IEEE 754, text encoding, endianness (6 notes) |
| `programming/` | From "what is a program" through variables, loops, functions, collections, OOP, FP, errors, compilation (13 notes + examples/) |
| `networking/` | Ethernet → IP → TCP → DNS/HTTP/TLS → infrastructure (18 notes in 4 subdirs) |
| `algorithms-and-data-structures/` | Linear (array, list, hash, LRU…), non-linear (tree, BST, heap, B-tree…), techniques (19 notes) |
| `databases/postgresql/` | Storage, durability, concurrency (MVCC, locks), query processing, indexes (29 notes) |
| `databases/sql/` | Relational model, querying, schema, modification, PG-specific extensions (32 notes) |
| `databases/migrations/` | Safe schema changes, schema evolution (expand-contract, backfilling, deploy ordering) (2 notes + index) |
| `databases/redis/` | Architecture, atomicity, data structures, distribution, memory, patterns, persistence (29 notes) |
| `rails/` | Redis in Rails (practice cases), Sidekiq (8-note series: architecture, lifecycle, guarantees, retry, signals, job design, concurrency, testing) |
| `system-design/` | CAP, consistency, consensus, load balancing, reliability, caching, queues, API, microservices (15 notes + cases/) |
| `messaging/` | Kafka architecture: brokers, partitions, replication, consumers, transactions |
| `computer/` | CPU pipeline, memory hierarchy, cache coherency, RAM, storage, buses, ISA, ABI, SIMD (12 notes in 2 axes) |
| `linux/` | Processes, threads, VM, FS, concurrency, syscalls, drivers, ELF, containers (30 notes in 6 subdirs) |
| `ruby/` | VM internals (tokenizer → compiler → execution), object model, methods, collections, GC, JIT, concurrency |
| `wip/` | Unfinished drafts and note-flow process artifacts (*-research/design/review.md) |

## Commands

No build step or runtime. Quick checks:
- Find unfinished items: `rg "TODO|FIXME" .`
- Note lengths: `wc -w *.md`

## Writing Flow

For creating new notes, use the 4-phase flow (`.claude/commands/`):

1. `/note-research <topic>` — explore repo + collaborative brainstorm with author
2. `/note-design <slug>` — draft explanation using prerequisite content → reader-agent perspective → concrete design artifacts → file structure from arc → integration plan
3. `/note-draft <slug>` — write → naive reader agent per file → series uniformity check → integration
4. `/note-review <slug>` — parallel reviewers: structural, checklist, naive reader (mental model building by 5-line blocks)

State between phases persists in `wip/<slug>-{research,design,review}.md`.

### Prompt design principle

**Commands describe what to produce, with constraints that require topic-specific content.** Every design step produces a concrete artifact (draft paragraph, cause-effect chain, example) grounded in specific prerequisite files. Naive reader agents provide perspective by simulating a reader who knows only the declared prerequisites.

Skills instruct the agent to **read specific styleguide sections at runtime** rather than duplicating rules. This keeps rules in one place (styleguide.md) and ensures the agent loads the actual content when needed.

Hookify rules (`.claude/hookify.*.local.md`) enforce mechanical checks in real-time: no metalanguage, no self-reference, no prompt leakage, no interview framing, no CIS location leak, no wide Unicode arrows. Use `/hookify:list` to see all active rules.

## Writing Style Requirements

**Read `styleguide.md` before writing or editing notes.** Key rules:

1. `styleguide.md` is the main writing guide. It defines how to design a strong note before writing, how to unfold it for the reader, and how to self-review it afterward. It is not a section template.

2. No styleguide vocabulary in final text, and no self-referential commentary about what the document is doing. The note should talk about the subject, not about its own pedagogy.

3. No prompt/session leakage. Avoid headings or sentences that only exist because of the current chat or author intent.

4. `Предпосылки` is the strict contract for technical knowledge: anything technical not explained in the note must be explicitly listed there. The repo-wide baseline is only non-technical human basics.

5. Never use a term before it is explained or declared in `Предпосылки`.

6. For explanatory notes, use the full causal pedagogy from `styleguide.md`: motivation, point of entry, scenario, effect, gradual disclosure, and detail-on-demand. For overview and reference-like files, not every explanatory default applies, but the invariants still do.

7. For fundamental or branch-opening notes, prefer role before name. For complex interdependent systems, start with a compact whole-system map before component details.

8. Trace mechanisms to observable effects and to the conditions where the concept becomes the right tool.

9. When using implementation names (`heap_page`, `rb_heap_t`), bind them to human concepts and explain what they are, where they live, and why they matter now.

10. Keep concepts on their abstraction layer. Shared theory belongs above technology-specific implementation details, and adding new notes may require cascading updates to neighboring materials.

11. When rules conflict, follow the priority hierarchy from `styleguide.md` §0.3: invariants (prerequisites contract, no metalanguage) > narrative (scenario before mechanics, bridges) > completeness (lifecycle, effects, etymology) > style (prose vs lists, code anchors).

## File Organization

**Read `structure-guide.md` for full structural patterns.** Key rules:

- One topic per file, kebab-case naming (`postgresql.md`, `indexes.md`)
- Dependency order is encoded in the overview file's "Порядок изучения" section and in prev/next navigation, not in filenames
- 3+ files on one theme → extract into a subdirectory
- Each themed directory has a domain-named overview file (`postgresql.md`, `linux.md`, `sidekiq.md`) with study order, cross-links, and "Как всё связано" trade-offs section
- Shared theory used by multiple technologies → extract to parent level (e.g. `system-design/replication.md`, `system-design/sharding.md`)
- Cross-link related notes with relative links at every mention, not just the first
- `structure-guide.md` owns navigation, callouts, tables, and other markup patterns
- Large assets (PDFs, images) go in `assets/` directory
- Single `#` title per note; `##` for major sections
- When adding a new note, check for cascading changes: update the domain overview file, cross-references in neighboring files, and the file map above

## Content Rules

- **No interview/preparation framing:** notes are technical material, never "interview prep". Words like "собеседование", "интервью", "подготовка к интервью" must not appear.
- **Classical CS examples only:** cities → San Francisco, New York, London, Tokyo. Companies → Amazon, Netflix, Twitter/X, Google. People → Alice, Bob, Charlie. No references to the author or their location.
- **ASCII diagrams — no wide Unicode arrows:** Characters `▼`, `▲`, `►`, `◄`, `▶` render wider than a standard monospace character and break diagram alignment. Use ASCII equivalents: `v`, `^`, `>`, `<`. Standard arrows `→`, `←`, `↑`, `↓` are fine in prose but avoid them inside box-drawing diagrams where alignment matters.

## Gotchas

Common agent mistakes when writing notes (hookify rules catch some mechanically, but awareness helps):

- **Author bias (curse of knowledge):** if YOU understand something, it doesn't mean a reader with only the declared Prerequisites will. Every technical concept needs either explanation or a Prerequisites entry.
- **Metalanguage leakage:** terms like "нарратив", "мостик", "послойное раскрытие" are styleguide vocabulary for the author — they must never appear in notes.
- **Feature-list arc:** listing capabilities in documentation order instead of building a story where each step creates the need for the next.
- **CIS location leakage:** agent may use author's location context (Almaty, Moscow, UTC+5) in examples. Always use classical CS examples.
- **Structure before pedagogy:** file structure (how many files, what order) should be derived from the narrative arc, not decided independently.
- **"Don't think about elephants" effect:** negative instructions in prompts activate the patterns they prohibit. Commands should describe what to produce with constraints that require specific content — concrete artifacts grounded in prerequisite files make generic output structurally impossible.
- **Atomicity has multiple meanings across the repo:** CPU-level atomicity (`computer/atomic-instructions.md`) = indivisible instruction via hardware (LOCK prefix, LL/SC). ACID atomicity (`databases/acid.md`) = all-or-nothing for a transaction group. Redis atomicity (`databases/redis/atomicity/`) = no interleaving because of single-threaded event loop. When writing about atomicity, link to the right definition for the context and clarify which sense is meant.

## Commits

Conventional commits when needed: `docs(postgresql): explain MVCC snapshots`
