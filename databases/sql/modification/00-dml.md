# DML — изменение данных

**Предпосылки:** [таблицы и типы](../schema/00-tables-and-types.md) (CREATE TABLE, DEFAULT), [ограничения](../schema/01-constraints.md) (NOT NULL, PK, FK, CHECK).

Запросы на чтение (SELECT) не меняют данные. Для добавления, изменения и удаления строк SQL предоставляет три команды: INSERT, UPDATE, DELETE. Эти команды составляют DML — Data Manipulation Language (англ. «язык манипулирования данными»).

## INSERT — добавление строк

```sql
INSERT INTO employees (id, name, department_id, salary, hire_date)
VALUES (7, 'Жанна', 1, 75000, '2024-06-01');
```

Столбцы с DEFAULT можно опустить:

```sql
INSERT INTO orders (id, total)
VALUES (6, 18000);
-- created_at и status получат значения по умолчанию
```

### Вставка нескольких строк

```sql
INSERT INTO employees (id, name, department_id, salary, hire_date) VALUES
(8, 'Захар',  2, 65000, '2024-07-01'),
(9, 'Ирина',  1, 80000, '2024-08-15');
```

### INSERT ... SELECT

Вставка из результата запроса:

```sql
INSERT INTO archived_orders (id, customer_id, total, created_at)
SELECT id, customer_id, total, created_at
FROM orders
WHERE created_at < '2024-01-01';
```

## UPDATE — изменение строк

```sql
UPDATE employees
SET salary = 95000
WHERE name = 'Анна';
```

UPDATE изменяет **все строки**, удовлетворяющие WHERE. Без WHERE — все строки таблицы:

```sql
UPDATE employees SET salary = salary * 1.1;  -- повышение всем на 10%
```

Можно обновлять несколько столбцов:

```sql
UPDATE employees
SET salary = 95000, department_id = 2
WHERE id = 1;
```

### UPDATE с подзапросом

```sql
UPDATE employees e
SET salary = salary * 1.1
WHERE department_id = (
    SELECT id FROM departments WHERE name = 'engineering'
);
```

## DELETE — удаление строк

```sql
DELETE FROM employees WHERE id = 9;
```

DELETE удаляет **все строки**, удовлетворяющие WHERE. Без WHERE — все строки таблицы:

```sql
DELETE FROM employees;  -- удалить всё!
```

DELETE уважает FOREIGN KEY: если на строку ссылаются дочерние записи и каскадного удаления нет — ошибка.

## TRUNCATE — быстрая очистка таблицы

TRUNCATE (англ. «усечь, обрезать») удаляет **все строки** таблицы, но быстрее DELETE:

```sql
TRUNCATE employees;
TRUNCATE employees RESTART IDENTITY;  -- и сбросить sequence
```

Разница: DELETE удаляет строки по одной и создаёт dead tuples (для MVCC и возможности ROLLBACK). TRUNCATE удаляет данные на уровне файлов — мгновенно, без dead tuples. Но TRUNCATE нельзя откатить в некоторых СУБД (в PostgreSQL — можно, он транзакционный).

TRUNCATE также сбрасывает visibility map и FSM, поэтому не нужен последующий VACUUM.

## RETURNING — получение результата (PostgreSQL)

В PostgreSQL INSERT, UPDATE и DELETE могут возвращать данные изменённых строк:

```sql
INSERT INTO employees (id, name, department_id, salary, hire_date)
VALUES (10, 'Кирилл', 2, 72000, '2024-09-01')
RETURNING id, name;
```

```
 id |  name
----+---------
 10 | Кирилл
```

```sql
UPDATE employees SET salary = salary * 1.1
WHERE department_id = 1
RETURNING name, salary;
```

```
 name | salary
------+--------
 Анна |  99000
 Вера |  93500
 Дина |   NULL
```

RETURNING особенно полезен для получения сгенерированного id после INSERT без дополнительного SELECT.

## INSERT ... ON CONFLICT — UPSERT (PostgreSQL)

UPSERT (update + insert) — вставка с обработкой конфликта уникальности:

```sql
INSERT INTO users (email, name)
VALUES ('anna@example.com', 'Анна')
ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name;
```

Если `email` уже существует — обновить `name`. `EXCLUDED` — ссылка на строку, которую пытались вставить.

```sql
INSERT INTO users (email, name)
VALUES ('anna@example.com', 'Анна')
ON CONFLICT (email) DO NOTHING;  -- молча пропустить дубликат
```

ON CONFLICT требует уникального индекса или ограничения для определения конфликта.

## Sources

- PostgreSQL Documentation (v16): INSERT, UPDATE, DELETE, TRUNCATE. <https://www.postgresql.org/docs/16/dml.html>
- PostgreSQL Documentation (v16): RETURNING. <https://www.postgresql.org/docs/16/dml-returning.html>
- PostgreSQL Documentation (v16): INSERT ON CONFLICT. <https://www.postgresql.org/docs/16/sql-insert.html#SQL-ON-CONFLICT>
