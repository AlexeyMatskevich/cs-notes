# Redis в Rails-приложении

**Предпосылки:** [Redis как сервер структур данных](../../databases/redis/index.md) (архитектура, структуры данных, персистентность, eviction), [конкурентность в Ruby](../../ruby/ruby-concurrency.md) ([GVL](../../ruby/ruby-concurrency.md#gvl-почему-потоки-не-ускоряют-cpu-код), потоки, I/O-конкурентность), [Puma](../../ruby/ruby-concurrency.md#puma-reactor--thread-pool) (воркеры + потоки).

Rails-приложение на Puma — это несколько процессов, в каждом несколько потоков. Процессы изолированы: у них нет общей памяти. Redis становится общим хранилищем состояния, доступным всем процессам по сети: кеш, сессии, счётчики, координация WebSocket'ов, фоновые задачи.

Серия читается в два прохода. Сначала — как Rails вообще разговаривает с Redis: короткие обращения из веб-запроса через пул соединений и отдельные долгоживущие соединения для подписчиков, блокирующих очередей и фоновых воркеров. Потом — выбор структуры данных под конкретную операцию: одно значение, частичное обновление объекта, очередь, приоритет, рассылка всем процессам, журнал событий.

За этими рецептами стоят общие концепции из system design: [когерентность кэша](../../system-design/07-caching.md#когерентность-локальный-vs-внешний-кэш), [cache stampede](../../system-design/07-caching.md#cache-stampede), [temporal decoupling](../../system-design/09-message-queues.md#temporal-decoupling-развязка-во-времени), [point-to-point и Pub/Sub](../../system-design/09-message-queues.md#point-to-point-и-pubsub), [гарантии доставки](../../system-design/08-delivery-guarantees.md) и [idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов).

## Содержание

[Клиенты и соединения](00-clients-and-connections.md) — redis-rb, hiredis-client, connection_pool, конфигурация нескольких инстансов Redis под разные задачи.

[Структуры данных на практике](01-data-structures-in-practice.md) — карта выбора: STRING, HASH, LIST, SET, ZSET, Stream, Bitmap, HyperLogLog и Pub/Sub на конкретных Rails-сценариях из `practice/`.

[Команды, блокирующие Redis](02-blocking-pitfalls.md) — какие команды блокируют event loop и как этого избежать в Rails-коде.

## Связанные заметки

- [Sidekiq](../sidekiq/index.md) — фоновые задачи через Redis LIST + BRPOP
- [Кэширование](../../system-design/07-caching.md) — когерентность, инвалидация, stampede
- [Очереди сообщений](../../system-design/09-message-queues.md) — acknowledgment, point-to-point vs pub/sub, лог vs очередь
- [Гарантии доставки](../../system-design/08-delivery-guarantees.md) — at-most-once, at-least-once, exactly-once
- [Паттерны надёжности](../../system-design/06-reliability-patterns.md) — retry, backoff, idempotency, bulkhead
