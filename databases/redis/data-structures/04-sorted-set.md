# Sorted Set

**Предпосылки:** [Set](03-set.md), [связный список](../../../algorithms-and-data-structures/linear/03-linked-list.md), [хеш-таблица](../../../algorithms-and-data-structures/linear/05-hash-table.md), [skip list](../../../algorithms-and-data-structures/non-linear/09-skip-list.md).

← [Set](03-set.md) | [Stream](05-stream.md) →

## Проблема порядка

Лидерборд. Alice набрала 100 очков, Bob — 250, Carol — 175. Три вопроса: «Какой ранг у Carol?», «Кто в топ-10?», «Кто набрал от 100 до 200?». [SET](03-set.md) гарантирует уникальность, но не может ответить ни на один — у элементов нет порядка. Sorted Set (ZSET) добавляет каждому элементу числовой вес — score — и поддерживает автоматическую сортировку. Элементы упорядочены по score, при равных score — лексикографически по значению. (Префикс Z в командах — следствие того, что буква S уже занята командами SET; antirez выбрал Z как свободную букву для нового пространства команд.)

## Score, ранги и диапазоны

```redis-cli
ZADD leaderboard 100 "alice"
ZADD leaderboard 250 "bob"
ZADD leaderboard 175 "carol"

ZSCORE leaderboard "carol"                   -- → 175
ZRANK leaderboard "carol"                    -- → 1 (второе место по возрастанию, индекс с 0)
ZREVRANK leaderboard "carol"                 -- → 1 (серебро: bob=0, carol=1, alice=2)

ZRANGE leaderboard 0 2 REV WITHSCORES       -- топ-3 по убыванию (Redis 6.2+)
-- → [["bob", 250], ["carol", 175], ["alice", 100]]

ZRANGEBYSCORE leaderboard 100 200            -- кто набрал от 100 до 200 → ["alice", "carol"]
ZINCRBY leaderboard 50 "alice"               -- alice теперь 150
ZREM leaderboard "alice"                     -- удалить элемент
```

`ZADD` добавляет элемент или обновляет score, если элемент уже существует. `ZRANK` возвращает позицию элемента за O(log n) — как именно, разберём в секции про skip list. `ZRANGEBYSCORE` с `LIMIT offset count` позволяет пагинацию по score-диапазону.

Лидерборд — один сценарий. Когда score — timestamp, ZSET превращается в нечто другое.

## ZSET как очередь с приоритетом

События приходят с разных серверов, сетевые задержки нарушают порядок. [LIST](02-list.md) сохраняет порядок вставки, но не порядок событий: если event_B (timestamp 1050) пришёл в Redis раньше event_A (timestamp 1000), LIST поставит B перед A. ZSET с timestamp в качестве score решает эту проблему — элементы всегда упорядочены по времени события, а не по времени поступления:

```redis-cli
ZADD queue 1700000000.000 "event_A"
ZADD queue 1700000000.050 "event_B"

ZPOPMIN queue 1    -- забрать элемент с наименьшим score (самый старый)
-- → [["event_A", 1700000000.0]]
```

`ZPOPMIN` атомарно извлекает элемент с минимальным score — аналог `RPOP` для LIST, но с гарантией правильного порядка. Удаление конкретного элемента из середины — `ZREM`, за O(log n). Определение позиции в очереди — `ZRANK`. Подробнее о паттернах очередей — в [разделе очередей](../patterns/03-queues.md).

## Операции со score'ами

Как и SET, ZSET поддерживает объединение и пересечение: `ZUNIONSTORE`, `ZINTERSTORE`. При объединении score одинаковых элементов из разных множеств по умолчанию суммируются. Параметр `AGGREGATE` меняет поведение: `MIN` берёт минимальный score, `MAX` — максимальный. Параметр `WEIGHTS` позволяет умножить score каждого входного множества на коэффициент перед агрегацией.

```redis-cli
ZUNIONSTORE combined 2 scores:week1 scores:week2 AGGREGATE SUM
-- суммарный лидерборд за две недели
```

## Внутри: skip list + hashtable

ZSET нужен O(log n) на операции с диапазонами и рангами И O(1) на получение score по элементу. Одна структура данных не даёт обоих гарантий одновременно — поэтому ZSET использует две.

**[Skip list](../../../algorithms-and-data-structures/non-linear/09-skip-list.md)** (`src/t_zset.c`, структура `zskiplist`) обеспечивает порядок. Это многоуровневый отсортированный связный список с O(log n) на поиск, вставку и удаление. Redis использует вероятность продвижения 1/4 (вместо классической 1/2), что уменьшает среднее количество уровней и экономит память на указателях.

Каждый узел skip list хранит span — количество элементов, которые перескакивает указатель на этом уровне. Благодаря span Redis вычисляет ранг элемента за O(log n), не подсчитывая элементы. Пример: `ZRANK leaderboard "carol"` находит узел "carol" в skip list, спускаясь с верхних уровней к нижним. На каждом шаге при движении вправо Redis суммирует span пройденных указателей. К моменту, когда "carol" найдена, сумма span'ов равна её рангу.

**Hashtable** (тот же `dict.c`, что в [Hash](./01-hash.md) и [Set](03-set.md)) обеспечивает O(1) поиск score по элементу. Без хеш-таблицы `ZSCORE member` требовал бы O(log n) обхода skip list.

При малом количестве элементов (до `zset-max-listpack-entries`, по умолчанию 128) и коротких значениях (до `zset-max-listpack-value`, по умолчанию 64 байта) ZSET использует listpack вместо skip list + hashtable — по тому же принципу, что и [Hash](./01-hash.md).

## См. также

- [Очередь звонков на ZSET в Rails](../../../rails/redis/practice/sorted-set-call-queue.md) — приоритеты, ZPOPMAX, ZREVRANK

## Sources

- Redis Documentation: Sorted Sets. <https://redis.io/docs/data-types/sorted-sets/>
- William Pugh, «Skip Lists: A Probabilistic Alternative to Balanced Trees», 1990
- Redis source: `src/t_zset.c`, структура `zskiplistNode`

---

← [Set](03-set.md) | [Stream](05-stream.md) →
