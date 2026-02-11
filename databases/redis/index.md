# Redis: структуры данных в памяти

**Предпосылки:** [ACID](../postgresql/storage/00-acid.md), базовые структуры данных ([массив](../../algorithms-and-data-structures/linear/01-array.md), [хеш-таблица](../../algorithms-and-data-structures/linear/05-hash-table.md), [связный список](../../algorithms-and-data-structures/linear/03-linked-list.md)), сеть (клиент/сервер, запрос/ответ).

Redis — это сервер структур данных в оперативной памяти с сетевым доступом. В отличие от реляционных СУБД, Redis не даёт ACID-гарантий и не хранит данные в таблицах. Вместо этого он предоставляет набор структур данных (строки, хеш-таблицы, списки, множества, упорядоченные множества, потоки), доступных по ключу через простой протокол. Всё хранится в RAM, операции выполняются в однопоточном event loop — простые команды часто укладываются в микросекунды, но реальная латентность зависит от сети, объёма данных, настроек персистентности и блокирующих команд.

## Порядок изучения

Всё начинается с архитектуры: однопоточный event loop определяет, почему команды атомарны, почему одна медленная команда блокирует весь сервер и как Redis обрабатывает тысячи соединений без потоков. Без этой модели остальные темы повисают в воздухе — непонятно, откуда берётся атомарность и почему O(N)-команды опасны.

Далее — структуры данных. Каждая из них работает поверх event loop и использует внутренние кодировки (listpack, intset, skiplist), которые проще понять последовательно: String вводит SDS и механизм кодировок, Hash и List показывают listpack и пороги переключения, Set и Sorted Set добавляют intset и skip list, а Stream, HyperLogLog, Bitmap и Pub/Sub опираются на уже знакомые идеи. После структур данных естественно перейти к атомарности составных операций: MULTI/EXEC и Lua-скрипты используют конкретные команды над конкретными структурами, и примеры без знания этих структур не читаются. Персистентность (RDB и AOF) не зависит от структур данных и атомарности — её можно читать параллельно с ними; достаточно понимать fork, copy-on-write и fsync.

Управление памятью требует знания всех типов данных, потому что внутренние кодировки и пороги переключения специфичны для каждого типа, а политики вытеснения работают на уровне ключей. Распределение (репликация, Sentinel, Cluster) опирается на персистентность — реплика получает данные через RDB-snapshot и AOF-поток — и на ограничения MULTI/EXEC в кластере. Практические паттерны идут последними: кеширование использует eviction и TTL, очереди — LIST и Stream, распределённые блокировки — Lua и SET NX EX, rate limiting — INCR и ZRANGEBYSCORE. Без предыдущих тем эти рецепты превращаются в чёрные ящики.

### Архитектура и модель исполнения

Однопоточная модель, работа с памятью и отличия от реляционных СУБД.

- [Что такое Redis](architecture/00-what-is-redis.md) — сравнение с PostgreSQL, философия выбора хранилища, CAP
- [Event loop](architecture/01-event-loop.md) — однопоточная модель, мультиплексирование, что блокирует цикл
- [Pipelining](architecture/02-pipelining.md) — батчинг команд для снижения сетевых задержек
- [Логические базы (SELECT)](architecture/03-logical-databases.md) — db 0..N, зачем это нужно и почему в Cluster всегда db 0

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

- [RDB](persistence/00-rdb.md) — BGSAVE, fork + copy-on-write, компактный snapshot
- [AOF](persistence/01-aof.md) — fsync-политики, rewrite, гибрид RDB + AOF

### Управление памятью

- [Внутренние кодировки](memory/00-encodings.md) — redisObject (16 байт), listpack, пороги переключения
- [Eviction](memory/01-eviction.md) — maxmemory, 8 политик, приближённые LRU/LFU
- [Проектирование ключей](memory/02-key-design.md) — именование ключей, KEYS и SCAN, UNLINK

### Распределение и отказоустойчивость

- [Репликация](../../system-design/replication.md) и [шардинг](../../system-design/sharding.md) — общие понятия (failover, кворум, shard key)
- [Распределение Redis](distribution/00-distribution.md) — что решают репликация, Sentinel и Cluster
- [Репликация](distribution/00-replication.md) — master-replica, replication backlog, WAIT
- [Sentinel](distribution/01-sentinel.md) — автоматический failover, кворум
- [Cluster](distribution/02-cluster.md) — 16 384 слота, hash tags, MOVED/ASK

### Практические паттерны

- [Кеширование](patterns/00-caching.md) — cache-aside, stampede, early expiration (см. также [архитектура кэширования](../../system-design/07-caching.md))
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
