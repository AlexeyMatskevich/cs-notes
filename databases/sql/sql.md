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

Заметки организованы как самодостаточный курс: от реляционной модели до продвинутых конструкций. Все примеры используют PostgreSQL, но основная часть материала — стандартный SQL, применимый к любой СУБД. PostgreSQL-специфичные конструкции помечены в тексте, а крупные PG-расширения выделены в [[databases/sql/postgresql/pg-extensions|отдельную подпапку]].

## Порядок изучения

Секции идут по зависимостям: основы → запросы → DDL → модификация. Внутри секций файлы в основном выстроены цепочкой, но не всегда — нормализация ответвляется от реляционной модели, а не от выражений.

### Основы

Фундамент, необходимый до любых запросов: как устроены данные, типы, NULL, выражения.

- [[databases/sql/foundations/relational-model|Реляционная модель]] — модель Кодда: отношения, реляционная алгебра, декларативность SQL
- [[databases/sql/foundations/types-and-null|Типы данных и NULL]] — числа, текст, даты, boolean, трёхзначная логика
- [[databases/sql/foundations/expressions|Выражения]] — CASE, COALESCE, NULLIF, CAST, приведение типов, функции даты и строк

Нормализация возвращается к [[databases/sql/foundations/relational-model|реляционной модели]] и отвечает на вопрос «как далеко разделять таблицы». Она не зависит от выражений — её можно читать сразу после реляционной модели.

- [[databases/sql/foundations/normalization|Нормализация]] — функциональные зависимости, 1НФ–5НФ

### Запросы

Чтение данных — от простой фильтрации до оконных функций.

- [[databases/sql/querying/select-and-filtering|SELECT и фильтрация]] — SELECT, FROM, WHERE, операторы, LIKE/ILIKE, BETWEEN, IN
- [[databases/sql/querying/sorting-and-limiting|Сортировка и ограничение]] — ORDER BY, LIMIT/OFFSET, DISTINCT
- [[databases/sql/querying/aggregation|Агрегация]] — COUNT/SUM/AVG/MIN/MAX, GROUP BY, HAVING, FILTER, string_agg/array_agg
- [[databases/sql/querying/joins|Соединения (JOIN)]] — псевдонимы таблиц, CROSS/INNER/LEFT/RIGHT/FULL, self-join, ON vs WHERE, USING
- [[databases/sql/querying/grouping-sets|Расширенная группировка]] — GROUPING SETS, ROLLUP, CUBE, функция GROUPING()
- [[databases/sql/querying/subqueries-and-cte|Подзапросы и CTE]] — скалярные, коррелированные, IN/EXISTS/ANY/ALL, NOT IN + NULL, LATERAL, WITH RECURSIVE
- [[databases/sql/querying/set-operations|Операции над множествами]] — UNION, INTERSECT, EXCEPT и их ALL-варианты
- [[databases/sql/querying/window-functions|Оконные функции]] — OVER, PARTITION BY, ранжирование, навигация, фреймы

### Определение структуры (DDL)

Как создавать и изменять таблицы.

- [[databases/sql/schema/tables-and-types|Таблицы и типы]] — CREATE/ALTER/DROP TABLE, типы данных, DEFAULT, IDENTITY
- [[databases/sql/schema/constraints|Ограничения]] — NOT NULL, UNIQUE, PK, FK, CHECK, каскады
- [[databases/sql/schema/partitioning|Партиционирование]] — логическая таблица из физических частей, выбор ключа, trade-offs
- [[databases/sql/schema/views|Представления]] — CREATE VIEW, обновляемые представления, view как слой доступа
- [[databases/sql/schema/indexes|Индексы]] — CREATE INDEX, составные, частичные, покрывающие, expression-индексы

### Пагинация

Пагинация зависит от знания индексов, поэтому следует после DDL.

- [[databases/sql/querying/pagination|Пагинация]] — OFFSET vs keyset, стабильный порядок, стоимость глубоких страниц

### Изменение данных

DML не зависит от пагинации, но в порядке изучения следует после неё: к этому моменту читатель знает и чтение, и структуру таблиц.

- [[databases/sql/modification/dml|DML]] — INSERT, UPDATE, DELETE, TRUNCATE
- [[databases/sql/modification/transactions|Транзакции]] — BEGIN/COMMIT/ROLLBACK, SAVEPOINT, уровни изоляции, ссылка на [ACID](../acid.md)
- [[databases/sql/modification/compound-dml|Составные DML-операции]] — INSERT...SELECT, VALUES, MERGE

### PostgreSQL: расширения стандартного SQL

Крупные возможности PostgreSQL, выходящие за рамки стандартного SQL — типы данных, DDL-конструкции, query-фичи.

→ [[databases/sql/postgresql/pg-extensions|PostgreSQL: расширения SQL]]

### Миграции

Безопасное изменение схемы на рабочей базе данных с данными и трафиком. Требует знания DDL, транзакций и [[databases/sql/postgresql/pg-extensions|PG-специфики]] (блокировки, CONCURRENTLY).

→ [Миграции](../migrations/migrations.md)

## Как всё связано

**Чтение vs запись:** SQL чётко разделяет чтение (SELECT) и изменение (INSERT/UPDATE/DELETE). Запросы на чтение можно составлять произвольной сложности — соединения, подзапросы, оконные функции — без риска изменить данные. Команды изменения, наоборот, изменяют состояние и требуют транзакционного контроля.

**Декларативность vs контроль:** SQL описывает *что*, а не *как*. Это даёт СУБД свободу оптимизации, но лишает программиста прямого контроля над алгоритмами. Когда производительность критична, приходится понимать, как СУБД интерпретирует запрос — см. [планировщик PostgreSQL](../postgresql/query-processing/planner.md).

**Стандарт vs реализация:** большинство конструкций в этих заметках — стандартный SQL. PostgreSQL расширяет стандарт: JSONB, массивы, FTS, DISTINCT ON — эти расширения вынесены в [[databases/sql/postgresql/pg-extensions|отдельный раздел]]. При переходе на другую СУБД стандартная часть переносится, расширения требуют адаптации.

## См. также

- [PostgreSQL: внутреннее устройство](../postgresql/postgresql.md) — как работает СУБД «под капотом» (MVCC, WAL, индексы, планировщик)
- [ACID](../acid.md) — транзакционный контракт, на который опирается SQL
- [Выбор хранилища](../../system-design/storage-selection.md) — когда SQL подходит, а когда нет
- [EXPLAIN и чтение планов запросов](../postgresql/query-processing/explain.md) — как проверить, что СУБД делает с вашим запросом

## Sources

- PostgreSQL Documentation (v16). <https://www.postgresql.org/docs/16/>
- SQL Standard (ISO/IEC 9075)
