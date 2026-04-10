---
tags:
  - domain/redis
  - type/overview
aliases:
  - Redis
---

# Redis: структуры данных в памяти

**Предпосылки:** [ACID](../acid.md), базовые структуры данных ([массив](../../algorithms-and-data-structures/linear/array.md), [хеш-таблица](../../algorithms-and-data-structures/linear/hash-table.md), [связный список](../../algorithms-and-data-structures/linear/linked-list.md)), сеть (клиент/сервер, запрос/ответ).

Redis — это сервер структур данных в оперативной памяти с сетевым доступом. В отличие от реляционных СУБД, Redis не даёт ACID-гарантий и не хранит данные в таблицах. Вместо этого он предоставляет набор структур данных ([[databases/redis/data-structures/string|строки]], [[databases/redis/data-structures/hash|хеш-таблицы]], [[databases/redis/data-structures/list|списки]], [[databases/redis/data-structures/set|множества]], [[databases/redis/data-structures/sorted-set|упорядоченные множества]], [[databases/redis/data-structures/stream|потоки]]), доступных по ключу через простой протокол. Всё хранится в RAM, операции выполняются в однопоточном [[databases/redis/architecture/event-loop|event loop]] — простые команды часто укладываются в микросекунды, но реальная латентность зависит от сети, объёма данных, настроек персистентности и блокирующих команд.

## Порядок изучения

Всё начинается с архитектуры: однопоточный [[databases/redis/architecture/event-loop|event loop]] определяет, почему команды атомарны, почему одна медленная команда блокирует весь сервер и как Redis обрабатывает тысячи соединений без потоков. Без этой модели остальные темы повисают в воздухе — непонятно, откуда берётся атомарность и почему O(N)-команды опасны.

Далее — структуры данных. Каждая из них работает поверх [[databases/redis/architecture/event-loop|event loop]] и использует [[databases/redis/memory/encodings|внутренние кодировки]] (listpack, intset, skiplist), которые проще понять последовательно: [[databases/redis/data-structures/string|String]] вводит SDS и механизм кодировок, [[databases/redis/data-structures/hash|Hash]] и [[databases/redis/data-structures/list|List]] показывают listpack и пороги переключения, [[databases/redis/data-structures/set|Set]] и [[databases/redis/data-structures/sorted-set|Sorted Set]] добавляют intset и skip list, а [[databases/redis/data-structures/stream|Stream]], [[databases/redis/data-structures/hyperloglog|HyperLogLog]], [[databases/redis/data-structures/bitmap-and-bitfield|Bitmap]] и [[databases/redis/data-structures/pub-sub|Pub/Sub]] опираются на уже знакомые идеи. После структур данных естественно перейти к атомарности составных операций: [[databases/redis/atomicity/multi-exec|MULTI/EXEC]] и [[databases/redis/atomicity/lua-scripting|Lua-скрипты]] используют конкретные команды над конкретными структурами, и примеры без знания этих структур не читаются. Персистентность ([[databases/redis/persistence/rdb|RDB]] и [[databases/redis/persistence/aof|AOF]]) не зависит от структур данных и атомарности — её можно читать параллельно с ними; достаточно понимать [fork и copy-on-write](../../linux/foundations/processes.md) и [fsync](../../linux/foundations/filesystems.md).

Управление памятью требует знания всех типов данных, потому что [[databases/redis/memory/encodings|внутренние кодировки]] и пороги переключения специфичны для каждого типа, а политики [[databases/redis/memory/eviction|вытеснения]] работают на уровне ключей. Распределение ([[databases/redis/distribution/replication|репликация]], [[databases/redis/distribution/sentinel|Sentinel]], [[databases/redis/distribution/cluster|Cluster]]) опирается на персистентность — реплика получает данные через [[databases/redis/persistence/rdb|RDB]]-snapshot и [[databases/redis/persistence/aof|AOF]]-поток — и на ограничения [[databases/redis/atomicity/multi-exec|MULTI/EXEC]] в кластере. Практические паттерны идут последними: [[databases/redis/patterns/caching|кеширование]] использует [[databases/redis/memory/eviction|eviction]] и TTL, [[databases/redis/patterns/queues|очереди]] — [[databases/redis/data-structures/list|LIST]] и [[databases/redis/data-structures/stream|Stream]], [[databases/redis/patterns/distributed-locks|распределённые блокировки]] — [[databases/redis/atomicity/lua-scripting|Lua]] и SET NX EX, [[databases/redis/patterns/rate-limiting|rate limiting]] — INCR и ZRANGEBYSCORE. Без предыдущих тем эти рецепты превращаются в чёрные ящики.

### Архитектура и модель исполнения

Однопоточная модель, работа с памятью и отличия от реляционных СУБД.

- [[databases/redis/architecture/what-is-redis|Что такое Redis]] — сравнение с PostgreSQL, философия выбора хранилища, CAP
- [[databases/redis/architecture/event-loop|Event loop]] — однопоточная модель, мультиплексирование, что блокирует цикл
- [[databases/redis/architecture/pipelining|Pipelining]] — батчинг команд для снижения сетевых задержек
- [[databases/redis/architecture/logical-databases|Логические базы (SELECT)]] — db 0..N, зачем это нужно и почему в [[databases/redis/distribution/cluster|Cluster]] всегда db 0

