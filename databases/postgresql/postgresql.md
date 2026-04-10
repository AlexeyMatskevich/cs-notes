---
tags:
  - domain/postgresql
  - type/overview
aliases:
  - PostgreSQL
---

# PostgreSQL: внутреннее устройство

**Предпосылки:** [SQL](../sql/sql.md) (SELECT, INSERT, UPDATE, DELETE), [транзакции](../sql/modification/transactions.md) (BEGIN, COMMIT, ROLLBACK), [ACID](../acid.md).

Большинство запросов к базе сводятся к нескольким паттернам доступа: точное совпадение или диапазон по упорядоченному столбцу, поиск элемента внутри составного значения, пространственные операции над геометрией или диапазонами, и фильтрация по огромным append-only таблицам. PostgreSQL предоставляет отдельный тип индекса под каждый паттерн, а за выбор между ними отвечает планировщик запросов. Но прежде чем разбираться с индексами и планировщиком, нужно понять физический уровень хранения, механизмы устойчивости к сбоям и параллельного доступа.

## Порядок изучения

Заметки сгруппированы по зависимостям: от физического хранения к устойчивости, параллельному доступу, обслуживанию, индексам и планировщику.

### Физическое хранение

Фундамент: как данные лежат на диске.

- [[databases/postgresql/storage/acid|ACID в PostgreSQL]] — реализация [ACID](../acid.md) через [[databases/postgresql/concurrency/mvcc|MVCC]], [[databases/postgresql/durability/wal|WAL]], constraints
- [[databases/postgresql/storage/pages-and-tuples|Страницы и кортежи]] — физическая единица хранения и формат строки
- [[databases/postgresql/storage/toast|TOAST]] — вынос больших значений за пределы страницы
- [[databases/postgresql/storage/physical-layout|Физическая структура хранения]] — файлы, форки, сегменты на диске и связь с [[databases/postgresql/durability/wal|WAL]]

### Устойчивость к сбоям и кеширование

Как PostgreSQL переживает сбои и почему дисковый I/O не убивает latency.

- [[databases/postgresql/durability/wal|WAL]] — журнал предзаписи для восстановления после сбоя
- [[databases/postgresql/durability/buffer-cache|Буферный кеш]] — shared buffers, dirty pages, [LRU](../../algorithms-and-data-structures/linear/lru-cache.md) vs [clock-sweep](../../algorithms-and-data-structures/linear/clock-sweep.md), [[databases/postgresql/durability/wal|WAL]] before data

### Параллельный доступ

Как транзакции читают и пишут параллельно, не ломая данные.

- [[databases/postgresql/concurrency/mvcc|MVCC]] — версионирование строк вместо блокировок чтения
- [[databases/postgresql/concurrency/anomalies|Аномалии транзакций]] — что может пойти не так при параллельном доступе
- [[databases/postgresql/concurrency/isolation-levels|Уровни изоляции]] — как PostgreSQL реализует READ COMMITTED, REPEATABLE READ, SERIALIZABLE
- [[databases/postgresql/concurrency/locks|Блокировки]] — координация записи, table-level и row-level locks
- [[databases/postgresql/concurrency/patterns|Практические паттерны]] — выбор между оптимистичным и пессимистичным подходом
- [[databases/postgresql/concurrency/common-mistakes|Распространённые ошибки]] — типичные заблуждения о транзакциях и блокировках
- [[databases/postgresql/concurrency/queues-and-skip-locked|Очереди задач]] — `FOR UPDATE SKIP LOCKED`, индекс под очередь, идемпотентность

### Обслуживание

- [[databases/postgresql/maintenance/vacuum|VACUUM]] — очистка dead tuples, предотвращение bloat

### Индексы

- [[databases/postgresql/indexes/btree|B-tree]] — индекс по умолчанию, точные совпадения и диапазоны
- [[databases/postgresql/indexes/gin|GIN]] — инвертированный индекс для массивов, JSONB, полнотекста
- [[databases/postgresql/indexes/gist|GiST]] — дерево для геометрии, диапазонов, пространственных запросов
- [[databases/postgresql/indexes/hash|Hash]] — хеш-индекс для точечных запросов по равенству
- [[databases/postgresql/indexes/brin|BRIN]] — компактный индекс для огромных таблиц с корреляцией
- [[databases/postgresql/indexes/spgist|SP-GiST]] — space-partitioned индекс (trie/quad-tree) для некоторых типов и запросов

