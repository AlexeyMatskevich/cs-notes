# PostgreSQL: расширения SQL

**Предпосылки:** [SQL](../sql.md) (весь курс SQL).

PostgreSQL расширяет стандартный SQL типами данных, операторами, DDL-конструкциями и query-фичами. Нумерация файлов задаёт рекомендованный порядок чтения, но темы в основном независимы — любой файл можно читать после завершения основного курса SQL.

## Порядок изучения

### Типы данных и операторы
- [JSONB](jsonb.md) — работа с JSON внутри SQL
- [Массивы и диапазоны](arrays-and-ranges.md) — ARRAY, range types

### Поиск
- [Полнотекстовый поиск](full-text-search.md) — tsvector, tsquery, ranking

### Процедурный SQL
- [Функции и процедуры](functions-and-procedures.md) — CREATE FUNCTION, PL/pgSQL
- [Триггеры](triggers.md) — автоматический вызов функций при DML

### Production DDL
- [Индексы в production](index-operations.md) — CONCURRENTLY, REINDEX, USING INDEX
- [EXCLUSION](exclusion-constraints.md) — запрет пересечений
- [Партиционирование](partitioning.md) — RANGE/LIST/HASH, pruning, retention
- [Материализованные представления](materialized-views.md) — REFRESH, CONCURRENTLY

### Изменение данных
- [Составные DML в PostgreSQL](compound-dml.md) — UPDATE...FROM, DELETE...USING, writable CTEs, MERGE с DELETE (PG 17)

### Запросы
- [DISTINCT ON](distinct-on.md) — top-1 в группе одной строкой

## Как всё связано

**Мощность vs портативность:** Каждая конструкция в этом разделе — PG-специфичная. При переходе на другую СУБД потребуется адаптация: стандартный SQL из основного курса переносится, расширения — нет.

## См. также
- [PostgreSQL internals](../../postgresql/postgresql.md) — как всё это работает под капотом

## Sources

- PostgreSQL Documentation (v16). <https://www.postgresql.org/docs/16/>
