# Redis: структуры данных в памяти

**Предпосылки:** [ACID](../postgresql/storage/00-acid.md), базовые структуры данных ([массив](../../algorithms-and-data-structures/linear/01-array.md), [хеш-таблица](../../algorithms-and-data-structures/linear/05-hash-table.md), [связный список](../../algorithms-and-data-structures/linear/03-linked-list.md)), сеть (клиент/сервер, запрос/ответ).

Redis — это сервер структур данных в оперативной памяти с сетевым доступом. В отличие от реляционных СУБД, Redis не даёт ACID-гарантий и не хранит данные в таблицах. Вместо этого он предоставляет набор структур данных (строки, хеш-таблицы, списки, множества, упорядоченные множества, потоки), доступных по ключу через простой протокол. Всё хранится в RAM, операции выполняются в однопоточном event loop — простые команды часто укладываются в микросекунды, но реальная латентность зависит от сети, объёма данных, настроек персистентности и блокирующих команд.

## Порядок изучения

Заметки сгруппированы по зависимостям: от архитектуры и модели исполнения к структурам данных, атомарности, персистентности, управлению памятью, распределённым конфигурациям и практическим паттернам.

### Архитектура и модель исполнения

Фундамент: почему Redis быстрый и чем он отличается от реляционных СУБД.

- [Что такое Redis](architecture/00-what-is-redis.md) — сравнение с PostgreSQL, философия выбора хранилища, CAP
- [Event loop](architecture/01-event-loop.md) — однопоточная модель, epoll, что блокирует цикл
- [Pipelining](architecture/02-pipelining.md) — батчинг команд, снижение накладных расходов на RTT

### Структуры данных

- [String](data-structures/00-string.md) — SDS, кодировки int/embstr/raw, INCR, TTL
- [Hash](data-structures/01-hash.md) — listpack vs hashtable, пороги, HGETALL
- [List](data-structures/02-list.md) — quicklist (связный список из listpack-блоков), BRPOP
- [Set](data-structures/03-set.md) — intset vs hashtable, операции над множествами
- [Sorted Set](data-structures/04-sorted-set.md) — skip list + hashtable, ZRANGEBYSCORE
- [Stream](data-structures/05-stream.md) — consumer groups, XADD/XREADGROUP/XACK
- [HyperLogLog](data-structures/06-hyperloglog.md) — вероятностный подсчёт уникальных, PFADD/PFCOUNT
- [Bitmap и Bitfield](data-structures/07-bitmap-and-bitfield.md) — SETBIT/BITCOUNT, BITFIELD, трекинг DAU
- [Pub/Sub](data-structures/08-pub-sub.md) — fire-and-forget, SUBSCRIBE/PUBLISH, sharded pub/sub

### Атомарность

- [Одна команда](atomicity/00-single-command.md) — почему отдельная команда всегда атомарна
- [MULTI/EXEC](atomicity/01-multi-exec.md) — транзакции, WATCH/MULTI/EXEC, отсутствие rollback
- [Lua-скрипты](atomicity/02-lua-scripting.md) — EVAL, KEYS[]/ARGV[], Redis Functions 7.0+

### Персистентность

- [RDB](persistence/00-rdb.md) — BGSAVE, fork + CoW, компактный snapshot
- [AOF](persistence/01-aof.md) — fsync-политики, rewrite, гибрид RDB + AOF

### Управление памятью

- [Внутренние кодировки](memory/00-encodings.md) — redisObject (16 байт), listpack, пороги переключения
- [Eviction](memory/01-eviction.md) — maxmemory, 8 политик, приближённые LRU/LFU
- [Проектирование ключей](memory/02-key-design.md) — именование ключей, SCAN vs KEYS, UNLINK

### Распределение и отказоустойчивость

- [Репликация](distribution/00-replication.md) — master-replica, replication backlog, WAIT
- [Sentinel](distribution/01-sentinel.md) — автоматический failover, кворум
- [Cluster](distribution/02-cluster.md) — 16 384 слота, hash tags, MOVED/ASK

### Практические паттерны

- [Кеширование](patterns/00-caching.md) — cache-aside, stampede, early expiration
- [Rate limiting](patterns/01-rate-limiting.md) — fixed window, sliding window, token bucket
- [Распределённые блокировки](patterns/02-distributed-locks.md) — SET NX EX, Lua unlock, Redlock, fencing tokens
- [Очереди](patterns/03-queues.md) — LIST-очередь, reliable queue, delayed queue (ZSET), Streams

## Как всё связано

Redis — система компромиссов, но с другими приоритетами, чем у реляционных СУБД.

**Speed vs Durability:** Данные в RAM — операции за микросекунды. Цена — при падении без персистентности данные теряются. RDB и AOF смягчают проблему, но не дают ACID-гарантий.

**Simplicity vs Functionality:** Однопоточная модель исключает гонки и deadlock'и. Цена — медленная команда блокирует весь сервер, нет JOIN'ов и сложных запросов.

**Memory vs Capacity:** Всё в RAM — быстрый доступ. Цена — объём данных ограничен оперативной памятью, нужны политики вытеснения.

**Atomicity vs Flexibility:** Одна команда атомарна бесплатно. Для составных операций — MULTI/EXEC (без условий) или Lua-скрипты (с условиями, но блокируют event loop).

## См. также

- [Redis в Rails-приложении](../../rails/redis/index.md) — клиенты, connection_pool, паттерны использования из Ruby/Rails

## Sources

- Redis Documentation. <https://redis.io/docs/>
- «Redis in Action» — Josiah Carlson, Manning, 2013
- Redis source code. <https://github.com/redis/redis>
