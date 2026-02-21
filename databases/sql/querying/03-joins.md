# Соединения (JOIN)

**Предпосылки:** [агрегация](02-aggregation.md) (GROUP BY, HAVING, pipeline до шага 8).

← [Агрегация](02-aggregation.md) | [Расширенная группировка](04-grouping-sets.md) →

Все предыдущие запросы работали с одной таблицей. Но в реальных базах данные **разделены** по нескольким таблицам: сотрудники — отдельно, отделы — отдельно. Связь между ними — через общее значение (ключ). JOIN (англ. «соединение, объединение») комбинирует строки из разных таблиц.

Две таблицы:

```
departments:
 id | name        | budget
----+-------------+--------
  1 | engineering | 500000
  2 | sales       | 300000
  3 | hr          | 150000

employees:
 id | name     | department_id | salary | hire_date
----+----------+---------------+--------+------------
  1 | Анна     |             1 |  90000 | 2021-03-15
  2 | Борис    |             2 |  60000 | 2020-07-01
  3 | Вера     |             1 |  85000 | 2022-01-10
  4 | Глеб     |             2 |  70000 | 2019-11-20
  5 | Дина     |             1 |  NULL  | 2023-06-01
  6 | Евгений  |          NULL |  55000 | 2024-02-01
```

Отдел `hr` не имеет сотрудников. Евгений не привязан к отделу (`department_id = NULL`).

## Псевдонимы таблиц

При работе с несколькими таблицами удобно давать им короткие имена. Псевдоним (alias) задаётся после имени таблицы в FROM:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
JOIN departments d ON e.department_id = d.id;
```

`e` — псевдоним для `employees`, `d` — для `departments`. Ключевое слово AS для табличных псевдонимов **необязательно**: `FROM employees AS e` и `FROM employees e` эквивалентны. Псевдонимы обязательны при self-join, где одна таблица используется дважды.

## CROSS JOIN — декартово произведение

Самый простой способ скомбинировать две таблицы — взять каждую строку первой и приклеить к каждой строке второй. 6 сотрудников x 3 отдела = 18 строк:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e CROSS JOIN departments d;
```

Большинство из 18 комбинаций бессмысленны — Анна соединена с каждым отделом, хотя работает только в engineering. CROSS JOIN важен как **концепция**: все остальные JOIN — это CROSS JOIN плюс фильтрация.

## INNER JOIN — осмысленное соединение

INNER JOIN (или просто JOIN) оставляет только строки, для которых условие ON вернуло TRUE:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
JOIN departments d ON e.department_id = d.id;
```

```
 name  | dept_name
-------+-------------
 Анна  | engineering
 Борис | sales
 Вера  | engineering
 Глеб  | sales
 Дина  | engineering
```

Кого здесь нет? **Евгения** — его `department_id` = NULL, и `NULL = 1`, `NULL = 2`, `NULL = 3` дают NULL. Ни одна комбинация не TRUE. **Отдела hr** — ни один сотрудник не имеет `department_id = 3`. INNER JOIN возвращает только строки с парой в обеих таблицах.

## LEFT JOIN — сохранение строк из левой таблицы

LEFT JOIN (полное название — LEFT OUTER JOIN) гарантирует, что **все строки левой таблицы** попадут в результат. Если пара не нашлась — столбцы правой таблицы заполняются NULL:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id;
```

```
 name     | dept_name
----------+-------------
 Анна     | engineering
 Борис    | sales
 Вера     | engineering
 Глеб     | sales
 Дина     | engineering
 Евгений  | NULL
```

Евгений вернулся — его отдел неизвестен, пары нет, но LEFT JOIN сохранил его. Столбцы из `departments` заполнены NULL.

Отдел `hr` по-прежнему отсутствует — он из правой таблицы, а LEFT JOIN защищает только левую.

## RIGHT JOIN и FULL OUTER JOIN

RIGHT JOIN — зеркало LEFT JOIN: сохраняет все строки правой таблицы. На практике используется редко — любой RIGHT JOIN можно переписать как LEFT JOIN, поменяв таблицы местами.

FULL OUTER JOIN — сохраняет все строки из обеих таблиц:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
FULL OUTER JOIN departments d ON e.department_id = d.id;
```

```
 name     | dept_name
----------+-------------
 Анна     | engineering
 Борис    | sales
 Вера     | engineering
 Глеб     | sales
 Дина     | engineering
 Евгений  | NULL
 NULL     | hr
```

И Евгений, и `hr` в результате.

```
INNER JOIN       -- только строки с парой в обеих таблицах
LEFT JOIN        -- все из левой + пары из правой (или NULL)
RIGHT JOIN       -- все из правой + пары из левой (или NULL)
FULL OUTER JOIN  -- все из обеих (NULL где нет пары)
```

## Паттерн «найти сирот»

LEFT JOIN + WHERE ... IS NULL — способ найти строки без пары:

```sql
SELECT d.name
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id
WHERE e.id IS NULL;
```

```
 name
------
 hr
```

LEFT JOIN сохраняет все отделы. Для `hr` столбцы `employees` — NULL. Фильтр `WHERE e.id IS NULL` оставляет только такие строки.

## Self-join — таблица соединяется сама с собой

Иногда нужно сравнить строки **внутри одной таблицы**. Пример: пары сотрудников из одного отдела:

```sql
SELECT e1.name, e2.name, e1.department_id
FROM employees e1
JOIN employees e2 ON e1.department_id = e2.department_id
WHERE e1.id < e2.id;
```

```
 name  | name | department_id
-------+------+--------------
 Анна  | Вера |            1
 Анна  | Дина |            1
 Вера  | Дина |            1
 Борис | Глеб |            2
