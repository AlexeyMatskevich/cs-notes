---
tags:
  - domain/rails
  - theme/queues
  - theme/reliability
  - type/overview
aliases:
  - Sidekiq
order: 0
---

# Sidekiq: фоновые задачи в Rails

**Предпосылки:** Ruby, Rails, базовое понимание Redis ([что такое Redis](../../databases/redis/redis.md)).

Sidekiq — фреймворк для обработки фоновых задач в Rails-приложениях. Он объединяет знакомые паттерны — очереди на Redis LIST, [retry](retry-and-errors.md) с backoff, graceful shutdown через [сигналы](../../linux/programming/signals.md) — в одну систему с конкретными trade-offs на каждом стыке.

Серия начинается с [архитектуры](architecture.md) (из чего состоит), проходит через [жизненный цикл задачи](job-lifecycle.md), [гарантии доставки](guarantees.md), обработку ошибок, [deploy](signals-and-deploy.md), [дизайн задач](job-design.md) и [масштабирование](concurrency-and-scaling.md), заканчивая [тестированием](testing.md).

## Порядок изучения

- [Архитектура](architecture.md) — три роли (client/broker/server), данные в Redis, устройство серверного процесса
- [Жизненный цикл задачи](job-lifecycle.md) — путь от `perform_async` до `perform`, JSON-сериализация, middleware
- [Гарантии и идемпотентность](guarantees.md) — три точки потери, BasicFetch vs SuperFetch, Transactional Push
- [Retry и обработка ошибок](retry-and-errors.md) — формула retry, sorted sets, Dead Letter Queue
- [Сигналы и deploy](signals-and-deploy.md) — TSTP/TERM, deploy sequence, IterableJob
- [Дизайн задач](job-design.md) — атомарность, fan-out, Batches, command vs event
- [Concurrency и масштабирование](concurrency-and-scaling.md) — потоки + GVL, процессы, приоритеты, Capsules
- [Тестирование и практики](testing.md) — fake/inline/disable, ActiveJob vs Sidekiq::Job

## Как всё связано

**OSS vs Pro.** OSS Sidekiq использует `BRPOP` (простая очередь) — при crash задача потеряна. Pro добавляет `SuperFetch` (private queues + orphan recovery), `reliable_push`, `reliable_scheduler`. Каждый механизм — отдельный opt-in. Без явного включения Pro поведение остаётся OSS.

**Threads vs Processes.** Потоки дают I/O overlap благодаря GVL, но не ускоряют CPU-bound работу. Процессы дают настоящий CPU-параллелизм, но потребляют больше памяти. Типичная конфигурация: несколько процессов с 5–25 потоками каждый.

**ActiveJob vs Sidekiq::Job.** ActiveJob = абстракция + переносимость между backend'ами, ~30% overhead. Sidekiq::Job = прямой доступ + Pro-фичи + контроль retry. Для приложений без смены backend — Sidekiq::Job практичнее.

## Sources

- [Sidekiq Wiki](https://github.com/sidekiq/sidekiq/wiki)
- Mike Perham, [How does Sidekiq work?](https://www.mikeperham.com/how-sidekiq-works/)
- [Sidekiq Redis Data Model](https://hype08.github.io/gradual-notes/thoughts/Sidekiq-Redis-Data-Model)
