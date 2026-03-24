# PostgreSQL: расширения SQL

**Предпосылки:** [SQL](../index.md) (весь курс SQL).

PostgreSQL расширяет стандартный SQL типами данных, операторами, DDL-конструкциями и query-фичами.

## Порядок изучения

### Типы данных и операторы
- [JSONB](00-jsonb.md) — работа с JSON внутри SQL
- [Массивы и диапазоны](01-arrays-and-ranges.md) — ARRAY, range types

### Поиск
- [Полнотекстовый поиск](02-full-text-search.md) — tsvector, tsquery, ranking

### Процедурный SQL
- [Функции и процедуры](03-functions-and-procedures.md) — CREATE FUNCTION, PL/pgSQL

### Production DDL
- [Индексы в production](04-index-operations.md) — CONCURRENTLY, REINDEX
- [EXCLUSION](05-exclusion-constraints.md) — запрет пересечений
- [Партиционирование](06-partitioning.md) — RANGE/LIST/HASH, pruning, retention
- [Материализованные представления](07-materialized-views.md) — REFRESH, CONCURRENTLY

### Запросы
- [DISTINCT ON](08-distinct-on.md) — top-1 в группе одной строкой

## Как всё связано

**Мощность vs портативность:** Каждая конструкция в этом разделе — PG-специфичная. При переходе на другую СУБД потребуется адаптация: стандартный SQL из основного курса переносится, расширения — нет.

## См. также
- [PostgreSQL internals](../../postgresql/index.md) — как всё это работает под капотом

## Sources

- PostgreSQL Documentation (v16). <https://www.postgresql.org/docs/16/>
