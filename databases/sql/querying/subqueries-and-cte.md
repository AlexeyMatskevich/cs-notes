---
tags:
  - domain/sql
  - theme/data-representation
  - type/concept
aliases:
  - CTE
  - Common Table Expression
  - WITH RECURSIVE
  - Subquery
  - LATERAL
order: 9
---

# Подзапросы и CTE

**Предпосылки:** [соединения](joins.md) ([JOIN](joins.md)), [агрегация](aggregation.md) ([GROUP BY](aggregation.md), агрегатные функции).

← [Расширенная группировка](grouping-sets.md) | [Операции над множествами](set-operations.md) →

Иногда результат одного запроса нужен внутри другого. «Покажи сотрудников, чья зарплата выше средней» — средняя сама по себе результат запроса. Подзапрос (subquery) — запрос, вложенный в другой запрос. CTE (Common Table Expression) — именованный подзапрос, определяемый через WITH.

## Скалярный подзапрос

Скалярный (scalar) подзапрос возвращает **одно значение** — одну строку и один столбец:

```sql
SELECT name, salary
FROM employees
WHERE salary > (SELECT AVG(salary) FROM employees WHERE salary IS NOT NULL);
```

```
 name | salary
------+--------
 Анна |  90000
 Вера |  85000
```

Подзапрос `SELECT AVG(salary) ...` вычисляет 72000. Внешний запрос фильтрует строки, где `salary > 72000`. Скалярный подзапрос можно использовать в SELECT, WHERE, HAVING — везде, где ожидается одно значение.

## Подзапрос в FROM (производная таблица)

Подзапрос в FROM создаёт временную таблицу:

```sql
SELECT dept_stats.department_id, dept_stats.avg_salary
FROM (
    SELECT department_id, AVG(salary) AS avg_salary
    FROM employees
    WHERE salary IS NOT NULL
    GROUP BY department_id
) AS dept_stats
WHERE dept_stats.avg_salary > 70000;
```

```
 department_id | avg_salary
---------------+-----------
             1 |      87500
```

