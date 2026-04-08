# DML — изменение данных

**Предпосылки:** [таблицы и типы](../schema/tables-and-types.md) (CREATE TABLE, DEFAULT), [ограничения](../schema/constraints.md) (NOT NULL, PK, FK, CHECK).

← [Пагинация](../querying/pagination.md) | [Транзакции](transactions.md) →

Запросы на чтение (SELECT) не меняют данные. Жизненный цикл данных в HR-системе за один рабочий день: онбординг нового сотрудника, пакетный найм, повышение, реструктуризация, увольнение, очистка staging-среды, ежедневный импорт с обработкой дубликатов. Каждая задача требует своей команды: INSERT, UPDATE, DELETE, TRUNCATE. Эти команды составляют DML — Data Manipulation Language (англ. «язык манипулирования данными»).

## Онбординг: Жанна выходит на работу — INSERT

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

### Пакетный найм — несколько строк

В компанию выходят сразу двое:

```sql
INSERT INTO employees (id, name, department_id, salary, hire_date) VALUES
(8, 'Захар',  2, 65000, '2024-07-01'),
(9, 'Ирина',  1, 80000, '2024-08-15');
```

### Нужен id для badge — RETURNING

HR-системе нужен id нового сотрудника сразу после вставки — для печати бейджа и привязки к проектам. Без RETURNING пришлось бы делать отдельный SELECT.

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

RETURNING особенно полезен для получения сгенерированного id после INSERT без дополнительного SELECT.

### Архивирование заказов — INSERT...SELECT

Заказы за прошлый год нужно перенести в архивную таблицу:

```sql
INSERT INTO archived_orders (id, customer_id, total, created_at)
SELECT id, customer_id, total, created_at
FROM orders
WHERE created_at < '2024-01-01';
```

## Повышение Анне — UPDATE

```sql
UPDATE employees
SET salary = 95000
WHERE name = 'Анна';
```

### UPDATE без WHERE — опасность

Весь отдел получает повышение 10%:

```sql
UPDATE employees SET salary = salary * 1.1
WHERE department_id = 1;
```

Попробуем забыть WHERE:

```sql
UPDATE employees SET salary = salary * 1.1;  -- повышение ВСЕМ!
```

UPDATE изменяет **все строки**, удовлетворяющие WHERE. Без WHERE — все строки таблицы. На production это катастрофа. Правило: всегда проверять WHERE перед UPDATE.

Можно обновлять несколько столбцов:

```sql
UPDATE employees
SET salary = 95000, department_id = 2
WHERE id = 1;
```

### Реструктуризация — UPDATE с подзапросом

Все сотрудники engineering переходят в новый отдел:

```sql
UPDATE employees e
SET department_id = 4
WHERE department_id = (
    SELECT id FROM departments WHERE name = 'engineering'
);
```

Подзапрос вычисляет id engineering — не нужно помнить числовой id, достаточно имени.

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

RETURNING работает и с UPDATE — показывает **новые** значения изменённых строк.

## Увольнение — DELETE

```sql
DELETE FROM employees WHERE id = 9;
```

DELETE удаляет **все строки**, удовлетворяющие WHERE. Без WHERE — все строки таблицы:

```sql
DELETE FROM employees;  -- удалить всё!
```

DELETE уважает FOREIGN KEY: если на строку ссылаются дочерние записи и каскадного удаления нет — ошибка. Подробнее — в [ограничениях](../schema/constraints.md).

## Сброс staging — TRUNCATE vs DELETE

Staging-среду нужно полностью очистить перед тестированием. DELETE удалит все строки, но медленно:

TRUNCATE (англ. «усечь, обрезать») удаляет **все строки** таблицы, но быстрее DELETE:

```sql
TRUNCATE employees;
TRUNCATE employees RESTART IDENTITY;  -- и сбросить sequence
```

Разница: DELETE удаляет строки по одной, и освободившееся место остаётся занятым до фоновой очистки. TRUNCATE удаляет данные на уровне файлов — мгновенно, без необходимости фоновой очистки. В PostgreSQL TRUNCATE транзакционный — его можно откатить.

## Ежедневный импорт — UPSERT (PostgreSQL)

Каждый день приходит файл с данными сотрудников. Если сотрудник уже есть (по email) — обновить имя. Если нет — вставить. Без UPSERT нужно два запроса или процедурная логика.

INSERT ... ON CONFLICT (update + insert) — вставка с обработкой конфликта уникальности:

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

Когда ON CONFLICT недостаточно — нужен произвольный JOIN для определения совпадения, условные ветки обновления или комбинация нескольких DML в одном запросе — [составные DML-операции](compound-dml.md) покрывают MERGE и другие паттерны.

## Sources

- PostgreSQL Documentation (v16): INSERT, UPDATE, DELETE, TRUNCATE. <https://www.postgresql.org/docs/16/dml.html>
- PostgreSQL Documentation (v16): RETURNING. <https://www.postgresql.org/docs/16/dml-returning.html>
- PostgreSQL Documentation (v16): INSERT ON CONFLICT. <https://www.postgresql.org/docs/16/sql-insert.html#SQL-ON-CONFLICT>

---

← [Пагинация](../querying/pagination.md) | [Транзакции](transactions.md) →
