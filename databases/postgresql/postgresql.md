# PostgreSQL: внутреннее устройство

**Предпосылки:** [SQL](../sql/sql.md) (SELECT, INSERT, UPDATE, DELETE), [транзакции](../sql/modification/transactions.md) (BEGIN, COMMIT, ROLLBACK), [ACID](../acid.md).

Большинство запросов к базе сводятся к нескольким паттернам доступа: точное совпадение или диапазон по упорядоченному столбцу, поиск элемента внутри составного значения, пространственные операции над геометрией или диапазонами, и фильтрация по огромным append-only таблицам. PostgreSQL предоставляет отдельный тип индекса под каждый паттерн, а за выбор между ними отвечает планировщик запросов. Но прежде чем разбираться с индексами и планировщиком, нужно понять физический уровень хранения, механизмы устойчивости к сбоям и параллельного доступа.

## Порядок изучения

Заметки сгруппированы по зависимостям: от физического хранения к устойчивости, параллельному доступу, обслуживанию, индексам и планировщику.

### Физическое хранение

Фундамент: как данные лежат на диске.

- [ACID в PostgreSQL](storage/acid.md) — реализация [ACID](../acid.md) через MVCC, WAL, constraints
- [Страницы и кортежи](storage/pages-and-tuples.md) — физическая единица хранения и формат строки
- [TOAST](storage/toast.md) — вынос больших значений за пределы страницы
- [Физическая структура хранения](storage/physical-layout.md) — файлы, форки, сегменты на диске и связь с WAL

### Устойчивость к сбоям и кеширование

Как PostgreSQL переживает сбои и почему дисковый I/O не убивает latency.

- [WAL](durability/wal.md) — журнал предзаписи для восстановления после сбоя
- [Буферный кеш](durability/buffer-cache.md) — shared buffers, dirty pages, [LRU](../../algorithms-and-data-structures/linear/lru-cache.md) vs [clock-sweep](../../algorithms-and-data-structures/linear/clock-sweep.md), WAL before data

### Параллельный доступ

Как транзакции читают и пишут параллельно, не ломая данные.

- [MVCC](concurrency/mvcc.md) — версионирование строк вместо блокировок чтения
- [Аномалии транзакций](concurrency/anomalies.md) — что может пойти не так при параллельном доступе
- [Уровни изоляции](concurrency/isolation-levels.md) — как PostgreSQL реализует READ COMMITTED, REPEATABLE READ, SERIALIZABLE
- [Блокировки](concurrency/locks.md) — координация записи, table-level и row-level locks
- [Практические паттерны](concurrency/patterns.md) — выбор между оптимистичным и пессимистичным подходом
- [Распространённые ошибки](concurrency/common-mistakes.md) — типичные заблуждения о транзакциях и блокировках
- [Очереди задач](concurrency/queues-and-skip-locked.md) — `FOR UPDATE SKIP LOCKED`, индекс под очередь, идемпотентность

### Обслуживание

- [VACUUM](maintenance/vacuum.md) — очистка dead tuples, предотвращение bloat

### Индексы

- [B-tree](indexes/btree.md) — индекс по умолчанию, точные совпадения и диапазоны
- [GIN](indexes/gin.md) — инвертированный индекс для массивов, JSONB, полнотекста
- [GiST](indexes/gist.md) — дерево для геометрии, диапазонов, пространственных запросов
- [Hash](indexes/hash.md) — хеш-индекс для точечных запросов по равенству
- [BRIN](indexes/brin.md) — компактный индекс для огромных таблиц с корреляцией
- [SP-GiST](indexes/spgist.md) — space-partitioned индекс (trie/quad-tree) для некоторых типов и запросов

### Проектирование схемы

Практический DDL (CREATE TABLE, constraints, партиционирование) — в [SQL: определение структуры](../sql/schema/tables-and-types.md). PG-специфичные расширения (JSONB, массивы, полнотекстовый поиск, функции) — в [SQL: PostgreSQL](../sql/postgresql/pg-extensions.md). Безопасное применение DDL на production-базах (блокировки, timeout discipline, expand-contract) — в [Миграциях](../migrations/migrations.md).

