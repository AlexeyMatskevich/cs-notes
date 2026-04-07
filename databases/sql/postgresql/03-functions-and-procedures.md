# Функции и процедуры

<details>
<summary>Предпосылки</summary>

[DML](../modification/00-dml.md) (INSERT, UPDATE), [выражения](../foundations/02-expressions.md) (CASE), [агрегация](../querying/02-aggregation.md).

</details>

← [Полнотекстовый поиск](02-full-text-search.md) | [Триггеры](triggers.md) · [Индексы в production](04-index-operations.md) →

Checkout в приложении: проверить наличие товара, списать со склада, создать заказ, записать лог. Четыре SQL-запроса — четыре round-trip'а между приложением и базой. При latency 5 мс на запрос — 20 мс только на сеть, не считая выполнения. Серверная функция выполняет ту же логику за один round-trip — вся логика рядом с данными, сетевой overhead минимален.

## SQL-функции

Самый простой вид — тело функции является обычным SQL-запросом:

```sql
CREATE FUNCTION dept_avg_salary(dept_id BIGINT)
RETURNS NUMERIC
LANGUAGE sql
STABLE
AS $$
    SELECT AVG(salary) FROM employees WHERE department_id = dept_id;
$$;
```

```sql
SELECT d.name, dept_avg_salary(d.id) AS avg_salary
FROM departments d;
```

```
    name     | avg_salary
-------------+-----------
 engineering |      87500
 sales       |      65000
 hr          |       NULL
```

`$$` — долларное квотирование (dollar quoting). Всё между `$$` и `$$` — строковый литерал. Это избавляет от экранирования одинарных кавычек внутри тела функции. При вложенных функциях можно использовать именованные ограничители: `$body$...$body$`.

`STABLE` — категория волатильности (volatility). Она сообщает планировщику, как функция ведёт себя:

| Категория | Поведение | Пример |
|---|---|---|
| `IMMUTABLE` | Всегда возвращает одинаковый результат для одних аргументов | `abs(x)`, `lower(text)` |
| `STABLE` | Результат не меняется в пределах одного оператора (statement) | Чтение таблиц (без записи), `now()` |
| `VOLATILE` | Результат может меняться при каждом вызове (по умолчанию) | `random()`, `clock_timestamp()`, функции с побочными эффектами |

Правильная категория позволяет планировщику оптимизировать: IMMUTABLE-функцию можно вычислить один раз и закешировать, STABLE — один раз за statement. VOLATILE вызывается каждый раз.

Неправильная категория — источник трудноуловимых багов. Если STABLE-функция `get_exchange_rate('USD')` помечена как IMMUTABLE, планировщик кеширует результат первого вызова и использует его для всех последующих строк в запросе — даже если курс изменился. В prepared statements кешированный результат может пережить несколько вызовов. Правило: IMMUTABLE — только для функций, результат которых зависит **исключительно** от аргументов (`abs`, `lower`, математические операции).

## PL/pgSQL — процедурный язык

Для логики с условиями, циклами и переменными — PL/pgSQL (Procedural Language/PostgreSQL):

```sql
CREATE FUNCTION salary_grade(emp_salary INTEGER)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF emp_salary IS NULL THEN
        RETURN 'unknown';
    ELSIF emp_salary >= 80000 THEN
        RETURN 'senior';
    ELSIF emp_salary >= 60000 THEN
        RETURN 'middle';
    ELSE
        RETURN 'junior';
    END IF;
END;
$$;
```

```sql
SELECT name, salary, salary_grade(salary) FROM employees;
```

```
  name   | salary | salary_grade
---------+--------+-------------
 Анна    |  90000 | senior
 Борис   |  60000 | middle
 Вера    |  85000 | senior
 Глеб    |  70000 | middle
 Дина    |   NULL | unknown
 Евгений |  55000 | junior
```

Функция используется в SELECT как обычное выражение.

### Переменные и циклы

```sql
CREATE FUNCTION count_high_earners(threshold INTEGER)
RETURNS BIGINT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    result BIGINT;
BEGIN
    SELECT COUNT(*) INTO result
    FROM employees
    WHERE salary >= threshold;

    RETURN result;
END;
$$;
```

`DECLARE` объявляет локальные переменные. `SELECT ... INTO` записывает результат запроса в переменную. Для итерации по строкам — `FOR ... IN ... LOOP`:

```sql
CREATE FUNCTION employees_in_dept(dept_id BIGINT)
RETURNS TABLE (emp_name TEXT, emp_salary INTEGER)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT name, salary FROM employees
    WHERE department_id = dept_id
    ORDER BY salary DESC;
END;
$$;
```

```sql
SELECT * FROM employees_in_dept(1);
```

```
 emp_name | emp_salary
----------+-----------
 Дина     |      NULL
 Анна     |     90000
 Вера     |     85000
```

`RETURNS TABLE` — функция возвращает набор строк. `RETURN QUERY` передаёт результат запроса вызывающей стороне.

### Обработка ошибок (EXCEPTION)

PL/pgSQL позволяет перехватывать ошибки внутри блока BEGIN...EXCEPTION:

