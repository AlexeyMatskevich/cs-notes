# SQL

**Предпосылки:** базовое программирование (переменные, типы, функции, условия, циклы).

SQL — декларативный язык для работы с реляционными базами данных. В отличие от императивных языков, где программист описывает *как* вычислить результат, SQL описывает *что* нужно получить, а СУБД сама выбирает способ выполнения.

Заметки организованы как самодостаточный курс: от реляционной модели до продвинутых конструкций. Все примеры используют PostgreSQL, но основная часть материала — стандартный SQL, применимый к любой СУБД. PostgreSQL-специфичные конструкции помечены в тексте, а крупные PG-расширения выделены в отдельную подпапку.

## Порядок изучения

Заметки выстроены по зависимостям: каждый следующий файл опирается на предыдущие.

### Основы

Фундамент, необходимый до любых запросов: как устроены данные, типы, NULL, выражения.

- [Реляционная модель](foundations/00-relational-model.md) — таблицы, строки, столбцы, отсутствие порядка
- [Типы данных и NULL](foundations/01-types-and-null.md) — числа, текст, даты, boolean, трёхзначная логика
- [Выражения](foundations/02-expressions.md) — CASE, COALESCE, NULLIF, CAST, приведение типов, функции даты и строк

### Запросы

Чтение данных — от простой фильтрации до оконных функций.

- [SELECT и фильтрация](querying/00-select-and-filtering.md) — SELECT, FROM, WHERE, операторы, LIKE/ILIKE, BETWEEN, IN
- [Сортировка и ограничение](querying/01-sorting-and-limiting.md) — ORDER BY, LIMIT/OFFSET, DISTINCT, DISTINCT ON
- [Агрегация](querying/02-aggregation.md) — COUNT/SUM/AVG/MIN/MAX, GROUP BY, HAVING, FILTER, string_agg/array_agg
- [Соединения (JOIN)](querying/03-joins.md) — псевдонимы таблиц, CROSS/INNER/LEFT/RIGHT/FULL, self-join, ON vs WHERE, USING, LATERAL
- [Расширенная группировка](querying/04-grouping-sets.md) — GROUPING SETS, ROLLUP, CUBE, функция GROUPING()
- [Подзапросы и CTE](querying/05-subqueries-and-cte.md) — скалярные, коррелированные, IN/EXISTS/ANY/ALL, NOT IN + NULL, WITH RECURSIVE
- [Операции над множествами](querying/06-set-operations.md) — UNION, INTERSECT, EXCEPT и их ALL-варианты
- [Оконные функции](querying/07-window-functions.md) — OVER, PARTITION BY, ранжирование, навигация, фреймы

### Определение структуры (DDL)

Как создавать и изменять таблицы.

- [Таблицы и типы](schema/00-tables-and-types.md) — CREATE/ALTER/DROP TABLE, типы данных, DEFAULT, IDENTITY/SERIAL
- [Ограничения](schema/01-constraints.md) — NOT NULL, UNIQUE, PK, FK, CHECK, каскады, EXCLUSION
- [Партиционирование](schema/02-partitioning.md) — RANGE, LIST, HASH-партиции, pruning
- [Представления](schema/03-views.md) — CREATE VIEW, материализованные представления
- [Индексы](schema/04-indexes.md) — CREATE INDEX, CONCURRENTLY, REINDEX, типы индексов, блокировки

### Изменение данных

- [DML](modification/00-dml.md) — INSERT, UPDATE, DELETE, TRUNCATE, RETURNING, UPSERT
- [Транзакции](modification/01-transactions.md) — BEGIN/COMMIT/ROLLBACK, SAVEPOINT, ссылка на [ACID](../acid.md)

### PostgreSQL: расширения стандартного SQL

Крупные возможности PostgreSQL, выходящие за рамки стандартного SQL.

- [JSONB](postgresql/00-jsonb.md) — операторы, функции, индексирование
- [Массивы и диапазоны](postgresql/01-arrays-and-ranges.md) — ARRAY, unnest, range types
- [Полнотекстовый поиск](postgresql/02-full-text-search.md) — tsvector, tsquery, GIN
- [Функции и процедуры](postgresql/03-functions-and-procedures.md) — CREATE FUNCTION, PL/pgSQL

## Как всё связано

**Чтение vs запись:** SQL чётко разделяет чтение (SELECT) и изменение (INSERT/UPDATE/DELETE). Запросы на чтение можно составлять произвольной сложности — соединения, подзапросы, оконные функции — без риска изменить данные. Команды изменения, наоборот, изменяют состояние и требуют транзакционного контроля.

**Декларативность vs контроль:** SQL описывает *что*, а не *как*. Это даёт СУБД свободу оптимизации, но лишает программиста прямого контроля над алгоритмами. Когда производительность критична, приходится понимать, как СУБД интерпретирует запрос — см. [планировщик PostgreSQL](../postgresql/query-processing/00-planner.md).

**Стандарт vs реализация:** большинство конструкций в этих заметках — стандартный SQL. PostgreSQL расширяет стандарт: JSONB, массивы, DISTINCT ON, FILTER, RETURNING, LATERAL — эти расширения помечены в тексте. При переходе на другую СУБД стандартная часть переносится, расширения требуют адаптации.

## См. также

- [PostgreSQL: внутреннее устройство](../postgresql/index.md) — как работает СУБД «под капотом» (MVCC, WAL, индексы, планировщик)
- [ACID](../acid.md) — транзакционный контракт, на который опирается SQL
- [Выбор хранилища](../../system-design/10-storage-selection.md) — когда SQL подходит, а когда нет
- [EXPLAIN и чтение планов запросов](../postgresql/query-processing/03-explain.md) — как проверить, что СУБД делает с вашим запросом

## Sources

- PostgreSQL Documentation (v16). <https://www.postgresql.org/docs/16/>
- SQL Standard (ISO/IEC 9075)
