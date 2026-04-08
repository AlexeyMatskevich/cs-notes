---
tags:
  - domain/sql
  - theme/data-representation
  - type/concept
aliases:
  - SELECT
  - WHERE
  - LIKE
  - BETWEEN
  - IN
order: 4
---

# SELECT и фильтрация

> [!info]- Предпосылки
> [реляционная модель](../foundations/relational-model.md), [типы данных и NULL](../foundations/types-and-null.md), [выражения](../foundations/expressions.md).

← [Выражения](../foundations/expressions.md) | [Сортировка и ограничение](sorting-and-limiting.md) →

Первый день аналитика в компании. Менеджер задаёт вопросы, каждый специфичнее предыдущего — текущих инструментов не хватает, и приходится изучать новые. Все вопросы обращены к таблице `employees`:

```
 id | name     | department_id | salary | hire_date
----+----------+---------------+--------+------------
  1 | Анна     |             1 |  90000 | 2021-03-15
  2 | Борис    |             2 |  60000 | 2020-07-01
  3 | Вера     |             1 |  85000 | 2022-01-10
  4 | Глеб     |             2 |  70000 | 2019-11-20
  5 | Дина     |             1 |  NULL  | 2023-06-01
  6 | Евгений  |          NULL |  55000 | 2024-02-01
```

## Покажи всех сотрудников

SELECT (англ. «выбрать, отобрать») определяет, какие столбцы показать в результате. FROM (англ. «из, откуда») указывает таблицу-источник.

```sql
SELECT name, salary
FROM employees;
```

```
 name     | salary
----------+--------
 Анна     |  90000
 Борис    |  60000
 Вера     |  85000
 Глеб     |  70000
 Дина     |  NULL
 Евгений  |  55000
```

Звёздочка `*` означает «все столбцы»: `SELECT * FROM employees`. Результат запроса — тоже таблица, у неё есть столбцы и строки. Этот факт станет критически важным при изучении подзапросов.

SELECT работает как **проекция**: из всех столбцов выбираются только нужные.

## Годовая зарплата — выражения и AS

«Покажи годовую зарплату». В таблице хранится месячная — нужно вычислить:

```sql
SELECT name, salary * 12 AS annual_salary
FROM employees;
```

```
 name     | annual_salary
----------+--------------
 Анна     |      1080000
 Борис    |       720000
 Вера     |      1020000
 Глеб     |       840000
 Дина     |         NULL
 Евгений  |       660000
```

У Дины `salary` — NULL, поэтому `NULL * 12` = NULL. AS (англ. «как») задаёт псевдоним столбца. Для выражений без AS PostgreSQL сгенерирует имя автоматически (обычно `?column?`).

## Высокооплачиваемые — первая ошибка

«Покажи сотрудников с годовой зарплатой больше 800000». Попробуем:

```sql
SELECT name, salary * 12 AS annual_salary
FROM employees
WHERE annual_salary > 800000;
```

Ошибка: `column "annual_salary" does not exist`. Почему?

## Логический порядок выполнения

Запрос **пишется** в порядке SELECT → FROM → WHERE, но SQL **выполняет** его иначе:

```
1. FROM employees              -- берём все строки из таблицы
2. WHERE department_id = 1     -- фильтруем, оставляем только TRUE
3. SELECT name, salary         -- выбираем нужные столбцы
```

FROM → WHERE → SELECT. WHERE выполняется **до** SELECT, поэтому псевдоним `annual_salary` ещё не существует. В WHERE придётся повторить выражение:

```sql
WHERE salary * 12 > 800000
```

Этот pipeline будет расширяться по мере изучения новых конструкций.

## Только инженеры — WHERE и сравнения

«Покажи только сотрудников engineering-отдела». WHERE (англ. «где», в смысле «при каком условии») отбирает строки, для которых условие вернуло TRUE:

```sql
SELECT name, salary
FROM employees
WHERE department_id = 1;
```

```
 name  | salary
-------+--------
 Анна  |  90000
 Вера  |  85000
 Дина  |  NULL
```

Евгений (`department_id = NULL`) не попал: `NULL = 1` дало NULL, строка отсеяна. WHERE пропускает строку **только при TRUE** — и NULL, и FALSE отсеиваются одинаково.

### Операторы сравнения