### Структуры данных

- [[databases/redis/data-structures/string|String]] — SDS, кодировки int/embstr/raw, INCR, TTL
- [[databases/redis/data-structures/hash|Hash]] — listpack vs hashtable, пороги, HGETALL
- [[databases/redis/data-structures/list|List]] — quicklist (связный список из listpack-блоков), BRPOP
- [[databases/redis/data-structures/set|Set]] — intset vs hashtable, операции над множествами
- [[databases/redis/data-structures/sorted-set|Sorted Set]] — skip list + hashtable, ZRANGEBYSCORE
- [[databases/redis/data-structures/stream|Stream]] — consumer groups, XADD/XREADGROUP/XACK
- [[databases/redis/data-structures/hyperloglog|HyperLogLog]] — вероятностный подсчёт уникальных, PFADD/PFCOUNT
- [[databases/redis/data-structures/bitmap-and-bitfield|Bitmap и Bitfield]] — SETBIT/BITCOUNT, BITFIELD, трекинг DAU
- [[databases/redis/data-structures/pub-sub|Pub/Sub]] — fire-and-forget, SUBSCRIBE/PUBLISH, sharded pub/sub

### Атомарность

- [[databases/redis/atomicity/single-command|Одна команда]] — почему отдельная команда всегда атомарна
- [[databases/redis/atomicity/multi-exec|MULTI/EXEC]] — транзакции, WATCH/MULTI/EXEC, отсутствие rollback
- [[databases/redis/atomicity/lua-scripting|Lua-скрипты]] — EVAL, KEYS[]/ARGV[], Redis Functions 7.0+

### Персистентность

- [[databases/redis/persistence/rdb|RDB]] — BGSAVE, fork + copy-on-write, компактный snapshot
- [[databases/redis/persistence/aof|AOF]] — fsync-политики, rewrite, гибрид RDB + AOF

### Управление памятью

- [[databases/redis/memory/encodings|Внутренние кодировки]] — redisObject (16 байт), listpack, пороги переключения
- [[databases/redis/memory/eviction|Eviction]] — maxmemory, 8 политик, приближённые LRU/LFU
- [[databases/redis/memory/key-design|Проектирование ключей]] — именование ключей, KEYS и SCAN, UNLINK

### Распределение и отказоустойчивость

- [Репликация](../../system-design/replication.md) и [шардинг](../../system-design/sharding.md) — общие понятия (failover, кворум, shard key)
- [[databases/redis/distribution/overview|Распределение Redis]] — что решают [[databases/redis/distribution/replication|репликация]], [[databases/redis/distribution/sentinel|Sentinel]] и [[databases/redis/distribution/cluster|Cluster]]
- [Репликация](./distribution/replication.md) — master-replica, replication backlog, WAIT
- [[databases/redis/distribution/sentinel|Sentinel]] — автоматический failover, кворум
- [[databases/redis/distribution/cluster|Cluster]] — 16 384 слота, hash tags, MOVED/ASK

### Практические паттерны

- [[databases/redis/patterns/caching|Кеширование]] — cache-aside, stampede, early expiration (см. также [архитектура кэширования](../../system-design/caching.md))
- [[databases/redis/patterns/rate-limiting|Rate limiting]] — fixed window, sliding window, token bucket
- [[databases/redis/patterns/distributed-locks|Распределённые блокировки]] — SET NX EX, Lua unlock, Redlock, fencing tokens
- [[databases/redis/patterns/queues|Очереди]] — [[databases/redis/data-structures/list|LIST]]-очередь, reliable queue, delayed queue ([[databases/redis/data-structures/sorted-set|Sorted Set]]), [[databases/redis/data-structures/stream|Streams]]

## Как всё связано

Redis — система компромиссов, но с другими приоритетами, чем у реляционных СУБД.

**Speed vs Durability:** Данные в RAM — операции за микросекунды. Цена — при падении без персистентности данные теряются. [[databases/redis/persistence/rdb|RDB]] и [[databases/redis/persistence/aof|AOF]] смягчают проблему, но не дают ACID-гарантий.

**Simplicity vs Functionality:** Однопоточная модель исключает гонки и deadlock'и. Цена — медленная команда блокирует весь сервер, нет JOIN'ов и сложных запросов.

**Memory vs Capacity:** Всё в RAM — быстрый доступ. Цена — объём данных ограничен оперативной памятью, нужны политики [[databases/redis/memory/eviction|вытеснения]].

**Atomicity vs Flexibility:** Одна команда атомарна бесплатно. Для составных операций — [[databases/redis/atomicity/multi-exec|MULTI/EXEC]] (без условий) или [[databases/redis/atomicity/lua-scripting|Lua-скрипты]] (с условиями, но блокируют [[databases/redis/architecture/event-loop|event loop]]).

## См. также

- [Redis в Rails-приложении](../../rails/redis/redis-in-rails.md) — клиенты, connection_pool, паттерны использования из Ruby/Rails

## Sources

- Redis Documentation. <https://redis.io/docs/>
- «Redis in Action» — Josiah Carlson, Manning, 2013
- Redis source code. <https://github.com/redis/redis>
