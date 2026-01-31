# Sorted Set

**Предпосылки:** [Set](03-set.md), [связный список](../../../algorithms-and-data-structures/linear/03-linked-list.md), [хеш-таблица](../../../algorithms-and-data-structures/linear/05-hash-table.md).

## Что хранит ZSET

[SET](03-set.md) гарантирует уникальность, но не упорядоченность. Sorted Set (ZSET) добавляет каждому элементу числовой вес (score) и поддерживает автоматическую сортировку. Элементы всегда упорядочены по score, при равных score — лексикографически по значению. Это позволяет строить лидерборды, очереди с приоритетом, временные ряды — любые сценарии, где нужна упорядоченная уникальная коллекция с быстрым доступом по рангу и диапазону score.

## Основные команды

```redis-cli
ZADD leaderboard 100 "alice"
ZADD leaderboard 250 "bob"
ZADD leaderboard 175 "carol"

ZRANGE leaderboard 0 2                       -- по возрастанию → ["alice", "carol", "bob"]
ZRANGE leaderboard 0 2 REV WITHSCORES         -- по убыванию с весами (Redis 6.2+)
                                              -- → [["bob", 250], ["carol", 175], ["alice", 100]]

ZSCORE leaderboard "carol"                   -- → 175
ZREVRANK leaderboard "carol"                 -- → 1 (второе место, индекс с 0)

ZINCRBY leaderboard 50 "alice"               -- alice теперь 150

ZRANGEBYSCORE leaderboard 100 200            -- элементы со score от 100 до 200
ZRANGEBYSCORE leaderboard "-inf" "+inf" LIMIT 0 10  -- первые 10 по возрастанию score
```

## ZSET как очередь с приоритетом

Автоматическая сортировка по score делает ZSET естественным выбором для очередей, где важен не порядок вставки, а приоритет или время события. [LIST](02-list.md) сохраняет порядок вставки, но не гарантирует сортировку по внешнему критерию. Если два события произошли на разных серверах, сетевые задержки могут нарушить порядок в LIST. ZSET решает эту проблему: используя timestamp как score, элементы всегда упорядочены по времени события, независимо от порядка поступления в Redis.

```redis-cli
ZADD queue 1700000000.000 "event_A"      -- timestamp как score
ZADD queue 1700000000.050 "event_B"

-- забрать самый "старый" элемент (минимальный score) атомарно:
ZPOPMIN queue 1
```

Дополнительные преимущества: выборка по диапазону score (`ZRANGEBYSCORE`), удаление конкретного элемента из середины за O(log n) (`ZREM`), определение позиции в очереди (`ZRANK`). Подробнее о паттернах очередей — в [разделе очередей](../patterns/03-queues.md).

## Операции над множествами

Как и SET, ZSET поддерживает объединение и пересечение: `ZUNIONSTORE`, `ZINTERSTORE`. При объединении score одинаковых элементов из разных множеств суммируются (или берётся min/max — настраивается параметром `AGGREGATE`).

## Внутреннее устройство: skip list + hashtable

Как ZSET обеспечивает O(log n) на операции с диапазонами и одновременно O(1) на получение score? Используя две структуры данных одновременно.

**Skip list** (`src/t_zset.c`, структура `zskiplist`) обеспечивает упорядоченность. Нижний уровень — обычный отсортированный связный список всех элементов. Каждый следующий уровень содержит случайное подмножество элементов нижнего (с вероятностью 1/4 для Redis). Поиск начинается с верхнего уровня и спускается вниз, пропуская большие участки списка — средняя сложность поиска, вставки и удаления O(log n). Каждый узел хранит span — количество элементов между ним и следующим узлом на этом уровне. Благодаря span Redis вычисляет ранг элемента (его позицию в отсортированной последовательности) за O(log n), суммируя span'ы при спуске.

**Hashtable** (тот же `dict.c`, что в [Hash](01-hash.md) и [Set](03-set.md)) обеспечивает O(1) поиск score по элементу. Без хеш-таблицы команда `ZSCORE member` потребовала бы O(log n) в skip list.

При малом количестве элементов (до `zset-max-listpack-entries`, по умолчанию 128) и коротких значениях (до `zset-max-listpack-value`, по умолчанию 64 байта) ZSET использует listpack вместо skip list + hashtable — по тому же принципу, что и [Hash](01-hash.md).

## См. также

- [Практика в Ruby/Rails: ZSET](../../../rails/redis/02-data-structures-in-practice.md#zset-sorted-set) — ZADD/ZRANGE/ZINCRBY, leaderboard и очереди из Rails-приложения

## Sources

- Redis Documentation: Sorted Sets. <https://redis.io/docs/data-types/sorted-sets/>
- William Pugh, «Skip Lists: A Probabilistic Alternative to Balanced Trees», 1990
- Redis source: `src/t_zset.c`, структура `zskiplistNode`
