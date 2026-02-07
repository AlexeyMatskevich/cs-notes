# Project Overview

## Purpose
Personal technical knowledge repository containing deep technical notes **in Russian**. Notes follow a narrative "story" pattern designed for understanding and retention, not reference lookup.

## Tech Stack
- Pure Markdown files, no build step or runtime
- Devbox for development environment (`devbox.json` present)
- Git for version control

## Structure
```
styleguide.md              # writing methodology (MUST READ before writing)
structure-guide.md         # file/folder structural patterns
network.md                 # networking notes
algorithms-and-data-structures/  # ADT, linear/non-linear structures, techniques
databases/
  distribution.md          # shared theory (replication, failover, sharding)
  postgresql/              # storage, durability, concurrency, maintenance, distribution, query-processing, indexes, schema-design
  redis/                   # architecture, atomicity, data-structures, distribution, memory, patterns, persistence
rails/
  redis/                   # Redis in Rails apps + 14 practice case studies
  sidekiq.md
system-design/             # CAP, consistency, consensus, load balancing, reliability, caching, queues, storage selection, cases
ruby/                      # collections, concurrency, GC, JIT internals
wip/                       # unfinished drafts
```

## Abstraction Layers (top to bottom)
1. **Architectural** (system-design/) — technology-agnostic patterns
2. **Shared domain theory** (databases/distribution.md) — concepts common to multiple technologies
3. **Technology-specific** (databases/postgresql/, databases/redis/) — implementation details
4. **Applied** (rails/redis/) — using technology in a concrete stack
