# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal technical knowledge repository containing deep technical notes in Russian. Notes follow a narrative "story" pattern designed for understanding and retention, not reference lookup.

## File Map

```
.
├── styleguide.md              # writing methodology for all notes
├── network.md                 # networking: from bits to HTTP
├── algorithms-and-data-structures/
│   ├── index.md
│   ├── linear/                # ADT, array, dynamic array, linked list, stack/queue/deque, hash table, LRU, clock-sweep (8 files)
│   ├── non-linear/            # graph, tree, binary tree, BST, heap, B-tree, B+tree, B*tree, inverted index, skip list (10 files)
│   └── techniques/            # dynamic programming (1 file)
├── databases/
│   ├── distribution.md        # shared theory: replication, failover, sharding
│   ├── postgresql/
│   │   ├── index.md
│   │   ├── storage/           # ACID, pages & tuples, TOAST, physical layout (4)
│   │   ├── durability/        # WAL, buffer cache (2)
│   │   ├── concurrency/       # MVCC, anomalies, isolation levels, locks, patterns, mistakes, queues (7)
│   │   ├── maintenance/       # VACUUM (1)
│   │   ├── distribution/      # replication, sharding (2)
│   │   ├── query-processing/  # planner, join order, subqueries/CTE, EXPLAIN, memory/spill, prepared stmts, slow queries, pagination (8)
│   │   ├── indexes/           # B-tree, GIN, GiST, Hash, BRIN, SP-GiST (6)
│   │   └── schema-design/     # constraints, sequences/identity, partitioning (3)
│   └── redis/
│       ├── index.md
│       ├── architecture/      # what is Redis, event loop, pipelining, logical databases (4)
│       ├── atomicity/         # single command, MULTI/EXEC, Lua scripting (3)
│       ├── data-structures/   # string, hash, list, set, sorted set, stream, HyperLogLog, bitmap/bitfield, pub/sub (9)
│       ├── distribution/      # overview, replication, Sentinel, Cluster (4)
│       ├── memory/            # encodings, eviction, key design (3)
│       ├── patterns/          # caching, rate limiting, distributed locks, queues (4)
│       └── persistence/       # RDB, AOF (2)
├── rails/
│   ├── redis/
│   │   ├── index.md           # Redis in Rails apps
│   │   ├── 00–02             # clients/connections, data structures in practice, blocking pitfalls (3)
│   │   └── practice/          # 14 case studies (bitmap-dau, hash-cart, HLL-visitors, etc.)
│   └── sidekiq.md             # Sidekiq deep dive
├── ruby/
│   ├── ruby_collections_notes.md   # Array, Hash, Set internals
│   ├── ruby_concurrency_notes.md   # threads, GIL, fibers
│   ├── ruby_gc_notes.md            # GC algorithms
│   └── ruby_jit_notes.md           # YJIT / ZJIT
└── wip/                        # unfinished drafts
    ├── rust-async-multithreading.md
    └── topic-queue.md
```

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

9. **No prompt/session leakage in notes:** The final text must not contain wording or structure that exists only because of the current conversation/prompt (even if the chat is not mentioned directly). Avoid “author intent” framing like “Чтобы почувствовать…”, “Дадим ментальную модель…”, “по просьбе…”. Headings should describe *what* is being explained, not *why the author decided to include it*. Causal “чтобы” is fine when it describes the system itself (e.g., “Чтобы обеспечить durability, PostgreSQL пишет WAL”).

## File Organization

- One topic per file, kebab-case naming (`postgresql.md`, `indexes.md`)
- Cross-link related notes with relative links
- Large assets (PDFs, images) go in `assets/` directory
- Single `#` title per note; `##` for major sections

## Commits

Conventional commits when needed: `docs(postgresql): explain MVCC snapshots`
