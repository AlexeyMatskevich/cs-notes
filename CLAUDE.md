# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal technical knowledge repository containing deep technical notes in Russian. Notes optimize for understanding and retention through linked facts, explicit dependencies, and causal explanation; index and overview files may be more map-like.

## File Map

```
.
├── styleguide.md              # writing guide and pedagogy of understanding
├── structure-guide.md         # file structure and markup patterns
├── networking/
│   ├── index.md               # networking: study order, how-it-all-connects, URL-to-page path
│   ├── foundations/            # Ethernet, IP, DHCP, NAT, IPv6 (5 files)
│   ├── transport/             # UDP, TCP, TCP tuning (3 files)
│   ├── application/           # DNS, HTTP, TLS, HTTP evolution, WebSocket (5 files)
│   └── infrastructure/        # OSI/TCP-IP models, routing protocols, firewalls, VPN, CDN (5 files)
├── algorithms-and-data-structures/
│   ├── index.md
│   ├── linear/                # ADT, array, dynamic array, linked list, stack/queue/deque, hash table, LRU, clock-sweep (8 files)
│   ├── non-linear/            # graph, tree, binary tree, BST, heap, B-tree, B+tree, B*tree, inverted index, skip list (10 files)
│   └── techniques/            # dynamic programming (1 file)
├── databases/
│   ├── acid.md                # ACID: transaction contract (shared by PostgreSQL, Redis refs)
│   ├── postgresql/
│   │   ├── index.md
│   │   ├── storage/           # ACID in PG (bridge), pages & tuples, TOAST, physical layout (4)
│   │   ├── durability/        # WAL, buffer cache (2)
│   │   ├── concurrency/       # MVCC, anomalies, isolation levels, locks, patterns, mistakes, queues (7)
│   │   ├── maintenance/       # VACUUM (1)
│   │   ├── distribution/      # replication, sharding (2)
│   │   ├── query-processing/  # planner, join order, subqueries/CTE, EXPLAIN, memory/spill, prepared stmts, slow queries (7)
│   │   └── indexes/           # B-tree, GIN, GiST, Hash, BRIN, SP-GiST (6)
│   ├── sql/
│   │   ├── index.md               # SQL: study order, cross-links
│   │   ├── foundations/           # relational model, types & NULL, expressions, normalization (4)
│   │   ├── querying/             # SELECT, sorting, aggregation, JOINs, grouping sets, subqueries/CTE/LATERAL, set ops, windows, pagination (9)
│   │   ├── schema/               # tables & types, constraints, partitioning, views, indexes (5)
│   │   ├── modification/         # DML, transactions, compound DML (3)
│   │   └── postgresql/           # JSONB, arrays, FTS, functions, triggers, compound DML, index ops, exclusion, partitioning, mat views, DISTINCT ON (11)
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
├── computer/
│   ├── index.md               # hardware: CPU, two axes (data-path, programmer-model)
│   ├── 00-cpu.md              # pipeline, superscalar, OoO, branch prediction
│   ├── atomic-instructions.md # CAS, LL/SC, LOCK prefix: bridge between both axes
│   ├── data-path/             # axis 1: where data travels and how fast
│   │   ├── 00-memory-hierarchy.md # L1/L2/L3, cache line, tag/index/offset, locality
│   │   ├── 01-cache-coherency.md  # MESI protocol, false sharing
│   │   ├── 02-ram.md              # DRAM, row buffer, banks, ranks, channels, DDR, NUMA
│   │   ├── 03-storage.md          # HDD (seek, IOPS), SSD (NAND, FTL), NVMe
│   │   └── 04-buses-and-dma.md    # programmed I/O, DMA, interrupts, PCIe
│   └── programmer-model/      # axis 2: what CPU promises to software
│       ├── 00-isa.md              # CISC vs RISC, micro-ops, ARM vs x86
│       ├── 01-abi-and-data-layout.md # calling convention, stack frame, alignment, struct layout
│       └── 02-simd.md              # SIMD: SSE, AVX, NEON, SVE, vectorization
├── linux/
│   ├── index.md               # Linux OS: study order, trade-offs
│   ├── foundations/           # OS basics: processes, threads, fd, VM, FS, scheduler, permissions (9 files)
│   ├── concurrency/           # synchronization, memory ordering, lock-free (3 files)
│   ├── programming/           # signals, mmap, file I/O, sockets, epoll/io_uring, memory mgmt, IPC (7 files)
│   ├── kernel/                # syscall internals, interrupts, drivers, network stack, kernel MM (5 files)
│   ├── infrastructure/        # ELF/linking, terminals, tracing, boot (4 files)
│   └── containers/            # namespaces, cgroups, overlay FS, seccomp, Docker (2 files)
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
│   ├── index.md                         # Ruby: study order, internal vs concurrency
│   └── ruby-concurrency.md                  # threads, GVL, Fiber, Ractor, серверы
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

1. `styleguide.md` is the main writing guide. It defines how to design a strong note before writing, how to unfold it for the reader, and how to self-review it afterward. It is not a section template.

2. No styleguide vocabulary in final text, and no self-referential commentary about what the document is doing. The note should talk about the subject, not about its own pedagogy.

3. No prompt/session leakage. Avoid headings or sentences that only exist because of the current chat or author intent.

4. `Предпосылки` is the strict contract for technical knowledge: anything technical not explained in the note must be explicitly listed there. The repo-wide baseline is only non-technical human basics.

5. Never use a term before it is explained or declared in `Предпосылки`.

6. For explanatory notes, use the full causal pedagogy from `styleguide.md`: motivation, point of entry, scenario, effect, gradual disclosure, and detail-on-demand. For `index.md`, overview, and reference-like files, not every explanatory default applies, but the invariants still do.

7. For fundamental or branch-opening notes, prefer role before name. For complex interdependent systems, start with a compact whole-system map before component details.

8. Trace mechanisms to observable effects and to the conditions where the concept becomes the right tool.

9. When using implementation names (`heap_page`, `rb_heap_t`), bind them to human concepts and explain what they are, where they live, and why they matter now.

10. Keep concepts on their abstraction layer. Shared theory belongs above technology-specific implementation details, and adding new notes may require cascading updates to neighboring materials.

## File Organization

**Read `structure-guide.md` for full structural patterns.** Key rules:

- One topic per file, kebab-case naming (`postgresql.md`, `indexes.md`)
- Files with numeric prefix (`00-acid.md`, `01-pages-and-tuples.md`): prefix = dependency order. File `02` may reference `00` and `01`, not the other way around.
- 3+ files on one theme → extract into a subdirectory
- Each themed directory has an `index.md` (study order, cross-links, "Как всё связано" trade-offs section)
- Shared theory used by multiple technologies → extract to parent level (e.g. `system-design/replication.md`, `system-design/sharding.md`)
- Cross-link related notes with relative links at the point of first mention
- `structure-guide.md` owns navigation, `<details>`, tables, and other markup patterns
- Large assets (PDFs, images) go in `assets/` directory
- Single `#` title per note; `##` for major sections
- When adding a new note, check for cascading changes: update `index.md`, cross-references in neighboring files, and the file map above

## Content Rules

- **No interview/preparation framing:** notes are technical material, never "interview prep". Words like "собеседование", "интервью", "подготовка к интервью" must not appear.
- **Classical CS examples only:** cities → San Francisco, New York, London, Tokyo. Companies → Amazon, Netflix, Twitter/X, Google. People → Alice, Bob, Charlie. No references to the author or their location.
- **ASCII diagrams — no wide Unicode arrows:** Characters `▼`, `▲`, `►`, `◄`, `▶` render wider than a standard monospace character and break diagram alignment. Use ASCII equivalents: `v`, `^`, `>`, `<`. Standard arrows `→`, `←`, `↑`, `↓` are fine in prose but avoid them inside box-drawing diagrams where alignment matters.

## Commits

Conventional commits when needed: `docs(postgresql): explain MVCC snapshots`
