# Транзакции

**Предпосылки:** [DML](00-dml.md) (INSERT, UPDATE, DELETE), [ACID](../../acid.md).

← [DML — изменение данных](00-dml.md) | [JSONB](../postgresql/00-jsonb.md) →

Перевод денег между счетами: списание с одного и зачисление на другой. Если между двумя UPDATE произойдёт сбой — деньги списаны, но не зачислены. Транзакция решает эту проблему: группа операций выполняется **целиком или не выполняется вообще**.

## BEGIN, COMMIT, ROLLBACK

```sql
BEGIN;
UPDATE accounts SET balance = balance - 1000 WHERE id = 1;
UPDATE accounts SET balance = balance + 1000 WHERE id = 2;
COMMIT;
```

BEGIN (англ. «начать») открывает транзакцию. COMMIT (англ. «зафиксировать, подтвердить») фиксирует все изменения. До COMMIT изменения видны только текущей транзакции.

Если что-то пошло не так:

```sql
BEGIN;
UPDATE accounts SET balance = balance - 1000 WHERE id = 1;
-- ошибка обнаружена
ROLLBACK;
```

ROLLBACK (англ. «откатить назад») отменяет все изменения с момента BEGIN. Таблица остаётся в состоянии до BEGIN.

## Автоматические транзакции

Каждая отдельная команда SQL, выполненная без явного BEGIN, автоматически оборачивается в транзакцию:

```sql
UPDATE accounts SET balance = balance - 1000 WHERE id = 1;
-- эквивалентно:
-- BEGIN;
-- UPDATE accounts SET balance = balance - 1000 WHERE id = 1;
-- COMMIT;
```

Это значит: одна команда — атомарна даже без явного BEGIN. Явный BEGIN нужен, когда **несколько команд** должны быть атомарными.

## SAVEPOINT — частичный откат

SAVEPOINT (англ. «точка сохранения») создаёт контрольную точку внутри транзакции. ROLLBACK TO откатывает к savepoint, но не закрывает транзакцию — после отката можно продолжить работу.

Импорт каталога товаров из CSV: 10 000 строк, часть содержит невалидные данные (дубли SKU, нарушение CHECK). Без SAVEPOINT одна ошибка откатывает весь BEGIN — 9 999 валидных строк потеряны. С SAVEPOINT перед каждым батчем ошибочный батч откатывается, а остальные фиксируются:

```sql
BEGIN;

SAVEPOINT batch_1;
INSERT INTO products (sku, name, price) VALUES
    ('A001', 'Keyboard', 2500),
    ('A002', 'Mouse', 1200);
-- OK, продолжаем

SAVEPOINT batch_2;
INSERT INTO products (sku, name, price) VALUES
    ('A001', 'Duplicate', 999);   -- нарушение UNIQUE(sku)
ROLLBACK TO batch_2;
-- batch_1 сохранён, batch_2 отменён

SAVEPOINT batch_3;
INSERT INTO products (sku, name, price) VALUES
    ('A003', 'Monitor', 35000);
-- OK

COMMIT;  -- зафиксированы batch_1 и batch_3
```

ROLLBACK TO уничтожает все savepoint'ы, созданные **после** указанного. Если есть sp1 → sp2 → sp3 и выполняется `ROLLBACK TO sp1`, то sp2 и sp3 исчезают — откатить к ним уже нельзя. Для продолжения работы после отката нужно создать новый savepoint.

Savepoint'ы не бесплатны: СУБД отслеживает состояние каждого, и на масштабе сотен тысяч overhead становится заметным. В PostgreSQL каждый SAVEPOINT создаёт subtransaction state — подробнее в [паттернах параллельного доступа](../../postgresql/concurrency/04-patterns.md).

## Долгие транзакции

Разработчик открыл BEGIN, выполнил SELECT для отладки и ушёл на обед. Пока транзакция открыта, СУБД не может освободить ресурсы, связанные с изменёнными строками — даже если все остальные транзакции давно завершились. Результат: рост занимаемого места и замедление запросов.

Та же проблема возникает в приложении: HTTP-запрос открывает транзакцию, делает внешний API-вызов (2 секунды timeout), потом продолжает работу с базой. Всё время ожидания API транзакция удерживает ресурсы.

В PostgreSQL механизм [MVCC](../../postgresql/concurrency/00-mvcc.md) усугубляет проблему: открытая транзакция держит snapshot, и [VACUUM](../../postgresql/maintenance/00-vacuum.md) не может удалить dead tuples, видимые этому snapshot — таблицы «пухнут» на гигабайты за минуты. Защита — `idle_in_transaction_session_timeout`: сервер принудительно завершает транзакцию, простаивающую дольше заданного времени.

## ACID

Транзакции обеспечивают четыре свойства, описанные в [ACID](../../acid.md):

**Atomicity** (атомарность) — транзакция выполняется целиком или не выполняется. Частичного результата нет.

**Consistency** (согласованность) — транзакция переводит базу из одного корректного состояния в другое. Ограничения (constraints) проверяются в конце транзакции.

**Isolation** (изоляция) — параллельные транзакции не видят незафиксированных изменений друг друга (степень изоляции зависит от уровня).

**Durability** (устойчивость) — после COMMIT данные сохранены, даже при сбое.

## Уровни изоляции

SQL стандарт определяет четыре уровня изоляции: READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE. PostgreSQL по умолчанию использует READ COMMITTED — каждый оператор видит данные, зафиксированные к моменту его начала.

```sql
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
-- все SELECT в этой транзакции видят один и тот же snapshot данных
SELECT balance FROM accounts WHERE id = 1;
-- ... другая транзакция меняет balance ...
SELECT balance FROM accounts WHERE id = 1;
-- тот же результат, что и в первом SELECT
COMMIT;
```

Подробнее о механике изоляции, аномалиях и выборе уровня — в [уровни изоляции в PostgreSQL](../../postgresql/concurrency/02-isolation-levels.md). Типовые паттерны работы с конкурентным доступом (SELECT FOR UPDATE, advisory locks (PostgreSQL), retry loops) — в [паттернах параллельного доступа](../../postgresql/concurrency/04-patterns.md).

## Sources

- PostgreSQL Documentation (v16): Transaction Management. <https://www.postgresql.org/docs/16/tutorial-transactions.html>
- PostgreSQL Documentation (v16): SET TRANSACTION. <https://www.postgresql.org/docs/16/sql-set-transaction.html>

---

← [DML — изменение данных](00-dml.md) | [JSONB](../postgresql/00-jsonb.md) →
