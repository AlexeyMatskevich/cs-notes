# Redis в Rails-приложении

**Предпосылки:** [Redis как сервер структур данных](../../databases/redis/index.md) (архитектура, структуры данных, персистентность, eviction), [конкурентность в Ruby](../../ruby/ruby-concurrency.md) ([GVL](../../ruby/ruby-concurrency.md#gvl-почему-потоки-не-ускоряют-cpu-код), потоки, I/O-конкурентность), [Puma](../../ruby/ruby-concurrency.md#puma-reactor--thread-pool) (воркеры + потоки).

Rails-приложение на Puma — это несколько процессов, в каждом несколько потоков. Процессы изолированы: у них нет общей памяти. Redis становится общим хранилищем состояния, доступным всем процессам по сети: кеш, сессии, счётчики, координация WebSocket'ов, фоновые задачи.

Две основные темы: как Rails-приложение подключается к Redis и управляет соединениями, и какие задачи Rails решает с помощью Redis-команд.

## Содержание

[Клиенты и соединения](00-clients-and-connections.md) — redis-rb, hiredis-client, connection_pool, конфигурация нескольких инстансов Redis под разные задачи.

[Структуры данных на практике](01-data-structures-in-practice.md) — rate limiter, корзина checkout, очереди, права доступа, аудит-лог, DAU/retention, ActionCable, блокировки, cache stampede, capped lists и другие сценарии в `practice/`.

[Команды, блокирующие Redis](02-blocking-pitfalls.md) — какие команды блокируют event loop и как этого избежать в Rails-коде.

## Связанные заметки

- [Sidekiq](../sidekiq/index.md) — фоновые задачи через Redis LIST + BRPOP