### Планировщик запросов

- [Планировщик запросов](query-processing/planner.md) — статистика, selectivity, cost model, методы доступа и алгоритмы соединения
- [Порядок соединения](query-processing/join-order.md) — [динамическое программирование](../../algorithms-and-data-structures/techniques/dynamic-programming.md), interesting orders, GEQO
- [Подзапросы и CTE](query-processing/subqueries-and-cte.md) — flattening, semi-join, материализация CTE
- [EXPLAIN](query-processing/explain.md) — как читать план: оценки vs факты, BUFFERS, где «болит» запрос
- [Память и spill](query-processing/memory-and-spill.md) — `work_mem`, сортировки и хеши, temp I/O
- [Prepared statements](query-processing/prepared-statements.md) — generic plan vs custom plan, parameter sensitivity
- [Диагностика медленных запросов](query-processing/diagnosing-slow-queries.md) — как быстро локализовать причину: оценки, I/O, spill, параметры

### Распределение и масштабирование

- [Репликация](../../system-design/replication.md) и [шардинг](../../system-design/sharding.md) — общие понятия (failover, кворум, shard key)
- [Репликация](./distribution/replication.md) — physical vs logical, lag, failover
- [Шардирование](distribution/sharding.md) — отличие от партиционирования, shard key, цена распределения

## Выбор индекса

| Задача | Индекс |
|--------|--------|
| Точное совпадение, диапазоны, сортировка | B-tree |
| Только точное совпадение, длинные ключи | Hash |
| «Содержит элемент» (массивы, JSONB, полнотекст) | GIN |
| Геометрия, диапазоны, «ближайший к» | GiST |
| Префиксы, пространственные разбиения (trie, quad-tree) | SP-GiST |
| Огромные append-only таблицы с корреляцией | BRIN |

| Операция | B-tree | Hash | GIN | GiST | SP-GiST | BRIN |
|----------|--------|------|-----|------|---------|------|
| = | ✓ | ✓ | | | | ✓ |
| <, >, <=, >=, BETWEEN | ✓ | | | | | ✓ |
| ORDER BY | ✓ | | | | | |
| @> (contains element) | | | ✓ | | | |
| && (overlaps) | | | ✓ | ✓ | | |
| @> (contains region) | | | | ✓ | ✓ | |
| <@ (contained in) | | | | ✓ | ✓ | |
| <-> (KNN) | | | | ✓ | ✓ | |
| LIKE 'prefix%' | ✓ | | | | ✓ | |
| UNIQUE | ✓ | | | | | |

## Как всё связано

PostgreSQL — система компромиссов. Каждая гарантия имеет цену:

**Durability vs Performance:** Писать на диск при каждом COMMIT дорого (random I/O). Решение — WAL (sequential I/O). Цена — сложность recovery и необходимость checkpoint'ов.

**Isolation vs Performance:** Блокировки при чтении убивают параллелизм. Решение — MVCC (версионирование). Цена — dead tuples и необходимость VACUUM.

**Memory vs I/O:** Диск медленный. Решение — буферный кеш (shared buffers). Цена — память ограничена, нужен алгоритм вытеснения, dirty pages требуют координации с WAL.

**Space vs Flexibility:** Tuple должен помещаться в страницу. Решение — TOAST (вынос больших значений). Цена — дополнительный I/O при чтении больших колонок.

**Correctness vs Performance:** Полная сериализуемость требует блокировок или откатов. Решение — уровни изоляции как компромисс. Цена — программист должен понимать, какие аномалии возможны.

**Simplicity vs Flexibility:** Один механизм защиты не подходит всем. Решение — два подхода (оптимистичный/пессимистичный) + атомарные операции SQL. Цена — программист должен выбирать.

**XID Space vs Complexity:** 32-битный XID ограничен, оборачивается. Решение — freezing старых tuples. Цена — VACUUM должен успевать замораживать, долгие транзакции опасны.

## Sources

- PostgreSQL Documentation (пример: v16): Transaction Isolation, MVCC, WAL, Indexes, VACUUM, Query Planning. <https://www.postgresql.org/docs/16/>
