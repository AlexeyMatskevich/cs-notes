# Представления (views)

**Предпосылки:** [подзапросы и CTE](../querying/05-subqueries-and-cte.md) (подзапросы, CTE), [соединения](../querying/03-joins.md) (JOIN).

← [Партиционирование](02-partitioning.md) | [Индексы](04-indexes.md) →

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
 Глеб | sales       |  70000
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

## MATERIALIZED VIEW — снимок данных

MATERIALIZED VIEW (англ. «материализованное представление», от «материализовать» — превратить в материю) сохраняет результат запроса **на диск**:

```sql
CREATE MATERIALIZED VIEW monthly_sales AS
SELECT date_trunc('month', created_at) AS month,
       SUM(total) AS revenue,
       COUNT(*) AS order_count
FROM orders
GROUP BY date_trunc('month', created_at);
```

В отличие от обычного view, данные вычисляются один раз и хранятся физически. Запросы к materialized view быстрые — это обычное чтение таблицы. Но данные могут устареть.

Конкретика: `monthly_sales` на 50 млн строк выполняется 30 секунд. Cron запускает REFRESH каждые 5 минут. Между рефрешами данные устарели максимум на 5 минут. Для аналитического дашборда — допустимо, для real-time отображения баланса — нет.

### REFRESH и блокировки

```sql
REFRESH MATERIALIZED VIEW monthly_sales;
```

Обычный REFRESH **блокирует чтение** materialized view на время выполнения. 30 секунд без доступа к данным на production неприемлемо.

В PostgreSQL есть неблокирующая альтернатива — REFRESH CONCURRENTLY:

```sql
CREATE UNIQUE INDEX monthly_sales_month_idx ON monthly_sales (month);
REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_sales;
```

CONCURRENTLY (PostgreSQL) требует UNIQUE INDEX на materialized view. Механизм: PostgreSQL вычисляет новые данные, сравнивает с существующими (diff), применяет изменения. Это медленнее обычного REFRESH, но не блокирует чтение. В самом конце — кратковременный lock для подмены данных (миллисекунды, не секунды). Без UNIQUE INDEX CONCURRENTLY невозможен — PostgreSQL не может вычислить diff без ключа для сопоставления строк.

### Когда использовать

Обычный view — когда данные должны быть всегда актуальны и запрос не слишком тяжёлый. Materialized view — для тяжёлых аналитических запросов, где допустима задержка в актуальности данных.

## Sources

- PostgreSQL Documentation (v16): CREATE VIEW. <https://www.postgresql.org/docs/16/sql-createview.html>
- PostgreSQL Documentation (v16): CREATE MATERIALIZED VIEW. <https://www.postgresql.org/docs/16/sql-creatematerializedview.html>

---

← [Партиционирование](02-partitioning.md) | [Индексы](04-indexes.md) →
