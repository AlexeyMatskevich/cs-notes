---
tags:
  - domain/redis
  - type/overview
aliases:
  - Redis
---

# Redis: структуры данных в памяти

**Предпосылки:** [ACID](../acid.md), базовые структуры данных ([массив](../../algorithms-and-data-structures/linear/array.md), [хеш-таблица](../../algorithms-and-data-structures/linear/hash-table.md), [связный список](../../algorithms-and-data-structures/linear/linked-list.md)), сеть (клиент/сервер, запрос/ответ).

Redis — это сервер структур данных в оперативной памяти с сетевым доступом. В отличие от реляционных СУБД, Redis не даёт ACID-гарантий и не хранит данные в таблицах. Вместо этого он предоставляет набор структур данных ([строки](data-structures/string.md), [хеш-таблицы](data-structures/hash.md), [списки](data-structures/list.md), [множества](data-structures/set.md), [упорядоченные множества](data-structures/sorted-set.md), [потоки](data-structures/stream.md)), доступных по ключу через простой протокол. Всё хранится в RAM, операции выполняются в однопоточном [event loop](architecture/event-loop.md) — простые команды часто укладываются в микросекунды, но реальная латентность зависит от сети, объёма данных, настроек персистентности и блокирующих команд.

## Порядок изучения

Всё начинается с архитектуры: однопоточный [event loop](architecture/event-loop.md) определяет, почему команды атомарны, почему одна медленная команда блокирует весь сервер и как Redis обрабатывает тысячи соединений без потоков. Без этой модели остальные темы повисают в воздухе — непонятно, откуда берётся атомарность и почему O(N)-команды опасны.

Далее — структуры данных. Каждая из них работает поверх [event loop](architecture/event-loop.md) и использует [внутренние кодировки](memory/encodings.md) (listpack, intset, skiplist), которые проще понять последовательно: [String](data-structures/string.md) вводит SDS и механизм кодировок, [Hash](data-structures/hash.md) и [List](data-structures/list.md) показывают listpack и пороги переключения, [Set](data-structures/set.md) и [Sorted Set](data-structures/sorted-set.md) добавляют intset и skip list, а [Stream](data-structures/stream.md), [HyperLogLog](data-structures/hyperloglog.md), [Bitmap](data-structures/bitmap-and-bitfield.md) и [Pub/Sub](data-structures/pub-sub.md) опираются на уже знакомые идеи. После структур данных естественно перейти к атомарности составных операций: [MULTI/EXEC](atomicity/multi-exec.md) и [Lua-скрипты](atomicity/lua-scripting.md) используют конкретные команды над конкретными структурами, и примеры без знания этих структур не читаются. Персистентность ([RDB](persistence/rdb.md) и [AOF](persistence/aof.md)) не зависит от структур данных и атомарности — её можно читать параллельно с ними; достаточно понимать [fork и copy-on-write](../../linux/foundations/processes.md) и [fsync](../../linux/foundations/filesystems.md).

Управление памятью требует знания всех типов данных, потому что [внутренние кодировки](memory/encodings.md) и пороги переключения специфичны для каждого типа, а политики [вытеснения](memory/eviction.md) работают на уровне ключей. Распределение ([репликация](distribution/replication.md), [Sentinel](distribution/sentinel.md), [Cluster](distribution/cluster.md)) опирается на персистентность — реплика получает данные через [RDB](persistence/rdb.md)-snapshot и [AOF](persistence/aof.md)-поток — и на ограничения [MULTI/EXEC](atomicity/multi-exec.md) в кластере. Практические паттерны идут последними: [кеширование](patterns/caching.md) использует [eviction](memory/eviction.md) и TTL, [очереди](patterns/queues.md) — [LIST](data-structures/list.md) и [Stream](data-structures/stream.md), [распределённые блокировки](patterns/distributed-locks.md) — [Lua](atomicity/lua-scripting.md) и SET NX EX, [rate limiting](patterns/rate-limiting.md) — INCR и ZRANGEBYSCORE. Без предыдущих тем эти рецепты превращаются в чёрные ящики.

### Архитектура и модель исполнения

Однопоточная модель, работа с памятью и отличия от реляционных СУБД.

- [Что такое Redis](architecture/what-is-redis.md) — сравнение с PostgreSQL, философия выбора хранилища, CAP
- [Event loop](architecture/event-loop.md) — однопоточная модель, мультиплексирование, что блокирует цикл
- [Pipelining](architecture/pipelining.md) — батчинг команд для снижения сетевых задержек
- [Логические базы (SELECT)](architecture/logical-databases.md) — db 0..N, зачем это нужно и почему в [Cluster](distribution/cluster.md) всегда db 0