### Проектирование схемы

Практический DDL (CREATE TABLE, constraints, партиционирование) — в [SQL: определение структуры](../sql/schema/tables-and-types.md). PG-специфичные расширения (JSONB, массивы, полнотекстовый поиск, функции) — в [SQL: PostgreSQL](../sql/postgresql/pg-extensions.md). Безопасное применение DDL на production-базах (блокировки, timeout discipline, expand-contract) — в [Миграциях](../migrations/migrations.md).

### Планировщик запросов

- [[databases/postgresql/query-processing/planner|Планировщик запросов]] — статистика, selectivity, cost model, методы доступа и алгоритмы соединения
- [[databases/postgresql/query-processing/join-order|Порядок соединения]] — [динамическое программирование](../../algorithms-and-data-structures/techniques/dynamic-programming.md), interesting orders, GEQO
- [[databases/postgresql/query-processing/subqueries-and-cte|Подзапросы и CTE]] — flattening, semi-join, материализация CTE
- [[databases/postgresql/query-processing/explain|EXPLAIN]] — как читать план: оценки vs факты, BUFFERS, где «болит» запрос
- [[databases/postgresql/query-processing/memory-and-spill|Память и spill]] — `work_mem`, сортировки и хеши, temp I/O
- [[databases/postgresql/query-processing/prepared-statements|Prepared statements]] — generic plan vs custom plan, parameter sensitivity
- [[databases/postgresql/query-processing/diagnosing-slow-queries|Диагностика медленных запросов]] — как быстро локализовать причину: оценки, I/O, spill, параметры

### Распределение и масштабирование

- [Репликация](../../system-design/replication.md) и [шардинг](../../system-design/sharding.md) — общие понятия (failover, кворум, shard key)
- [Репликация](./distribution/replication.md) — physical vs logical, lag, failover
- [[databases/postgresql/distribution/sharding|Шардирование]] — отличие от партиционирования, shard key, цена распределения

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

**Durability vs Performance:** Писать на диск при каждом COMMIT дорого (random I/O). Решение — [[databases/postgresql/durability/wal|WAL]] (sequential I/O). Цена — сложность recovery и необходимость checkpoint'ов.

**Isolation vs Performance:** Блокировки при чтении убивают параллелизм. Решение — [[databases/postgresql/concurrency/mvcc|MVCC]] (версионирование). Цена — dead tuples и необходимость [[databases/postgresql/maintenance/vacuum|VACUUM]].

**Memory vs I/O:** Диск медленный. Решение — [[databases/postgresql/durability/buffer-cache|буферный кеш]] (shared buffers). Цена — память ограничена, нужен алгоритм вытеснения, dirty pages требуют координации с [[databases/postgresql/durability/wal|WAL]].

**Space vs Flexibility:** Tuple должен помещаться в страницу. Решение — [[databases/postgresql/storage/toast|TOAST]] (вынос больших значений). Цена — дополнительный I/O при чтении больших колонок.

**Correctness vs Performance:** Полная сериализуемость требует блокировок или откатов. Решение — [[databases/postgresql/concurrency/isolation-levels|уровни изоляции]] как компромисс. Цена — программист должен понимать, какие [[databases/postgresql/concurrency/anomalies|аномалии]] возможны.

**Simplicity vs Flexibility:** Один механизм защиты не подходит всем. Решение — два подхода (оптимистичный/пессимистичный) + атомарные операции SQL. Цена — программист должен выбирать.

**XID Space vs Complexity:** 32-битный XID ограничен, оборачивается. Решение — freezing старых tuples. Цена — [[databases/postgresql/maintenance/vacuum|VACUUM]] должен успевать замораживать, долгие транзакции опасны.

## Sources

- PostgreSQL Documentation (пример: v16): Transaction Isolation, MVCC, WAL, Indexes, VACUUM, Query Planning. <https://www.postgresql.org/docs/16/>