`=` (равно), `<>` или `!=` (не равно), `<`, `>`, `<=`, `>=`. Равенство — `=`, не `==`. Условия комбинируются через `AND`, `OR`, `NOT` — их поведение с NULL описано в [типах и NULL](../foundations/types-and-null.md#логические-операторы-и-null).

```sql
SELECT name, salary
FROM employees
WHERE department_id = 1 AND salary > 80000;
```

```
 name | salary
------+--------
 Анна |  90000
 Вера |  85000
```

Дина не попала: `department_id = 1` — TRUE, но `NULL > 80000` — NULL. `TRUE AND NULL` --> NULL, строка отсеяна.

## Где Дина? — NULL в фильтрации

«Покажи, у кого зарплата не 90000». Ожидание: все, кроме Анны. Реальность:

```sql
SELECT name, salary FROM employees WHERE salary <> 90000;
```

```
 name     | salary
----------+--------
 Борис    |  60000
 Вера     |  85000
 Глеб     |  70000
 Евгений  |  55000
```

Дина не попала: `NULL <> 90000` --> NULL. **NULL проваливает любое сравнение, и строка молча исчезает из результата.** Для включения строк с неизвестными значениями нужно явное `OR salary IS NULL`. Проверить NULL можно только через `IS NULL` и `IS NOT NULL`:

```sql
WHERE salary <> 90000 OR salary IS NULL
```

## Зарплата от 60k до 85k — BETWEEN

«Покажи сотрудников с зарплатой от 60 до 85 тысяч». Можно записать через два сравнения: `salary >= 60000 AND salary <= 85000`. BETWEEN (англ. «между») — короткая запись того же:

```sql
SELECT name, salary
FROM employees
WHERE salary BETWEEN 60000 AND 85000;
```

```
 name  | salary
-------+--------
 Борис |  60000
 Вера  |  85000
 Глеб  |  70000
```

Границы **включаются** с обеих сторон.

Предупреждение для дат: `created_at BETWEEN '2024-01-01' AND '2024-12-31'` с типом `timestamp` превращает правую границу в `'2024-12-31 00:00:00'`, и события после полуночи 31 декабря не попадут. С типом `date` проблемы нет.

## Инженеры или продажники — IN

«Покажи сотрудников из engineering или sales». Можно через `department_id = 1 OR department_id = 2`. С тремя отделами — три OR. С десятью — нечитаемо.

IN (англ. «в, среди») проверяет, входит ли значение в список:

```sql
SELECT name, department_id
FROM employees
WHERE department_id IN (1, 2);
```

```
 name  | department_id
-------+--------------
 Анна  |            1
 Борис |            2
 Вера  |            1
 Глеб  |            2
 Дина  |            1
```

`IN (1, 2)` эквивалентен `department_id = 1 OR department_id = 2`. Евгений (`department_id = NULL`) не попал — `NULL = 1 OR NULL = 2` --> `NULL OR NULL` --> NULL.

IN также работает с подзапросами — подробнее в [подзапросах и CTE](subqueries-and-cte.md).

## Имя на А — LIKE

«Покажи сотрудников, чьё имя начинается на А». LIKE (англ. «похожий на») сравнивает строку с шаблоном. Два спецсимвола: `%` — любое количество символов, `_` — ровно один символ.

```sql
SELECT name FROM employees WHERE name LIKE 'А%';
```

```
 name
------
 Анна
```

В PostgreSQL LIKE регистрозависим: `'анна' LIKE 'А%'` — FALSE. Для регистронезависимого поиска PostgreSQL предоставляет ILIKE:

```sql
SELECT name FROM employees WHERE name ILIKE 'а%';
```

ILIKE — специфика PostgreSQL. В стандартном SQL регистронезависимый поиск делается через `LOWER(name) LIKE LOWER('а%')`.

## Сложный паттерн — регулярные выражения

LIKE ограничен двумя спецсимволами. Для сложных шаблонов PostgreSQL поддерживает полноценные регулярные выражения через оператор `~`:

```sql
SELECT name FROM employees WHERE name ~ '(ер|ор)';
```

Четыре варианта оператора:

```
~   -- совпадение (регистрозависимо)
~*  -- совпадение (регистроНЕзависимо)
!~  -- НЕ совпадает (регистрозависимо)
!~* -- НЕ совпадает (регистроНЕзависимо)
```

В стандарте SQL есть `SIMILAR TO`, но он менее мощный и почти не используется на практике.

Для производительности: LIKE с шаблоном `'prefix%'` может использовать индекс на столбце. Регулярные выражения и LIKE с `'%substring%'` требуют специальных индексов или [полнотекстового поиска](../postgresql/full-text-search.md) — подробнее в [индексах](../schema/indexes.md).

> [!info]- Задача: сотрудники без отдела с зарплатой ниже средней
> **Частая ошибка:**
> ```sql
> SELECT name FROM employees WHERE department_id = NULL AND salary < 72000;
> ```
> `department_id = NULL` возвращает NULL для каждой строки — результат пуст.
>
> **Правильный вариант:**
> ```sql
> SELECT name FROM employees WHERE department_id IS NULL AND salary < 72000;
> ```
> Для проверки на NULL — только `IS NULL`, никогда `= NULL`.

## Sources

- PostgreSQL Documentation (v16): SELECT, WHERE, Pattern Matching. <https://www.postgresql.org/docs/16/sql-select.html>, <https://www.postgresql.org/docs/16/functions-matching.html>

---

← [Выражения](../foundations/expressions.md) | [Сортировка и ограничение](sorting-and-limiting.md) →