### Структуры данных

- [String](data-structures/string.md) — SDS, кодировки int/embstr/raw, INCR, TTL
- [Hash](data-structures/hash.md) — listpack vs hashtable, пороги, HGETALL
- [List](data-structures/list.md) — quicklist (связный список из listpack-блоков), BRPOP
- [Set](data-structures/set.md) — intset vs hashtable, операции над множествами
- [Sorted Set](data-structures/sorted-set.md) — skip list + hashtable, ZRANGEBYSCORE
- [Stream](data-structures/stream.md) — consumer groups, XADD/XREADGROUP/XACK
- [HyperLogLog](data-structures/hyperloglog.md) — вероятностный подсчёт уникальных, PFADD/PFCOUNT
- [Bitmap и Bitfield](data-structures/bitmap-and-bitfield.md) — SETBIT/BITCOUNT, BITFIELD, трекинг DAU
- [Pub/Sub](data-structures/pub-sub.md) — fire-and-forget, SUBSCRIBE/PUBLISH, sharded pub/sub

### Атомарность

- [Одна команда](atomicity/single-command.md) — почему отдельная команда всегда атомарна
- [MULTI/EXEC](atomicity/multi-exec.md) — транзакции, WATCH/MULTI/EXEC, отсутствие rollback
- [Lua-скрипты](atomicity/lua-scripting.md) — EVAL, KEYS[]/ARGV[], Redis Functions 7.0+

### Персистентность

- [RDB](persistence/rdb.md) — BGSAVE, fork + copy-on-write, компактный snapshot
- [AOF](persistence/aof.md) — fsync-политики, rewrite, гибрид RDB + AOF

### Управление памятью

- [Внутренние кодировки](memory/encodings.md) — redisObject (16 байт), listpack, пороги переключения
- [Eviction](memory/eviction.md) — maxmemory, 8 политик, приближённые LRU/LFU
- [Проектирование ключей](memory/key-design.md) — именование ключей, KEYS и SCAN, UNLINK

### Распределение и отказоустойчивость

- [Репликация](../../system-design/replication.md) и [шардинг](../../system-design/sharding.md) — общие понятия (failover, кворум, shard key)
- [Распределение Redis](distribution/overview.md) — что решают [репликация](distribution/replication.md), [Sentinel](distribution/sentinel.md) и [Cluster](distribution/cluster.md)
- [Репликация](./distribution/replication.md) — master-replica, replication backlog, WAIT
- [Sentinel](distribution/sentinel.md) — автоматический failover, кворум
- [Cluster](distribution/cluster.md) — 16 384 слота, hash tags, MOVED/ASK

### Практические паттерны

- [Кеширование](patterns/caching.md) — cache-aside, stampede, early expiration (см. также [архитектура кэширования](../../system-design/caching.md))
- [Rate limiting](patterns/rate-limiting.md) — fixed window, sliding window, token bucket
- [Распределённые блокировки](patterns/distributed-locks.md) — SET NX EX, Lua unlock, Redlock, fencing tokens
- [Очереди](patterns/queues.md) — [LIST](data-structures/list.md)-очередь, reliable queue, delayed queue ([Sorted Set](data-structures/sorted-set.md)), [Streams](data-structures/stream.md)

## Как всё связано

Redis — система компромиссов, но с другими приоритетами, чем у реляционных СУБД.

**Speed vs Durability:** Данные в RAM — операции за микросекунды. Цена — при падении без персистентности данные теряются. [RDB](persistence/rdb.md) и [AOF](persistence/aof.md) смягчают проблему, но не дают ACID-гарантий.

**Simplicity vs Functionality:** Однопоточная модель исключает гонки и deadlock'и. Цена — медленная команда блокирует весь сервер, нет JOIN'ов и сложных запросов.

**Memory vs Capacity:** Всё в RAM — быстрый доступ. Цена — объём данных ограничен оперативной памятью, нужны политики [вытеснения](memory/eviction.md).

**Atomicity vs Flexibility:** Одна команда атомарна бесплатно. Для составных операций — [MULTI/EXEC](atomicity/multi-exec.md) (без условий) или [Lua-скрипты](atomicity/lua-scripting.md) (с условиями, но блокируют [event loop](architecture/event-loop.md)).

## См. также

- [Redis в Rails-приложении](../../rails/redis/redis-in-rails.md) — клиенты, connection_pool, паттерны использования из Ruby/Rails

## Sources

- Redis Documentation. <https://redis.io/docs/>
- «Redis in Action» — Josiah Carlson, Manning, 2013
- Redis source code. <https://github.com/redis/redis>