```

`e1.id < e2.id` убирает дубликаты и «самопары». Евгений не попал — `NULL = NULL` в ON даёт NULL.

## ON vs WHERE при LEFT JOIN

При INNER JOIN условие в ON и в WHERE взаимозаменяемы — оптимизатор строит одинаковый план. При LEFT JOIN — **нет**:

```sql
-- Вариант A: условие в ON
SELECT e.name, d.name AS dept_name
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id AND d.budget > 200000;

-- Вариант B: условие в WHERE
SELECT e.name, d.name AS dept_name
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
WHERE d.budget > 200000;
```

Вариант A: ON не нашёл пару для Дины (engineering, budget=500000, пара есть) — а для `hr` нет сотрудника. Но если бы `budget` не проходил условие, LEFT JOIN подставил бы NULL. Все сотрудники остаются в результате.

Вариант B: LEFT JOIN подставил данные отделов, потом WHERE отсеивает строки, где `d.budget` NULL или <= 200000. Евгений (dept NULL) и сотрудники отделов с малым бюджетом **исчезают** — LEFT JOIN фактически превращается в INNER JOIN.

Правило: при LEFT JOIN условия на правую таблицу ставятся **в ON**, а не в WHERE, если нужно сохранить строки левой таблицы.

## USING — когда столбцы совпадают по имени

Если столбец соединения одинаково назван в обеих таблицах, вместо ON можно использовать USING:

```sql
SELECT e.name, d.name
FROM employees e
JOIN departments d USING (department_id);
```

USING(department_id) эквивалентен `ON e.department_id = d.department_id`. Столбец `department_id` появляется в результате один раз (а не дважды, как при ON).

## NATURAL JOIN — неявное соединение

NATURAL JOIN автоматически находит все столбцы с одинаковыми именами в обеих таблицах и соединяет по ним. Если в `employees` и `departments` есть общий столбец `department_id`, `NATURAL JOIN` использует его как условие.

NATURAL JOIN зависит от **имён столбцов**, а не от намерения разработчика. Если кто-то добавит столбец `name` в `departments`, NATURAL JOIN молча начнёт соединять и по `department_id`, и по `name` — запрос вернёт неправильный результат без ошибки. Правило: NATURAL JOIN не используется в production-коде. Всегда явный ON или USING.

## LATERAL — подзапрос с доступом к текущей строке

LATERAL (англ. «боковой») позволяет подзапросу в FROM ссылаться на столбцы предшествующих таблиц. Это как вложенный цикл: для каждой строки левой таблицы выполняется подзапрос.

```sql
SELECT d.name, top.employee_name, top.salary
FROM departments d
LEFT JOIN LATERAL (
    SELECT e.name AS employee_name, e.salary
    FROM employees e
    WHERE e.department_id = d.id
    ORDER BY e.salary DESC NULLS LAST
    LIMIT 1
) top ON true;
```

```
 name        | employee_name | salary
-------------+---------------+--------
 engineering | Анна          |  90000
 sales       | Глеб          |  70000
 hr          | NULL          |   NULL
```

Для каждого отдела подзапрос находит сотрудника с максимальной зарплатой. LATERAL ссылается на `d.id` из внешней таблицы — без LATERAL это было бы ошибкой. LEFT JOIN LATERAL сохраняет `hr`, у которого нет сотрудников.

Подробнее о коррелированных подзапросах — в [подзапросах и CTE](05-subqueries-and-cte.md).

LATERAL уникален в ситуациях, где для каждой строки нужно вызвать **set-returning функцию** — функцию, возвращающую несколько строк. Допустим, у сотрудников есть JSONB-поле `skills`:

```sql
-- предположим: employees.skills jsonb, например '["sql", "python", "go"]'
SELECT e.name, skill
FROM employees e
CROSS JOIN LATERAL jsonb_array_elements_text(e.skills) AS skill;
```

```
 name  | skill
-------+--------
 Анна  | sql
 Анна  | python
 Анна  | go
 Борис | sql
 Борис | java
```

`jsonb_array_elements_text` принимает массив конкретного сотрудника и возвращает набор строк — по одной на каждый элемент. Без LATERAL подзапрос в FROM не может ссылаться на `e.skills`.

**LATERAL vs оконные функции.** Top-N внутри группы (как пример выше с лучшим сотрудником в отделе) можно решить и через `ROW_NUMBER() OVER (PARTITION BY ...)` — часто это проще. LATERAL незаменим там, где нужно **порождать строки** из значения каждой строки: развернуть массив, вызвать `generate_series`, передать параметр в табличную функцию.

## NULL в контексте JOIN

NULL в столбце соединения означает «нет пары»: `NULL = значение` даёт NULL, условие ON не TRUE, строка не соединяется. При INNER JOIN такая строка исчезает. При LEFT JOIN — сохраняется с NULL в столбцах правой таблицы.

## Pipeline: расширение FROM

FROM расширяется на шаге 1:

```
1. FROM t1 JOIN t2 ON ...  -- соединение таблиц, ON на шаге 1
2. WHERE                   -- фильтрация строк (после соединения)
3. GROUP BY                -- группировка
4. HAVING                  -- фильтрация групп
5. SELECT                  -- вычисление выражений
6. DISTINCT                -- дедупликация
7. ORDER BY                -- сортировка
8. LIMIT/OFFSET            -- обрезка
```

ON выполняется на шаге 1 (до WHERE). При LEFT JOIN ON и WHERE **неэквивалентны** для условий на правую таблицу.

## Sources

- PostgreSQL Documentation (v16): JOIN, LATERAL. <https://www.postgresql.org/docs/16/sql-select.html>
- PostgreSQL Documentation (v16): Join Types. <https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-JOIN>

---

← [Агрегация](02-aggregation.md) | [Расширенная группировка](04-grouping-sets.md) →
