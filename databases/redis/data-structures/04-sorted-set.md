# Sorted Set

**Предпосылки:** [Set](03-set.md), [связный список](../../../algorithms-and-data-structures/linear/03-linked-list.md), [хеш-таблица](../../../algorithms-and-data-structures/linear/05-hash-table.md).

SET гарантирует уникальность, но не упорядоченность. Sorted Set (ZSET) добавляет каждому элементу числовой вес (score) и поддерживает автоматическую сортировку. Это позволяет строить лидерборды, очереди с приоритетом, временные ряды — любые сценарии, где нужна упорядоченная уникальная коллекция с быстрым доступом по рангу и диапазону score.

## Skip list + hashtable

Sorted Set (ZSET) хранит уникальные элементы, каждый с числовым весом (score). Элементы всегда упорядочены по score, при равных score — лексикографически по значению. Внутри Redis ZSET использует две структуры данных одновременно.

**Skip list** (`src/t_zset.c`, структура `zskiplist`) обеспечивает упорядоченность. Skip list — это вероятностная альтернатива сбалансированному дереву. Нижний уровень — обычный отсортированный связный список всех элементов. Каждый следующий уровень содержит случайное подмножество элементов нижнего уровня (с вероятностью 1/4 для Redis). Поиск начинается с верхнего уровня и спускается вниз, пропуская большие участки списка. Средняя сложность поиска, вставки и удаления — O(log n). Каждый узел skip list хранит span — количество элементов между ним и следующим узлом на этом уровне. Благодаря span Redis может эффективно вычислять ранг элемента (его позицию в отсортированной последовательности) за O(log n), суммируя span'ы при спуске по уровням.

**Hashtable** (тот же `dict.c`, что в Hash и Set) обеспечивает O(1) поиск score по элементу. Без хеш-таблицы команда `ZSCORE member` потребовала бы O(log n) в skip list.

При малом количестве элементов (до `zset-max-listpack-entries`) и коротких значениях (до `zset-max-listpack-value`) ZSET использует listpack вместо skip list + hashtable — по тому же принципу, что и Hash.

## Основные команды

Skip list и hashtable дают O(log n) операции с диапазонами и O(1) получение score — рассмотрим основные команды, которые этим пользуются.

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

Автоматическая сортировка по score делает ZSET естественным выбором для очередей, где важен не порядок вставки, а приоритет или время события. LIST сохраняет порядок вставки, но не гарантирует сортировку по внешнему критерию. Если два события произошли на разных серверах, сетевые задержки могут нарушить порядок в LIST. ZSET решает эту проблему: используя timestamp как score, элементы всегда упорядочены по времени события, независимо от порядка поступления в Redis.

```redis-cli
ZADD queue 1700000000.000 "event_A"      -- timestamp как score
ZADD queue 1700000000.050 "event_B"

-- забрать самый "старый" элемент (минимальный score) атомарно:
ZPOPMIN queue 1
```

Дополнительные преимущества: выборка по диапазону score (`ZRANGEBYSCORE`), удаление конкретного элемента из середины за O(log n) (`ZREM`), определение позиции в очереди (`ZRANK`). Подробнее о паттернах очередей — в [разделе очередей](../patterns/03-queues.md).

## Операции над множествами

Как и SET, ZSET поддерживает объединение и пересечение: `ZUNIONSTORE`, `ZINTERSTORE`. При объединении score одинаковых элементов из разных множеств суммируются (или берётся min/max — настраивается параметром `AGGREGATE`).

## См. также

- [Практика в Ruby/Rails: ZSET](../../../rails/redis/02-data-structures-in-practice.md#zset-sorted-set) — ZADD/ZRANGE/ZINCRBY, leaderboard и очереди из Rails-приложения

## Sources

- Redis Documentation: Sorted Sets. <https://redis.io/docs/data-types/sorted-sets/>
- William Pugh, «Skip Lists: A Probabilistic Alternative to Balanced Trees», 1990
- Redis source: `src/t_zset.c`, структура `zskiplistNode`
