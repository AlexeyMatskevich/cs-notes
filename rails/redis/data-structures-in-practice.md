---
tags:
  - domain/rails
  - theme/caching
  - type/concept
aliases:
  - Redis data structures
order: 1
---

# Структуры данных Redis на практике

**Предпосылки:** [Клиенты и соединения](clients-and-connections.md), [STRING](../../databases/redis/data-structures/string.md), [HASH](../../databases/redis/data-structures/hash.md), [LIST](../../databases/redis/data-structures/list.md), [SET](../../databases/redis/data-structures/set.md), [ZSET](../../databases/redis/data-structures/sorted-set.md), [Stream](../../databases/redis/data-structures/stream.md), [HyperLogLog](../../databases/redis/data-structures/hyperloglog.md), [Bitmap](../../databases/redis/data-structures/bitmap-and-bitfield.md), [Pub/Sub](../../databases/redis/data-structures/pub-sub.md), [MULTI/EXEC](../../databases/redis/atomicity/multi-exec.md).

<- [Клиенты и соединения](clients-and-connections.md) | [Команды, блокирующие Redis](blocking-pitfalls.md) ->

Структуру Redis выбирают не по сходству с предметной областью, а по минимальному набору операций, который нужен приложению. Нужен TTL и атомарный счётчик — STRING. Нужны частичные обновления одного объекта — HASH. Нужны порядок и блокирующее ожидание — LIST. Нужны приоритеты и ранги — ZSET. Нужна рассылка всем процессам — Pub/Sub. Нужны история и подтверждение обработки — Stream.

Ниже — конкретные Rails-сценарии, сгруппированные от простых операций с одним ключом к координации между процессами.

Почти в каждом сценарии Redis закрывает не только локальную задачу структуры данных, но и системный trade-off: [rate limiting](../../system-design/reliability-patterns.md#rate-limiting-ограничение-входящей-нагрузки), [когерентность локального кэша](../../system-design/caching.md#когерентность-локальный-vs-внешний-кэш), [очередь против pub/sub](../../system-design/message-queues.md#point-to-point-и-pubsub), [acknowledgment](../../system-design/message-queues.md#acknowledgment) и [гарантии доставки](../../system-design/delivery-guarantees.md).

**Одно значение, один ключ.** [Rate limiter на STRING](practice/string-rate-limiter.md) — атомарный счётчик с TTL для ограничения запросов партнёров. [Корзина checkout на HASH](practice/hash-checkout-cart.md) — несколько полей заказа, обновляемых независимо без гонки. [Ограниченный лог активности на LIST](practice/list-capped-activity-log.md) — LPUSH + LTRIM для хранения последних N действий.

**Коллекции и очереди.** [Очередь email на LIST](practice/list-background-queue.md) — FIFO с блокирующим ожиданием через `BRPOP`. [Очередь звонков на ZSET](practice/sorted-set-call-queue.md) — приоритеты, позиция в очереди, удаление из середины за O(log n). [Права доступа на SET](practice/set-permissions.md) — O(1) проверка принадлежности и серверные пересечения/объединения ролей.

**Аналитика и счётчики.** [Уникальные посетители на HyperLogLog](practice/hyperloglog-unique-visitors.md) — 12 КБ на счётчик вместо десятков мегабайт в SET. [DAU и retention на Bitmap](practice/bitmap-dau-retention.md) — 1.25 МБ на день при 10 миллионах пользователей, серверные `BITOP AND/OR`.

**Координация и гарантии.** [Аудит-лог платежей на Stream](practice/stream-payment-audit.md) — consumer groups для параллельной обработки несколькими сервисами с гарантией [at-least-once](../../system-design/delivery-guarantees.md#at-least-once-не-менее-одного-раза) (каждое сообщение доставлено хотя бы один раз). [Атомарный перевод через MULTI/EXEC](practice/multi-exec-atomic-transfer.md) — оптимистичная блокировка с `WATCH` и retry. [Распределённая блокировка на STRING](practice/string-distributed-lock.md) — SET NX EX + Lua для защиты от двойной обработки Sidekiq-джобов. [Защита от cache stampede](practice/string-cache-stampede.md) — блокировка на перестроение и early expiration.

**Межпроцессная рассылка.** [Инвалидация кеша через Pub/Sub](practice/pub-sub-cache-invalidation.md) — рассылка всем Puma-воркерам без подтверждений и без хранения истории. [ActionCable через Pub/Sub](practice/pub-sub-actioncable.md) — координация WebSocket'ов между Puma-процессами через Redis-подписку.

---

<- [Клиенты и соединения](clients-and-connections.md) | [Команды, блокирующие Redis](blocking-pitfalls.md) ->
