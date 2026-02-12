# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal technical knowledge repository containing deep technical notes in Russian. Notes follow a narrative "story" pattern designed for understanding and retention, not reference lookup.

## File Map

```
.
├── styleguide.md              # writing methodology for all notes
├── structure-guide.md         # structural patterns for notes
├── network.md                 # networking: from bits to HTTP
├── algorithms-and-data-structures/
│   ├── index.md
│   ├── linear/                # ADT, array, dynamic array, linked list, stack/queue/deque, hash table, LRU, clock-sweep (8 files)
│   ├── non-linear/            # graph, tree, binary tree, BST, heap, B-tree, B+tree, B*tree, inverted index, skip list (10 files)
│   └── techniques/            # dynamic programming (1 file)
├── databases/
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
├── system-design/
│   ├── index.md               # system design: architecture, scalability, trade-offs
│   ├── replication.md         # replication: sync/async, lag, failover, split brain, quorum
│   ├── sharding.md            # horizontal partitioning: shard key, resharding, combined architecture
│   ├── 00-cap-theorem.md      # CAP theorem: consistency vs availability during partition
│   ├── 01-consistency-models.md   # spectrum from eventual to linearizability
│   ├── 02-conflict-resolution.md  # LWW, vector clocks, CRDTs
│   ├── 03-consensus.md           # Raft: leader election, log replication, safety
│   ├── 04-read-write-profiles.md # read-heavy vs write-heavy: architecture implications
│   ├── 05-load-balancing.md      # health checks, algorithms, L4/L7, HA
│   ├── 06-reliability-patterns.md # timeout, retry, circuit breaker, bulkhead, idempotency
│   ├── 07-caching.md             # cache levels, coherence, invalidation, cache-aside, stampede
│   ├── 08-delivery-guarantees.md  # at-most-once, at-least-once, exactly-once: delivery semantics in distributed systems
│   ├── 09-message-queues.md      # async communication: broker, ACK, partitions, backpressure, DLQ
│   ├── 10-storage-selection.md   # choosing storage: access patterns, OLTP/OLAP, NoSQL categories, ACID/BASE
│   ├── 11-api-design.md          # REST, GraphQL, gRPC: HTTP methods, pagination, versioning, protocol choice
│   ├── 12-microservices.md       # monolith → modular monolith → microservices, saga, decomposition criteria
│   ├── 13-event-driven-architecture.md  # CQRS, event sourcing: read/write separation, projections, event store
│   └── cases/
│       └── hotel-booking.md      # case study: async booking, state machine, refund flow
├── messaging/
│   ├── index.md               # messaging technologies: Kafka, Pulsar
│   └── kafka/
│       ├── index.md
│       └── architecture/      # broker, topic, partition, offset, replication, producer reliability, consumer internals, transactions (5 files)
├── ruby/
│   ├── internal/
│   │   ├── index.md                         # порядок изучения, связи между группами
│   │   ├── vm/                              # Source → Bytecode → Execution
│   │   │   ├── 00-tokenization-and-parsing.md  # текст → токены → AST
│   │   │   ├── 01-compilation.md               # AST → ISeq
│   │   │   ├── 02-execution.md                 # фреймы, EP, VM цикл
│   │   │   └── 03-control-flow.md              # if/while, break/return
│   │   ├── object-model/                    # Objects, Classes, Modules, Shapes
│   │   │   ├── 00-objects-and-classes.md        # RObject, RClass, метакласс
│   │   │   ├── 01-modules.md                   # include/prepend, CREF
│   │   │   └── 02-shapes.md                    # shape_id, ivar cache
│   │   ├── methods/                         # Method lifecycle
│   │   │   ├── 00-method-dispatch.md           # типы методов, method cache
│   │   │   └── 01-method-definition.md         # def → m_tbl через CREF
│   │   ├── collections/                    # Built-in type internals
│   │   │   ├── index.md                       # embedded/heap pattern, study order
│   │   │   ├── 00-array.md                    # RArray: embedded/heap, growth ×1.5, shared/CoW
│   │   │   ├── 01-hash.md                     # RHash: AR table (≤8), ST table, SipHash
│   │   │   └── 02-string.md                   # RString: embedded/heap, encoding, fstring
│   │   ├── blocks.md                        # замыкания, Proc, lambda
│   │   ├── metaprogramming.md               # eval, instance_eval, define_method, refinements
│   │   ├── gc.md                            # GC: mark-sweep, generational, incremental, compaction
│   │   └── jit.md                           # JIT: YJIT (BBV), ZJIT (method-based), guards, invalidation
│   ├── ruby_collections_notes.md            # Array, Hash, String internals (old, replaced by internal/collections/)
│   └── ruby_concurrency_notes.md            # threads, GIL, fibers
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

1. **Narrative principle:** every document is a connected story, not a reference. Choose a narrative thread (axis) for the document — goal→problem→solution→result, chain of trade-offs, entity lifecycle, request/data path, or system layers. All threads are equal; pick the one that fits the topic best. Each concept should follow from the previous one through causal links.

2. **No styleguide vocabulary in final text:** The styleguide uses its own methodology terms internally ("нарратив", "мостик", "нить повествования", "граф зависимостей", "конечный эффект" as a methodology concept, "атомарное понятие", "уровень 0/1/2/3"). These terms must never leak into the notes. Technical terms ("массив", "B-tree", "транзакция") are fine. Normal Russian transitional phrases ("сначала разберём", "перейдём к", "выше мы говорили", "позже увидим") are also fine — they are natural language, not meta-language.

3. **No self-referential commentary about the document structure:** Avoid sentences that describe what the document/section is doing instead of explaining the subject matter (e.g. "В этой части мы прошли по цепочке компромиссов", "Следующий кусок пазла"). The text should talk about the topic, not about itself. This does NOT mean removing ordinary transitions — phrases like "сначала разберём X, потом перейдём к Y" are normal and improve readability.

4. **Layered disclosure for complex topics:** When a topic has 3+ interdependent components (e.g., MVCC = xmin/xmax + CLOG + Snapshot), start with an abstract layer — a compact mental model of the whole mechanism before diving into each component. Layer 0 = what it does and how parts connect; Layer 1 = each component in detail; Layer 2 = edge cases and optimizations.

5. **Dependency order:** Never use a term before defining it. Before writing a section, list its dependencies and ensure each is either already explained, in prerequisites, or explained right now.

6. **Prerequisites section:** Start documents/parts with explicit "Предпосылки" stating what reader should already know.

7. **Concrete effects:** Trace every mechanism to observable outcomes (latency, memory, OOM, CPU), not abstract statements.

8. **Code anchors:** When introducing implementation names (`heap_page`, `rb_heap_t`), bind them to human concepts: "страница кучи (`struct heap_page`)". Include what it is, where it lives, and why it matters now.

9. **Prose over lists:** Bullet points break narrative flow. Use prose when possible.

10. **No prompt/session leakage in notes:** The final text must not contain wording or structure that exists only because of the current conversation/prompt (even if the chat is not mentioned directly). Avoid “author intent” framing like “Чтобы почувствовать…”, “Дадим ментальную модель…”, “по просьбе…”. Headings should describe *what* is being explained, not *why the author decided to include it*. Causal “чтобы” is fine when it describes the system itself (e.g., “Чтобы обеспечить durability, PostgreSQL пишет WAL”).

11. **Scenario-driven:** each note is built around a realistic scenario that threads through the document. Every technical detail (command, structure, parameter) is introduced at the moment the scenario creates a need for it — not in documentation order. Test: remove all technical details; the scenario alone should read as a coherent story of problems and solutions.

12. **Cross-layer linking, not duplication:** concepts belong to the abstraction layer where they're defined (system-design → technology-specific → applied). Lower-level notes reference the upper level instead of re-explaining. If a statement is true for any message broker (not just Redis Stream), it belongs in `system-design/`, not in `redis/`.

## File Organization

**Read `structure-guide.md` for full structural patterns.** Key rules:

- One topic per file, kebab-case naming (`postgresql.md`, `indexes.md`)
- Files with numeric prefix (`00-acid.md`, `01-pages-and-tuples.md`): prefix = dependency order. File `02` may reference `00` and `01`, not the other way around.
- 3+ files on one theme → extract into a subdirectory
- Each themed directory has an `index.md` (study order, cross-links, "Как всё связано" trade-offs section)
- Shared theory used by multiple technologies → extract to parent level (e.g. `system-design/replication.md`, `system-design/sharding.md`)
- Cross-link related notes with relative links at the point of first mention
- Large assets (PDFs, images) go in `assets/` directory
- Single `#` title per note; `##` for major sections
- When adding a new note, check for cascading changes: update `index.md`, cross-references in neighboring files, and the file map above

## Content Rules

- **No interview/preparation framing:** notes are technical material, never "interview prep". Words like "собеседование", "интервью", "подготовка к интервью" must not appear.
- **Classical CS examples only:** cities → San Francisco, New York, London, Tokyo. Companies → Amazon, Netflix, Twitter/X, Google. People → Alice, Bob, Charlie. No references to the author or their location.
- **ASCII diagrams — no wide Unicode arrows:** Characters `▼`, `▲`, `►`, `◄`, `▶` render wider than a standard monospace character and break diagram alignment. Use ASCII equivalents: `v`, `^`, `>`, `<`. Standard arrows `→`, `←`, `↑`, `↓` are fine in prose but avoid them inside box-drawing diagrams where alignment matters.

## Commits

Conventional commits when needed: `docs(postgresql): explain MVCC snapshots`
