# Repository Guidelines

This repository is a collection of technical notes. Contributions should optimize for clarity, correctness, and future recall.

## File Map

```
.
├── styleguide.md              # writing methodology for all notes
├── structure-guide.md         # structural patterns for notes
├── networking/
│   ├── index.md               # networking: study order, how-it-all-connects
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
│   ├── postgresql/
│   │   ├── index.md
│   │   ├── storage/           # ACID, pages & tuples, TOAST, physical layout (4)
│   │   ├── durability/        # WAL, buffer cache (2)
│   │   ├── concurrency/       # MVCC, anomalies, isolation levels, locks, patterns, mistakes, queues (7)
│   │   ├── maintenance/       # VACUUM (1)
│   │   ├── distribution/      # replication, sharding (2)
│   │   ├── query-processing/  # planner, join order, subqueries/CTE, EXPLAIN, memory/spill, prepared stmts, slow queries (7)
│   │   └── indexes/           # B-tree, GIN, GiST, Hash, BRIN, SP-GiST (6)
│   ├── sql/
│   │   ├── index.md               # SQL: study order, cross-links
│   │   ├── foundations/           # relational model, types & NULL, expressions, normalization (4)
│   │   ├── querying/             # SELECT, sorting, aggregation, JOINs, grouping sets, subqueries/CTE, set ops, windows, pagination (9)
│   │   ├── schema/               # tables & types, constraints, partitioning, views (4)
│   │   ├── modification/         # DML, transactions (2)
│   │   └── postgresql/           # JSONB, arrays & ranges, FTS, functions & procedures (4)
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
├── computer/
│   ├── index.md               # hardware: CPU, two axes (data-path, programmer-model)
│   ├── 00-cpu.md              # pipeline, superscalar, OoO, branch prediction
│   ├── data-path/             # axis 1: where data travels and how fast
│   │   ├── 00-memory-hierarchy.md # L1/L2/L3, cache line, tag/index/offset, locality
│   │   ├── 01-cache-coherency.md  # MESI protocol, false sharing
│   │   ├── 02-ram.md              # DRAM, row buffer, banks, ranks, channels, DDR, NUMA
│   │   ├── 03-storage.md          # HDD (seek, IOPS), SSD (NAND, FTL), NVMe
│   │   └── 04-buses-and-dma.md    # programmed I/O, DMA, interrupts, PCIe
│   └── programmer-model/      # axis 2: what CPU promises to software
│       ├── 00-isa.md              # CISC vs RISC, micro-ops, ARM vs x86
│       └── 01-abi-and-data-layout.md # calling convention, stack frame, alignment, struct layout
├── system-design/
│   ├── index.md               # system design: architecture, scalability, trade-offs
│   ├── 00-cap-theorem.md      # CAP theorem: consistency vs availability during partition
│   ├── 01-consistency-models.md   # spectrum from eventual to linearizability
│   ├── 02-conflict-resolution.md  # LWW, vector clocks, CRDTs
│   ├── 03-consensus.md           # Raft: leader election, log replication, safety
│   ├── 04-read-write-profiles.md # read-heavy vs write-heavy: architecture implications
│   ├── 05-load-balancing.md      # health checks, algorithms, L4/L7, HA
│   ├── 06-reliability-patterns.md # timeout, retry, circuit breaker, bulkhead, idempotency
│   ├── 07-caching.md             # cache levels, coherence, invalidation, cache-aside, stampede
│   └── cases/
│       └── hotel-booking.md      # case study: async booking, state machine, refund flow
├── ruby/
│   ├── internal/
│   │   ├── index.md                    # порядок изучения, связи между группами
│   │   ├── vm/                         # tokenization, compilation, execution, control flow (4)
│   │   ├── object-model/               # objects & classes, modules, shapes (3)
│   │   ├── methods/                    # method dispatch, method definition (2)
│   │   ├── blocks.md                   # замыкания, Proc, lambda
│   │   ├── metaprogramming.md          # eval, instance_eval, define_method, refinements
│   │   ├── gc.md                       # GC: mark-sweep, generational, incremental, compaction
│   │   └── jit.md                      # JIT: YJIT (BBV), ZJIT (method-based), guards, invalidation
│   └── ruby_concurrency_notes.md       # threads, GIL, fibers
└── wip/                        # unfinished drafts
    ├── rust-async-multithreading.md
    └── topic-queue.md
```

## Build, Test, and Development Commands

There is no build step or runtime for this repo.

- Quick sanity checks: `rg "TODO|FIXME" .` and `wc -w *.md` to keep notes focused.

## Coding Style & Naming Conventions

- Follow `styleguide.md` for the writing “story” pattern (goal → problem → solution → result) and terminology rules.
- Notes must not “leak” the prompt/session: the final text should read as standalone subject matter, without “author intent” phrasing that exists only because of the current chat (e.g., headings like “Чтобы почувствовать…” or “по просьбе…”).
- Use a single `#` title per note; use `##` for major sections; keep headings descriptive.
- Use fenced code blocks with language tags (e.g. ```sql, ```rust) and keep examples minimal but runnable.
- File names: prefer `kebab-case.md` for new notes (existing `_` names are fine).
- **ASCII diagrams — no wide Unicode arrows:** Do not use `▼`, `▲`, `►`, `◄`, `▶` — they render wider than a monospace character and break alignment. Use `v`, `^`, `>`, `<` instead.

## Testing Guidelines

No automated tests. If you add executable snippets, include a short “How to run” section near the snippet.

## Commit & Pull Request Guidelines

This folder is not currently a Git work tree, so there is no existing commit style to follow.

- If/when Git is used, prefer Conventional Commits: `docs(postgresql): explain MVCC snapshots`.
- PRs (or review requests) should include: a short summary, sources/links, and any renamed/moved files called out explicitly.

## Security & References

- Never include secrets, private endpoints, or internal credentials in notes.
- For non-obvious claims, add a short “Sources” section with links and relevant version numbers.
