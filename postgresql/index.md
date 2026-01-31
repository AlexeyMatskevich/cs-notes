# PostgreSQL: внутреннее устройство

**Предпосылки:** SQL (SELECT, INSERT, UPDATE, DELETE), транзакции (BEGIN, COMMIT, ROLLBACK).

Большинство запросов к базе сводятся к нескольким паттернам доступа: точное совпадение или диапазон по упорядоченному столбцу, поиск элемента внутри составного значения, пространственные операции над геометрией или диапазонами, и фильтрация по огромным append-only таблицам. PostgreSQL предоставляет отдельный тип индекса под каждый паттерн, а за выбор между ними отвечает планировщик запросов. Но прежде чем разбираться с индексами и планировщиком, нужно понять физический уровень хранения, механизмы устойчивости к сбоям и параллельного доступа.

## Порядок изучения

Заметки сгруппированы по зависимостям: от физического хранения к устойчивости, параллельному доступу, обслуживанию, индексам и планировщику.

### Физическое хранение

Фундамент: как данные лежат на диске.

- [ACID](storage/00-acid.md) — четыре гарантии транзакций
- [Страницы и кортежи](storage/01-pages-and-tuples.md) — физическая единица хранения и формат строки
- [TOAST](storage/02-toast.md) — вынос больших значений за пределы страницы
- [Физическая структура хранения](storage/03-physical-layout.md) — справочник: файлы, форки, сегменты на диске

### Устойчивость к сбоям и кеширование

Как PostgreSQL переживает сбои и почему дисковый I/O не убивает latency.

- [WAL](durability/00-wal.md) — журнал предзаписи для восстановления после сбоя
- [Буферный кеш](durability/01-buffer-cache.md) — shared buffers, dirty pages, [LRU](../algorithms-and-data-structures/linear/06-lru-cache.md) vs [clock-sweep](../algorithms-and-data-structures/linear/07-clock-sweep.md), WAL before data

### Параллельный доступ

Как транзакции читают и пишут параллельно, не ломая данные.

- [MVCC](concurrency/00-mvcc.md) — версионирование строк вместо блокировок чтения
- [Аномалии транзакций](concurrency/01-anomalies.md) — что может пойти не так при параллельном доступе
- [Уровни изоляции](concurrency/02-isolation-levels.md) — как PostgreSQL реализует READ COMMITTED, REPEATABLE READ, SERIALIZABLE
- [Блокировки](concurrency/03-locks.md) — координация записи, table-level и row-level locks
- [Практические паттерны](concurrency/04-patterns.md) — выбор между оптимистичным и пессимистичным подходом
- [Распространённые ошибки](concurrency/05-common-mistakes.md) — типичные заблуждения о транзакциях и блокировках
- [Очереди задач](concurrency/06-queues-and-skip-locked.md) — `FOR UPDATE SKIP LOCKED`, индекс под очередь, идемпотентность

### Обслуживание

- [VACUUM](maintenance/00-vacuum.md) — очистка dead tuples, предотвращение bloat

### Индексы

- [B-tree](indexes/00-btree.md) — индекс по умолчанию, точные совпадения и диапазоны
- [GIN](indexes/01-gin.md) — инвертированный индекс для массивов, JSONB, полнотекста
- [GiST](indexes/02-gist.md) — дерево для геометрии, диапазонов, пространственных запросов
- [Hash](indexes/03-hash.md) — хеш-индекс для точечных запросов по равенству
- [BRIN](indexes/04-brin.md) — компактный индекс для огромных таблиц с корреляцией
- [SP-GiST](indexes/05-spgist.md) — space-partitioned индекс (trie/quad-tree) для некоторых типов и запросов

### Проектирование схемы

- [Ограничения (constraints)](schema-design/00-constraints.md) — PK/UNIQUE/FK/CHECK/EXCLUDE, влияние на корректность и скорость
- [Sequence и авто-id](schema-design/01-sequences-and-identity.md) — SERIAL/IDENTITY, «дырки» в id и порядок событий
- [Партиционирование](schema-design/02-partitioning.md) — pruning, индексы на партициях, типовые ошибки запросов

### Планировщик запросов

- [Планировщик запросов](query-processing/00-planner.md) — статистика, selectivity, cost model, методы доступа и алгоритмы соединения
- [Порядок соединения](query-processing/01-join-order.md) — [динамическое программирование](../algorithms-and-data-structures/techniques/00-dynamic-programming.md), interesting orders, GEQO
- [Подзапросы и CTE](query-processing/02-subqueries-and-cte.md) — flattening, semi-join, материализация CTE
- [EXPLAIN](query-processing/03-explain.md) — как читать план: оценки vs факты, BUFFERS, где «болит» запрос
- [Память и spill](query-processing/04-memory-and-spill.md) — `work_mem`, сортировки и хеши, temp I/O
- [Prepared statements](query-processing/05-prepared-statements.md) — generic plan vs custom plan, parameter sensitivity
- [Диагностика медленных запросов](query-processing/06-diagnosing-slow-queries.md) — как быстро локализовать причину: оценки, I/O, spill, параметры
- [Пагинация](query-processing/07-pagination.md) — `LIMIT/OFFSET` vs keyset, стабильный порядок и стоимость “дальних” страниц

## Выбор индекса

| Задача | Индекс |
|--------|--------|
| Точное совпадение, диапазоны, сортировка | B-tree |
| Только точное совпадение, длинные ключи | Hash |
| «Содержит элемент» (массивы, JSONB, полнотекст) | GIN |
| Геометрия, диапазоны, «ближайший к» | GiST |
| Огромные append-only таблицы с корреляцией | BRIN |

| Операция | B-tree | Hash | GIN | GiST | BRIN |
|----------|--------|------|-----|------|------|
| = | ✓ | ✓ | | | ✓ |
| <, >, <=, >=, BETWEEN | ✓ | | | | ✓ |
| ORDER BY | ✓ | | | | |
| @> (contains element) | | | ✓ | | |
| && (overlaps) | | | ✓ | ✓ | |
| @> (contains region) | | | | ✓ | |
| <-> (KNN) | | | | ✓ | |
| UNIQUE | ✓ | | | | |

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