Подзапрос в FROM выполняется на шаге 1 [[databases/sql/querying/aggregation#полный-порядок-выполнения-запроса|порядка выполнения]] — он становится источником строк, как обычная таблица. Подзапрос в FROM обязательно имеет псевдоним (AS dept_stats).

## Коррелированные и некоррелированные подзапросы

**Некоррелированный** подзапрос не зависит от внешнего запроса — его можно выполнить отдельно. Пример выше (AVG(salary)) — некоррелированный.

**Коррелированный** подзапрос ссылается на столбцы внешнего запроса и выполняется **для каждой строки** внешнего запроса:

```sql
SELECT e.name, e.salary, e.department_id
FROM employees e
WHERE e.salary > (
    SELECT AVG(e2.salary)
    FROM employees e2
    WHERE e2.department_id = e.department_id
      AND e2.salary IS NOT NULL
);
```

```
 name | salary | department_id
------+--------+--------------
 Анна |  90000 |             1
 Глеб |  70000 |             2
```

Для каждого сотрудника подзапрос вычисляет среднюю зарплату **его** отдела. Анна (90000) выше средней по engineering (87500). Глеб (70000) выше средней по sales (65000).

## IN с подзапросом

IN проверяет, входит ли значение в результат подзапроса:

```sql
SELECT name
FROM employees
WHERE department_id IN (
    SELECT id FROM departments WHERE budget > 200000
);
```

```
 name
------
 Анна
 Борис
 Вера
 Глеб
 Дина
```

Подзапрос возвращает id отделов с бюджетом > 200000 (engineering=1, sales=2). Внешний запрос оставляет сотрудников этих отделов.

### NOT IN и ловушка с NULL

`NOT IN` с подзапросом, содержащим NULL, **никогда не вернёт TRUE**:

```sql
SELECT name
FROM employees
WHERE department_id NOT IN (SELECT department_id FROM employees);
```

Подзапрос возвращает `{1, 2, NULL}`. Для любого `department_id = X` условие `X NOT IN (1, 2, NULL)` раскрывается как `X <> 1 AND X <> 2 AND X <> NULL`. Последнее сравнение `X <> NULL` --> NULL ([[databases/sql/foundations/types-and-null#трёхзначная-логика|трёхзначная логика]]), и всё выражение --> NULL. Результат: **ноль строк**.

Защита: используйте `NOT EXISTS` вместо `NOT IN`, или добавляйте `WHERE ... IS NOT NULL` в подзапрос.

## EXISTS — проверка существования

EXISTS (англ. «существует») возвращает TRUE, если подзапрос вернул **хотя бы одну строку**:

```sql
SELECT d.name
FROM departments d
WHERE EXISTS (
    SELECT 1
    FROM employees e
    WHERE e.department_id = d.id AND e.salary > 80000
);
```

```
 name
-------------
 engineering
```

EXISTS не зависит от содержимого строк подзапроса — важен только факт «есть ли хотя бы одна строка». `SELECT 1` — конвенция, означающая «нам не важно, что именно возвращать».

EXISTS корректно работает с NULL: ему не нужно сравнивать значения, а только проверять наличие строк. Поэтому EXISTS безопаснее NOT IN при наличии NULL.

## ANY/ALL — сравнение с множеством

IN проверяет **равенство** со значениями из набора. Но задача может требовать другого сравнения: «Покажи сотрудников, зарабатывающих больше **каждого** из отдела продаж». IN проверяет `=`, а нужен `>`. Здесь нужны ANY и ALL.

ALL (англ. «все») — TRUE, если условие выполняется **для всех** значений из подзапроса:

```sql
SELECT name, salary
FROM employees
WHERE salary > ALL (SELECT salary FROM employees WHERE department_id = 2 AND salary IS NOT NULL);
```

Подзапрос возвращает зарплаты sales: `(60000, 70000)`. `salary > ALL (60000, 70000)` — TRUE, если зарплата больше **каждого** значения, то есть больше максимума (70000):

```
 name | salary
------+--------
 Анна |  90000
 Вера |  85000
```

ANY (англ. «любой») — TRUE, если условие выполняется **хотя бы для одного** значения. «Больше хотя бы одного из отдела продаж»:

```sql
SELECT name, salary
FROM employees
WHERE salary > ANY (SELECT salary FROM employees WHERE department_id = 2 AND salary IS NOT NULL);
```

`salary > ANY (60000, 70000)` — TRUE, если зарплата больше **хотя бы одного** значения, то есть больше минимума (60000):

```
 name | salary
------+--------
 Анна |  90000
 Вера |  85000
 Глеб |  70000
```

Мнемоника: `> ANY(набор)` ≈ `> MIN(набор)`, `> ALL(набор)` ≈ `> MAX(набор)`. `= ANY(набор)` эквивалентен `IN(набор)`.

При пустом подзапросе: `ANY` --> FALSE (не нашлось ни одного подходящего), `ALL` --> TRUE (условие выполняется для всех нуля элементов — vacuous truth, «пустая истина»).

## CTE — именованный подзапрос

CTE (Common Table Expression) определяется через WITH и даёт подзапросу имя:

```sql
WITH dept_avg AS (
    SELECT department_id, AVG(salary) AS avg_salary
    FROM employees
    WHERE salary IS NOT NULL
    GROUP BY department_id
)
SELECT e.name, e.salary, da.avg_salary
FROM employees e
JOIN dept_avg da ON e.department_id = da.department_id
WHERE e.salary > da.avg_salary;
```

```
 name | salary | avg_salary
------+--------+-----------
 Анна |  90000 |      87500
 Глеб |  70000 |      65000
```

CTE улучшает читаемость: сложный запрос разбивается на именованные блоки. CTE можно ссылаться несколько раз в основном запросе.

PostgreSQL с версии 12 может встроить нерекурсивный CTE в основной запрос — подробнее в [CTE в PostgreSQL](../../postgresql/query-processing/subqueries-and-cte.md). В PostgreSQL WITH может включать INSERT, UPDATE, DELETE — подробнее в [составных DML в PostgreSQL](../postgresql/compound-dml.md).

## WITH RECURSIVE — рекурсивные запросы

RECURSIVE (англ. «рекурсивный») позволяет CTE ссылаться на саму себя. Типичное применение — обход иерархий (дерево категорий, оргструктура).

Таблица сотрудников со ссылкой на руководителя:

```sql
CREATE TABLE staff (
    id         integer PRIMARY KEY,
    name       text NOT NULL,
    manager_id integer REFERENCES staff(id)
);

INSERT INTO staff VALUES
(1, 'Alice',   NULL),   -- CEO
(2, 'Bob',     1),      -- reports to Alice
(3, 'Charlie', 1),      -- reports to Alice
(4, 'Diana',   2),      -- reports to Bob
(5, 'Eve',     2),      -- reports to Bob
(6, 'Frank',   3);      -- reports to Charlie
```

Иерархия:

```
Alice (1)
+-- Bob (2)
|   +-- Diana (4)
|   +-- Eve (5)
+-- Charlie (3)
    +-- Frank (6)
```

Задача: показать всех подчинённых Alice — прямых и непрямых, на любой глубине. Через обычный JOIN можно найти прямых подчинённых (один уровень), подчинённых подчинённых (два JOIN), но глубина дерева заранее неизвестна.

```sql
WITH RECURSIVE subordinates AS (
    -- базовый случай: сама Alice
    SELECT id, name, manager_id, 1 AS level
    FROM staff
    WHERE id = 1

    UNION ALL

    -- рекурсивный шаг: подчинённые текущего уровня
    SELECT s.id, s.name, s.manager_id, sub.level + 1
    FROM staff s
    JOIN subordinates sub ON s.manager_id = sub.id
)
SELECT * FROM subordinates;
```

```
 id | name    | manager_id | level
----+---------+------------+------
  1 | Alice   |       NULL |     1
  2 | Bob     |          1 |     2
  3 | Charlie |          1 |     2
  4 | Diana   |          2 |     3
  5 | Eve     |          2 |     3
  6 | Frank   |          3 |     3
```

Пошагово:

```
Итерация 1 (базовый случай):
  -> Alice (id=1, level=1)

Итерация 2 (рекурсивный шаг):
  Ищем строки где manager_id = 1 (id Alice)
  -> Bob (id=2, level=2), Charlie (id=3, level=2)

Итерация 3:
  Ищем строки где manager_id IN (2, 3)
  -> Diana (id=4, level=3), Eve (id=5, level=3), Frank (id=6, level=3)

Итерация 4:
  Ищем строки где manager_id IN (4, 5, 6)
  -> ничего не найдено -> рекурсия останавливается
```

Структура WITH RECURSIVE всегда одинакова: **базовый случай** (anchor) — начальный набор строк. **UNION ALL** — соединяет результаты. **Рекурсивный шаг** — запрос, ссылающийся на имя CTE (`subordinates`). На каждой итерации он видит только строки, добавленные предыдущей итерацией. Рекурсия останавливается, когда рекурсивный шаг возвращает ноль строк.

### UNION ALL vs UNION в рекурсии

Для деревьев без циклов UNION ALL быстрее — дубликатов не будет. Если в данных возможны циклы (граф, а не дерево), UNION предотвратит бесконечную рекурсию: дубликат не добавится и процесс остановится. Дополнительная защита — ограничение глубины: `WHERE sub.level < 10` в рекурсивном шаге.

## LATERAL — подзапрос с доступом к внешним строкам

CTE с ROW_NUMBER нумерует **все** строки во **всех** группах, потом фильтрует — на миллионах строк работа избыточна. LATERAL подходит к задаче иначе: для каждой строки внешней таблицы выполняет отдельный подзапрос с LIMIT.

«Покажи топ-2 по зарплате в каждом отделе»:

```sql
SELECT d.name AS dept, top.employee_name, top.salary
FROM departments d
LEFT JOIN LATERAL (
    SELECT e.name AS employee_name, e.salary
    FROM employees e
    WHERE e.department_id = d.id
    ORDER BY e.salary DESC NULLS LAST
    LIMIT 2
) top ON true;
```

```
 dept        | employee_name | salary
-------------+---------------+--------
 engineering | Анна          |  90000
 engineering | Вера          |  85000
 sales       | Глеб          |  70000
 sales       | Борис         |  60000
 hr          | NULL          |   NULL
```

LATERAL (англ. «боковой», стандарт SQL:2003) позволяет подзапросу в FROM ссылаться на столбцы предшествующих таблиц — как вложенный цикл, где для каждой строки внешней таблицы выполняется подзапрос. Без LATERAL ссылка на `d.id` из подзапроса в FROM была бы ошибкой.

LEFT JOIN LATERAL сохраняет `hr`, у которого нет сотрудников. Это коррелированный подзапрос в FROM — тот же механизм, что в коррелированных подзапросах выше, но здесь подзапрос порождает набор строк, а не одно значение.

LATERAL незаменим там, где нужно **порождать строки** из значения каждой строки: развернуть массив, вызвать `generate_series`, передать параметр в табличную функцию.

### ROW_NUMBER vs LATERAL

ROW_NUMBER + CTE — стандартный и универсальный способ: нумерует все строки, фильтрует по номеру. При больших объёмах нумерация всех строк создаёт overhead. LATERAL с LIMIT обращается только к нужным строкам каждой группы — при наличии индекса по `(department_id, salary DESC)` выполняет N отдельных index scan'ов вместо одного полного прохода. Для top-1 PostgreSQL предлагает ещё более компактный вариант — [DISTINCT ON](../postgresql/distinct-on.md).

## Sources

- PostgreSQL Documentation (v16): Subqueries, WITH (CTE). <https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-WITH>
- PostgreSQL Documentation (v16): EXISTS, IN, ANY, ALL. <https://www.postgresql.org/docs/16/functions-subquery.html>
- PostgreSQL Documentation (v16): LATERAL. <https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-LATERAL>

---

← [Расширенная группировка](grouping-sets.md) | [Операции над множествами](set-operations.md) →
