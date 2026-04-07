# Sidekiq: фоновые задачи в Rails

**Предпосылки:** Ruby, Rails, базовое понимание Redis ([что такое Redis](../../databases/redis/index.md)).

Sidekiq — фреймворк для обработки фоновых задач в Rails-приложениях. Он объединяет знакомые паттерны — очереди на Redis LIST, retry с backoff, graceful shutdown через сигналы — в одну систему с конкретными trade-offs на каждом стыке.

Серия начинается с архитектуры (из чего состоит), проходит через жизненный цикл задачи, гарантии доставки, обработку ошибок, deploy, дизайн задач и масштабирование, заканчивая тестированием.

## Порядок изучения

- [Архитектура](00-architecture.md) — три роли (client/broker/server), данные в Redis, устройство серверного процесса
- [Жизненный цикл задачи](01-job-lifecycle.md) — путь от `perform_async` до `perform`, JSON-сериализация, middleware
- [Гарантии и идемпотентность](02-guarantees.md) — три точки потери, BasicFetch vs SuperFetch, Transactional Push
- [Retry и обработка ошибок](03-retry-and-errors.md) — формула retry, sorted sets, Dead Letter Queue
- [Сигналы и deploy](04-signals-and-deploy.md) — TSTP/TERM, deploy sequence, IterableJob
- [Дизайн задач](05-job-design.md) — атомарность, fan-out, Batches, command vs event
- [Concurrency и масштабирование](06-concurrency-and-scaling.md) — потоки + GVL, процессы, приоритеты, Capsules
- [Тестирование и практики](07-testing.md) — fake/inline/disable, ActiveJob vs Sidekiq::Job

## Как всё связано

**OSS vs Pro.** OSS Sidekiq использует `BRPOP` (простая очередь) — при crash задача потеряна. Pro добавляет `SuperFetch` (private queues + orphan recovery), `reliable_push`, `reliable_scheduler`. Каждый механизм — отдельный opt-in. Без явного включения Pro поведение остаётся OSS.

**Threads vs Processes.** Потоки дают I/O overlap благодаря GVL, но не ускоряют CPU-bound работу. Процессы дают настоящий CPU-параллелизм, но потребляют больше памяти. Типичная конфигурация: несколько процессов с 5–25 потоками каждый.

**ActiveJob vs Sidekiq::Job.** ActiveJob = абстракция + переносимость между backend'ами, ~30% overhead. Sidekiq::Job = прямой доступ + Pro-фичи + контроль retry. Для приложений без смены backend — Sidekiq::Job практичнее.

## Sources

- [Sidekiq Wiki](https://github.com/sidekiq/sidekiq/wiki)
- Mike Perham, [How does Sidekiq work?](https://www.mikeperham.com/how-sidekiq-works/)
- [Sidekiq Redis Data Model](https://hype08.github.io/gradual-notes/thoughts/Sidekiq-Redis-Data-Model)
