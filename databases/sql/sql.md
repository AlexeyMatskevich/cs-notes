---
tags:
  - domain/sql
  - type/overview
aliases:
  - SQL
---

# SQL

**Предпосылки:** базовое программирование (переменные, типы, функции, условия, циклы).

SQL — декларативный язык для работы с реляционными базами данных. В отличие от императивных языков, где программист описывает *как* вычислить результат, SQL описывает *что* нужно получить, а СУБД сама выбирает способ выполнения.

Заметки организованы как самодостаточный курс: от реляционной модели до продвинутых конструкций. Все примеры используют PostgreSQL, но основная часть материала — стандартный SQL, применимый к любой СУБД. PostgreSQL-специфичные конструкции помечены в тексте, а крупные PG-расширения выделены в [отдельную подпапку](postgresql/pg-extensions.md).

## Порядок изучения

Секции идут по зависимостям: основы → запросы → DDL → модификация. Внутри секций файлы в основном выстроены цепочкой, но не всегда — нормализация ответвляется от реляционной модели, а не от выражений.

### Основы

Фундамент, необходимый до любых запросов: как устроены данные, типы, NULL, выражения.

- [Реляционная модель](foundations/relational-model.md) — модель Кодда: отношения, реляционная алгебра, декларативность SQL
- [Типы данных и NULL](foundations/types-and-null.md) — числа, текст, даты, boolean, трёхзначная логика
- [Выражения](foundations/expressions.md) — CASE, COALESCE, NULLIF, CAST, приведение типов, функции даты и строк

Нормализация возвращается к [реляционной модели](foundations/relational-model.md) и отвечает на вопрос «как далеко разделять таблицы». Она не зависит от выражений — её можно читать сразу после реляционной модели.

- [Нормализация](foundations/normalization.md) — функциональные зависимости, 1НФ–5НФ

### Запросы

Чтение данных — от простой фильтрации до оконных функций.

- [SELECT и фильтрация](querying/select-and-filtering.md) — SELECT, FROM, WHERE, операторы, LIKE/ILIKE, BETWEEN, IN
- [Сортировка и ограничение](querying/sorting-and-limiting.md) — ORDER BY, LIMIT/OFFSET, DISTINCT
- [Агрегация](querying/aggregation.md) — COUNT/SUM/AVG/MIN/MAX, GROUP BY, HAVING, FILTER, string_agg/array_agg
- [Соединения (JOIN)](querying/joins.md) — псевдонимы таблиц, CROSS/INNER/LEFT/RIGHT/FULL, self-join, ON vs WHERE, USING
- [Расширенная группировка](querying/grouping-sets.md) — GROUPING SETS, ROLLUP, CUBE, функция GROUPING()
- [Подзапросы и CTE](querying/subqueries-and-cte.md) — скалярные, коррелированные, IN/EXISTS/ANY/ALL, NOT IN + NULL, LATERAL, WITH RECURSIVE
- [Операции над множествами](querying/set-operations.md) — UNION, INTERSECT, EXCEPT и их ALL-варианты
- [Оконные функции](querying/window-functions.md) — OVER, PARTITION BY, ранжирование, навигация, фреймы

### Определение структуры (DDL)

Как создавать и изменять таблицы.

- [Таблицы и типы](schema/tables-and-types.md) — CREATE/ALTER/DROP TABLE, типы данных, DEFAULT, IDENTITY
- [Ограничения](schema/constraints.md) — NOT NULL, UNIQUE, PK, FK, CHECK, каскады
- [Партиционирование](schema/partitioning.md) — логическая таблица из физических частей, выбор ключа, trade-offs
- [Представления](schema/views.md) — CREATE VIEW, обновляемые представления, view как слой доступа
- [Индексы](schema/indexes.md) — CREATE INDEX, составные, частичные, покрывающие, expression-индексы

### Пагинация

Пагинация зависит от знания индексов, поэтому следует после DDL.

- [Пагинация](querying/pagination.md) — OFFSET vs keyset, стабильный порядок, стоимость глубоких страниц

### Изменение данных

DML не зависит от пагинации, но в порядке изучения следует после неё: к этому моменту читатель знает и чтение, и структуру таблиц.

- [DML](modification/dml.md) — INSERT, UPDATE, DELETE, TRUNCATE
- [Транзакции](modification/transactions.md) — BEGIN/COMMIT/ROLLBACK, SAVEPOINT, уровни изоляции, ссылка на [ACID](../acid.md)
- [Составные DML-операции](modification/compound-dml.md) — INSERT...SELECT, VALUES, MERGE

### PostgreSQL: расширения стандартного SQL

Крупные возможности PostgreSQL, выходящие за рамки стандартного SQL — типы данных, DDL-конструкции, query-фичи.

→ [PostgreSQL: расширения SQL](postgresql/pg-extensions.md)

### Миграции

Безопасное изменение схемы на рабочей базе данных с данными и трафиком. Требует знания DDL, транзакций и [PG-специфики](postgresql/pg-extensions.md) (блокировки, CONCURRENTLY).

→ [Миграции](../migrations/migrations.md)

## Как всё связано

**Чтение vs запись:** SQL чётко разделяет чтение (SELECT) и изменение (INSERT/UPDATE/DELETE). Запросы на чтение можно составлять произвольной сложности — соединения, подзапросы, оконные функции — без риска изменить данные. Команды изменения, наоборот, изменяют состояние и требуют транзакционного контроля.

**Декларативность vs контроль:** SQL описывает *что*, а не *как*. Это даёт СУБД свободу оптимизации, но лишает программиста прямого контроля над алгоритмами. Когда производительность критична, приходится понимать, как СУБД интерпретирует запрос — см. [планировщик PostgreSQL](../postgresql/query-processing/planner.md).

**Стандарт vs реализация:** большинство конструкций в этих заметках — стандартный SQL. PostgreSQL расширяет стандарт: JSONB, массивы, FTS, DISTINCT ON — эти расширения вынесены в [отдельный раздел](postgresql/pg-extensions.md). При переходе на другую СУБД стандартная часть переносится, расширения требуют адаптации.

## См. также

- [PostgreSQL: внутреннее устройство](../postgresql/postgresql.md) — как работает СУБД «под капотом» (MVCC, WAL, индексы, планировщик)
- [ACID](../acid.md) — транзакционный контракт, на который опирается SQL
- [Выбор хранилища](../../system-design/storage-selection.md) — когда SQL подходит, а когда нет
- [EXPLAIN и чтение планов запросов](../postgresql/query-processing/explain.md) — как проверить, что СУБД делает с вашим запросом

## Sources

- PostgreSQL Documentation (v16). <https://www.postgresql.org/docs/16/>
- SQL Standard (ISO/IEC 9075)
