---
tags:
  - domain/rails
  - theme/caching
  - theme/performance
  - type/overview
aliases:
  - Redis in Rails
order: 0
---

# Redis в Rails-приложении

**Предпосылки:** [Redis как сервер структур данных](../../databases/redis/redis.md) (архитектура, структуры данных, персистентность, eviction), [конкурентность в Ruby](../../ruby/ruby-concurrency.md) ([GVL](../../ruby/ruby-concurrency.md#gvl-почему-потоки-не-ускоряют-cpu-код), потоки, I/O-конкурентность), [Puma](../../ruby/ruby-concurrency.md#puma-reactor--thread-pool) (воркеры + потоки).

Rails-приложение на Puma — это несколько процессов, в каждом несколько потоков. Процессы изолированы: у них нет общей памяти. Redis становится общим хранилищем состояния, доступным всем процессам по сети: кеш, сессии, счётчики, координация WebSocket'ов, фоновые задачи.

Серия читается в два прохода. Сначала — как Rails вообще разговаривает с Redis: короткие обращения из веб-запроса через пул соединений и отдельные долгоживущие соединения для подписчиков, блокирующих очередей и фоновых воркеров. Потом — выбор структуры данных под конкретную операцию: одно значение, частичное обновление объекта, очередь, приоритет, рассылка всем процессам, журнал событий.

За этими рецептами стоят общие концепции из system design: [когерентность кэша](../../system-design/caching.md#когерентность-локальный-vs-внешний-кэш), [cache stampede](../../system-design/caching.md#cache-stampede), [temporal decoupling](../../system-design/message-queues.md#temporal-decoupling-развязка-во-времени), [point-to-point и Pub/Sub](../../system-design/message-queues.md#point-to-point-и-pubsub), [гарантии доставки](../../system-design/delivery-guarantees.md) и [idempotency](../../system-design/reliability-patterns.md#idempotency-безопасность-повторных-запросов).

## Содержание

[Клиенты и соединения](clients-and-connections.md) — redis-rb, hiredis-client, connection_pool, конфигурация нескольких инстансов [Redis](../../databases/redis/redis.md) под разные задачи.

[Структуры данных на практике](data-structures-in-practice.md) — карта выбора: STRING, HASH, LIST, SET, ZSET, Stream, Bitmap, HyperLogLog и Pub/Sub на конкретных Rails-сценариях из `practice/`.

[Команды, блокирующие Redis](blocking-pitfalls.md) — какие команды блокируют [event loop](../../databases/redis/architecture/event-loop.md) и как этого избежать в Rails-коде.

## Связанные заметки

- [Sidekiq](../sidekiq/sidekiq.md) — [фоновые задачи](../sidekiq/architecture.md) через Redis LIST + BRPOP
- [Кэширование](../../system-design/caching.md) — когерентность, инвалидация, stampede
- [Очереди сообщений](../../system-design/message-queues.md) — acknowledgment, point-to-point vs pub/sub, лог vs очередь
- [Гарантии доставки](../../system-design/delivery-guarantees.md) — at-most-once, at-least-once, exactly-once
- [Паттерны надёжности](../../system-design/reliability-patterns.md) — retry, backoff, idempotency, bulkhead
