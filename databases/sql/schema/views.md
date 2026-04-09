---
tags:
  - domain/sql
  - theme/schema-evolution
  - type/concept
aliases:
  - Views
  - CREATE VIEW
order: 15
---

# Представления (views)

**Предпосылки:** [подзапросы и CTE](../querying/subqueries-and-cte.md) (подзапросы, CTE), [соединения](../querying/joins.md) ([JOIN](../querying/joins.md)).

← [Партиционирование](partitioning.md) | [Индексы](indexes.md) →

Дашборд аналитики показывает количество сотрудников, среднюю зарплату и использование бюджета по отделам. Запрос — 3 JOIN, 2 подзапроса, 25 строк SQL. Каждое открытие страницы перезапускает этот запрос. Если тот же отчёт нужен в двух разных местах приложения — запрос дублируется, и любое изменение схемы требует правки в обоих местах.

Представление (view, англ. «вид, взгляд») — именованный запрос, сохранённый в базе. Обращение к view выглядит как обращение к таблице, но данные вычисляются при каждом запросе.

## CREATE VIEW

```sql
CREATE VIEW employee_details AS
SELECT e.id, e.name, d.name AS department, e.salary, e.hire_date
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id;
```

Теперь вместо повторения JOIN можно писать:

```sql
SELECT name, department, salary
FROM employee_details
WHERE salary > 70000;
```

```
 name | department  | salary
------+-------------+--------
 Анна | engineering |  90000
 Вера | engineering |  85000
```

View — это **именованный запрос**, а не копия данных. При каждом SELECT из view PostgreSQL выполняет сохранённый запрос заново. Данные всегда актуальны, но производительность определяется сложностью запроса внутри view.

## Обновление и удаление view

```sql
CREATE OR REPLACE VIEW employee_details AS
SELECT ...;   -- заменить определение

DROP VIEW employee_details;
DROP VIEW IF EXISTS employee_details;
```

`CREATE OR REPLACE` позволяет изменить запрос view без её удаления и пересоздания.

## Обновляемые представления

Простые view (один SELECT из одной таблицы, без GROUP BY, DISTINCT, JOIN, подзапросов) допускают INSERT, UPDATE, DELETE:

```sql
CREATE VIEW engineers AS
SELECT id, name, salary
FROM employees
WHERE department_id = 1;

UPDATE engineers SET salary = 95000 WHERE name = 'Анна';
```

Это обновит строку в базовой таблице `employees`. Для сложных view обновление невозможно (или требует триггеров INSTEAD OF).

## View как слой доступа

Таблица `employees` содержит `salary` и `ssn` (номер социального страхования). Аналитикам нужны только `name` и `department`. Можно выдать column-level GRANT, но каждый новый столбец в таблице требует ревью — забытый GRANT на конфиденциальный столбец = утечка данных.

Альтернатива — view с безопасным набором столбцов:

```sql
CREATE VIEW employee_directory AS
SELECT e.id, e.name, d.name AS department, e.hire_date
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id;

REVOKE ALL ON employees FROM analyst_role;
GRANT SELECT ON employee_directory TO analyst_role;
```

Аналитики видят только то, что включено в view. Новый столбец в `employees` автоматически скрыт — он не в SELECT view. Доступ управляется через одну точку.

View ограничивает **столбцы**, но не **строки**: аналитик увидит все строки base table. Для ограничения по строкам — добавить WHERE в определение view или использовать row-level security (в PostgreSQL — RLS).

Для тяжёлых запросов, результат которых допустимо обновлять периодически, PostgreSQL предлагает [материализованные представления](../postgresql/materialized-views.md) — view, сохраняющие результат на диск.

## Sources

- PostgreSQL Documentation (v16): CREATE VIEW. <https://www.postgresql.org/docs/16/sql-createview.html>

---

← [Партиционирование](partitioning.md) | [Индексы](indexes.md) →
