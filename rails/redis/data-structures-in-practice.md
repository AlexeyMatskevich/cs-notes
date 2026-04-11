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

Почти в каждом сценарии Redis закрывает не только локальную задачу структуры данных, но и системный trade-off: [[system-design/reliability-patterns#rate-limiting-ограничение-входящей-нагрузки|rate limiting]], [[system-design/caching#когерентность-локальный-vs-внешний-кэш|когерентность локального кэша]], [[system-design/message-queues#point-to-point-и-pubsub|очередь против pub/sub]], [[system-design/message-queues#acknowledgment|acknowledgment]] и [гарантии доставки](../../system-design/delivery-guarantees.md).

**Одно значение, один ключ.** [[rails/redis/practice/string-rate-limiter|Rate limiter на STRING]] — атомарный счётчик с TTL для ограничения запросов партнёров. [[rails/redis/practice/hash-checkout-cart|Корзина checkout на HASH]] — несколько полей заказа, обновляемых независимо без гонки. [[rails/redis/practice/list-capped-activity-log|Ограниченный лог активности на LIST]] — LPUSH + LTRIM для хранения последних N действий.

**Коллекции и очереди.** [[rails/redis/practice/list-background-queue|Очередь email на LIST]] — FIFO с блокирующим ожиданием через `BRPOP` (используется в [Sidekiq](../sidekiq/sidekiq.md)). [[rails/redis/practice/sorted-set-call-queue|Очередь звонков на ZSET]] — приоритеты, позиция в очереди, удаление из середины за O(log n). [[rails/redis/practice/set-permissions|Права доступа на SET]] — O(1) проверка принадлежности и серверные пересечения/объединения ролей.

**Аналитика и счётчики.** [[rails/redis/practice/hyperloglog-unique-visitors|Уникальные посетители на HyperLogLog]] — 12 КБ на счётчик вместо десятков мегабайт в SET. [[rails/redis/practice/bitmap-dau-retention|DAU и retention на Bitmap]] — 1.25 МБ на день при 10 миллионах пользователей, серверные `BITOP AND/OR`.

**Координация и гарантии.** [[rails/redis/practice/stream-payment-audit|Аудит-лог платежей на Stream]] — consumer groups для параллельной обработки несколькими сервисами с гарантией [[system-design/delivery-guarantees#at-least-once-не-менее-одного-раза|at-least-once]] (каждое сообщение доставлено хотя бы один раз). [[rails/redis/practice/multi-exec-atomic-transfer|Атомарный перевод через MULTI/EXEC]] — оптимистичная блокировка с `WATCH` и retry. [[rails/redis/practice/string-distributed-lock|Распределённая блокировка на STRING]] — SET NX EX + Lua для защиты от двойной обработки [Sidekiq](../sidekiq/sidekiq.md)-джобов. [[rails/redis/practice/string-cache-stampede|Защита от cache stampede]] — блокировка на перестроение и early expiration.

**Межпроцессная рассылка.** [[rails/redis/practice/pub-sub-cache-invalidation|Инвалидация кеша через Pub/Sub]] — рассылка всем Puma-воркерам без подтверждений и без хранения истории. [[rails/redis/practice/pub-sub-actioncable|ActionCable через Pub/Sub]] — координация WebSocket'ов между Puma-процессами через [Redis](../../databases/redis/redis.md)-подписку.

---

<- [Клиенты и соединения](clients-and-connections.md) | [Команды, блокирующие Redis](blocking-pitfalls.md) ->