```sql
CREATE FUNCTION safe_insert_user(p_email TEXT, p_name TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO users (email, name) VALUES (p_email, p_name);
    RETURN TRUE;
EXCEPTION
    WHEN unique_violation THEN
        RETURN FALSE;
END;
$$;
```

Каждый блок EXCEPTION создаёт **implicit subtransaction** — аналог [SAVEPOINT](../modification/01-transactions.md#savepoint--частичный-откат). Если ошибка не возникает, subtransaction фиксируется прозрачно. Если возникает — откатывается только блок, а не вся транзакция.

В цикле это означает subtransaction на **каждую итерацию**. Тысяча итераций с EXCEPTION — тысяча subtransactions, каждая с overhead на создание и фиксацию. Для bulk upsert `INSERT ... ON CONFLICT` (без subtransactions) значительно эффективнее:

```sql
INSERT INTO users (email, name)
VALUES ('alice@example.com', 'Alice')
ON CONFLICT (email) DO NOTHING;
```

ON CONFLICT обрабатывает коллизию внутри одной операции — без дополнительных subtransactions.

## Процедуры

Checkout-функция обрабатывает один заказ. Но ежедневная пакетная выверка — 50 000 заказов, каждый требует UPDATE. Одна транзакция на 50 000 UPDATE держит блокировки минутами и не позволяет освободить память до COMMIT. Нужен способ фиксировать промежуточные результаты. Процедуры (PROCEDURE, начиная с PostgreSQL 11) отличаются от функций: не возвращают значение, но могут управлять транзакциями.

```sql
CREATE PROCEDURE transfer_funds(
    from_id BIGINT,
    to_id   BIGINT,
    amount  NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE accounts SET balance = balance - amount WHERE id = from_id;
    UPDATE accounts SET balance = balance + amount WHERE id = to_id;
    COMMIT;
END;
$$;
```

```sql
CALL transfer_funds(1, 2, 1000);
```

Ключевые отличия от функций:

| | Функция | Процедура |
|---|---|---|
| Вызов | `SELECT func()` / в выражениях | `CALL proc()` |
| Возврат значения | Да (`RETURNS`) | Нет |
| Транзакции внутри | Нет (работает в текущей) | Да (`COMMIT`/`ROLLBACK`) |
| Использование в SQL | В SELECT, WHERE, и т.д. | Только через CALL |

Для большинства задач достаточно функций. Процедуры нужны, когда внутри тела требуется фиксировать промежуточные результаты (COMMIT) — например, при пакетной обработке больших объёмов данных.

## Управление функциями

Checkout-функция в production, бизнес-логика меняется — новая категория скидок. Нужно обновить функцию без удаления зависимых view. Замена существующей функции:

```sql
CREATE OR REPLACE FUNCTION salary_grade(emp_salary INTEGER)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    ...
END;
$$;
```

`CREATE OR REPLACE` заменяет тело, не меняя OID функции. Зависимости (views, другие функции) сохраняются. Но нельзя менять тип возврата или аргументы — для этого нужно сначала `DROP FUNCTION`.

Удаление:

```sql
DROP FUNCTION salary_grade(INTEGER);
DROP FUNCTION IF EXISTS salary_grade(INTEGER);
```

Имя функции и типы аргументов — её сигнатура. PostgreSQL допускает перегрузку: несколько функций с одним именем, но разными аргументами.

## Транзакционный DDL

Деплой новой версии checkout-функции вместе с ALTER TABLE в одной миграции — что произойдёт при ошибке? В большинстве СУБД (MySQL, Oracle) команды DDL (CREATE TABLE, ALTER TABLE, DROP TABLE) автоматически фиксируют транзакцию. Если внутри транзакции выполнить ALTER TABLE и затем ROLLBACK — ALTER уже зафиксирован, откат не произойдёт.

PostgreSQL — исключение. DDL в PostgreSQL **транзакционный**:

```sql
BEGIN;
CREATE TABLE test (id integer);
INSERT INTO test VALUES (1);
ROLLBACK;

-- Таблица test НЕ существует -- ROLLBACK откатил и CREATE TABLE
```

Это означает, что миграции базы данных можно выполнять внутри транзакции. Если что-то пошло не так — ROLLBACK отменяет все изменения, включая DDL. База остаётся в консистентном состоянии.

Исключения: некоторые операции не транзакционны даже в PostgreSQL — `CREATE DATABASE`, `CREATE INDEX CONCURRENTLY` (подробнее в [индексах в production](04-index-operations.md)). Но основные DDL-команды (CREATE TABLE, ALTER TABLE, DROP TABLE) полностью транзакционны.

## См. также

- [Триггеры](triggers.md) — автоматический вызов функций при INSERT, UPDATE, DELETE

## Sources

- PostgreSQL Documentation (v16): CREATE FUNCTION. <https://www.postgresql.org/docs/16/sql-createfunction.html>
- PostgreSQL Documentation (v16): CREATE PROCEDURE. <https://www.postgresql.org/docs/16/sql-createprocedure.html>
- PostgreSQL Documentation (v16): PL/pgSQL. <https://www.postgresql.org/docs/16/plpgsql.html>

---

← [Полнотекстовый поиск](02-full-text-search.md) | [Триггеры](triggers.md) · [Индексы в production](04-index-operations.md) →
