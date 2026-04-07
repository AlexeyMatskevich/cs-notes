# Структуры данных Redis на практике

**Предпосылки:** [Клиенты и соединения](00-clients-and-connections.md), [STRING](../../databases/redis/data-structures/00-string.md), [HASH](../../databases/redis/data-structures/01-hash.md), [LIST](../../databases/redis/data-structures/02-list.md), [SET](../../databases/redis/data-structures/03-set.md), [ZSET](../../databases/redis/data-structures/04-sorted-set.md), [Stream](../../databases/redis/data-structures/05-stream.md), [HyperLogLog](../../databases/redis/data-structures/06-hyperloglog.md), [Bitmap](../../databases/redis/data-structures/07-bitmap-and-bitfield.md), [Pub/Sub](../../databases/redis/data-structures/08-pub-sub.md), [MULTI/EXEC](../../databases/redis/atomicity/01-multi-exec.md).

<- [Клиенты и соединения](00-clients-and-connections.md) | [Команды, блокирующие Redis](02-blocking-pitfalls.md) ->

Каждая структура Redis решает задачу, которую другие структуры решают плохо или не решают вообще. Ниже — конкретные бизнес-сценарии из Rails-приложений, сгруппированные от простых операций с одним ключом к координации между процессами.

**Одно значение, один ключ.** [Rate limiter на STRING](practice/string-rate-limiter.md) — атомарный счётчик с TTL для ограничения запросов партнёров. [Корзина checkout на HASH](practice/hash-checkout-cart.md) — несколько полей заказа, обновляемых независимо без гонки. [Ограниченный лог активности на LIST](practice/list-capped-activity-log.md) — LPUSH + LTRIM для хранения последних N действий.

**Коллекции и очереди.** [Очередь email на LIST](practice/list-background-queue.md) — FIFO с блокирующим ожиданием через `BRPOP`. [Очередь звонков на ZSET](practice/sorted-set-call-queue.md) — приоритеты, позиция в очереди, удаление из середины за O(log n). [Права доступа на SET](practice/set-permissions.md) — O(1) проверка принадлежности и серверные пересечения/объединения ролей.

**Аналитика и счётчики.** [Уникальные посетители на HyperLogLog](practice/hyperloglog-unique-visitors.md) — 12 КБ на счётчик вместо десятков мегабайт в SET. [DAU и retention на Bitmap](practice/bitmap-dau-retention.md) — 1.25 МБ на день при 10 миллионах пользователей, серверные `BITOP AND/OR`.

**Координация и гарантии.** [Аудит-лог платежей на Stream](practice/stream-payment-audit.md) — consumer groups для параллельной обработки несколькими сервисами с гарантией [at-least-once](../../system-design/08-delivery-guarantees.md#at-least-once-не-менее-одного-раза) (каждое сообщение доставлено хотя бы один раз). [Атомарный перевод через MULTI/EXEC](practice/multi-exec-atomic-transfer.md) — оптимистичная блокировка с `WATCH` и retry. [Распределённая блокировка на STRING](practice/string-distributed-lock.md) — SET NX EX + Lua для защиты от двойной обработки Sidekiq-джобов. [Защита от cache stampede](practice/string-cache-stampede.md) — блокировка на перестроение и early expiration.

**Межпроцессная рассылка.** [Инвалидация кеша через Pub/Sub](practice/pub-sub-cache-invalidation.md) — fire-and-forget рассылка всем Puma-воркерам. [ActionCable через Pub/Sub](practice/pub-sub-actioncable.md) — координация WebSocket'ов между Puma-процессами через Redis-подписку.

---

<- [Клиенты и соединения](00-clients-and-connections.md) | [Команды, блокирующие Redis](02-blocking-pitfalls.md) ->
