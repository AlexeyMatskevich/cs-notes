# Блокировки

**Предпосылки:** [MVCC](00-mvcc.md), [уровни изоляции](02-isolation-levels.md).

MVCC убирает блокировки чтения: читатели не блокируют писателей, писатели не блокируют читателей. Но два параллельных UPDATE одной строки — конфликт, который MVCC не решает. Платёжный сервис обрабатывает 200 транзакций/сек: два запроса одновременно списывают деньги с одного аккаунта. Без координации один перезапишет результат другого. Блокировки — механизм этой координации.

PostgreSQL использует три уровня блокировок. Row-level locks координируют запись в одну строку — они берутся автоматически при UPDATE и DELETE. Table-level locks защищают структуру таблицы от параллельного DDL. Advisory locks — блокировки, которые PostgreSQL не берёт сам: их запрашивает приложение для координации операций, не привязанных к конкретным строкам. Если транзакции берут блокировки в разном порядке, возникает deadlock — PostgreSQL обнаруживает его и откатывает одну из транзакций.

## Автоматические блокировки при записи

**Каждый UPDATE и DELETE автоматически берёт row-level lock.** Это не опция — это часть работы PostgreSQL.

```text
T1: UPDATE accounts SET balance = balance - 500 WHERE id = 1;
    -- PostgreSQL берёт lock на строку id=1

T2: UPDATE accounts SET balance = balance - 300 WHERE id = 1;
    -- T2 пытается взять lock, видит что занят
    -- T2 ждёт завершения T1
```

Когда T1 завершается и T2 получает lock, дальнейшее зависит от уровня изоляции. В READ COMMITTED PostgreSQL перечитывает строку и перепроверяет WHERE с новыми данными ([re-evaluation](02-isolation-levels.md)). В REPEATABLE READ — откатывает T2 с ошибкой сериализации, потому что строка изменилась после snapshot.

Без автоматических блокировок две транзакции могли бы одновременно записать в одну строку, создав хаос.

## Четыре режима row-level locks

Один режим «заблокировано» был бы слишком грубым. При проверке foreign key транзакция убеждается, что строка существует — она не меняет данные. Другая транзакция обновляет эту же строку. Если обе берут одинаковый «exclusive lock» — вторая ждёт первую. Но конфликта на самом деле нет: первая не меняет данные, только читает.

**Решение:** Разные уровни «строгости» с матрицей совместимости.

| Режим | Назначение | Блокирует |
|-------|------------|-----------|
| FOR KEY SHARE | «Проверяю, что строка существует» (foreign key) | Только FOR UPDATE |
| FOR SHARE | «Не хочу, чтобы менялось» | FOR UPDATE, FOR NO KEY UPDATE |
| FOR NO KEY UPDATE | «Меняю, но не ключ» | Всё кроме FOR KEY SHARE |
| FOR UPDATE | «Буду менять, возможно ключ» | Все режимы |

Матрица совместимости — какие режимы могут удерживаться одновременно:

```text
                    FOR KEY SHARE   FOR SHARE   FOR NO KEY UPDATE   FOR UPDATE
FOR KEY SHARE             +             +               +               -
FOR SHARE                 +             +               -               -
FOR NO KEY UPDATE         +             -               -               -
FOR UPDATE                -             -               -               -

(+ = совместимы, могут одновременно;  - = конфликт, одна транзакция ждёт)
```

**Пример:** T1 проверяет foreign key (FOR KEY SHARE). T2 обновляет не-ключевые поля (FOR NO KEY UPDATE). В матрице на пересечении стоит «+» — обе работают параллельно. Без разных режимов — одна бы ждала другую.

**FOR UPDATE** — самый строгий. Используется явно (`SELECT ... FOR UPDATE`) или автоматически при UPDATE/DELETE.

**FOR SHARE** — разделяемый. Несколько транзакций могут держать FOR SHARE на одной строке. Используется, когда нужно гарантировать, что строка не изменится, но сами менять не планируете.

## Table-level locks — защита структуры таблицы

Row-level locks защищают данные. Но что если одна транзакция читает таблицу, а другая делает `DROP TABLE` или `ALTER TABLE`?

**Проблема:** Транзакция T1 выполняет SELECT, читает страницу за страницей. Транзакция T2 делает `ALTER TABLE ... DROP COLUMN`. T1 читает следующую страницу — а там уже другая структура. Мусор вместо данных.

**Решение:** Table-level locks. Даже SELECT берёт лёгкую блокировку, которая не мешает другим читателям и писателям, но блокирует изменение структуры.

| Операция | Lock |
|----------|------|
| SELECT | ACCESS SHARE |
| UPDATE, DELETE, INSERT | ROW EXCLUSIVE |
| CREATE INDEX CONCURRENTLY | SHARE UPDATE EXCLUSIVE |
| CREATE INDEX | SHARE |
| ALTER TABLE, DROP TABLE | ACCESS EXCLUSIVE |

**ACCESS SHARE** совместим почти со всем, кроме ACCESS EXCLUSIVE. Пока хоть один SELECT выполняется — нельзя удалить или изменить структуру таблицы.

**ACCESS EXCLUSIVE** блокирует всё. Пока ALTER TABLE работает — никто не может даже читать.

**Практическая проблема:** Долгий SELECT блокирует DDL.

```sql
-- Сессия 1: долгий отчёт
SELECT * FROM huge_table;  -- держит ACCESS SHARE 10 минут

-- Сессия 2: срочная миграция
ALTER TABLE huge_table ADD COLUMN new_col INT;
-- Ждёт ACCESS EXCLUSIVE, но ACCESS SHARE мешает
-- 10 минут простоя!
```

**Скрытая проблема: очередь блокировок.** Что если во время ожидания ALTER TABLE приходит ещё один SELECT?

```text
T1: SELECT (держит ACCESS SHARE) — долгий отчёт
T2: ALTER TABLE (ждёт ACCESS EXCLUSIVE)
T3: SELECT (хочет ACCESS SHARE)
```

Интуитивно: ACCESS SHARE совместим с ACCESS SHARE, T3 должен работать параллельно с T1.

Реальность: T3 тоже ждёт. PostgreSQL ставит T3 в очередь ЗА T2, чтобы T2 не голодал вечно. Один ALTER TABLE в ожидании блокирует ВСЕ последующие запросы к таблице.

```text
Время --->
T1: [SELECT ============================]  ACCESS SHARE
T2:          [ALTER TABLE ....waiting....]  ACCESS EXCLUSIVE, в очереди
T3:               [SELECT .....waiting...]  ACCESS SHARE, в очереди за T2
T4:                    [SELECT ..waiting.]  ACCESS SHARE, в очереди за T2
```

Пока T1 держит ACCESS SHARE, T2 ждёт. Но и T3, и T4 выстраиваются за T2 — весь трафик к таблице встаёт.

**Решения:**

**1. lock_timeout на DDL** — не создавать очередь:
```sql
SET lock_timeout = '5s';
ALTER TABLE huge_table ADD COLUMN new_col INT;
-- Не получил lock за 5 секунд — отмена, попробуем позже
```

**2. CONCURRENTLY для индексов** — слабые блокировки:
```sql
-- Обычный: берёт SHARE lock, блокирует запись
CREATE INDEX idx_email ON users(email);

-- Неблокирующий: можно читать и писать во время создания
CREATE INDEX CONCURRENTLY idx_email ON users(email);
```

`CONCURRENTLY` работает дольше (несколько проходов), но не блокирует DML.

**3. Устранить причину долгих SELECT:** вынести аналитику на read replica, завершать забытые транзакции через `idle_in_transaction_session_timeout`, оптимизировать неэффективные запросы.

```sql
-- Убивать транзакции, idle больше 5 минут
SET idle_in_transaction_session_timeout = '5min';
```

## Advisory locks — когда row-level locks недостаточно

Row-level locks привязаны к конкретным строкам. Но иногда нужно координировать операции, которые не связаны с одной строкой.

**Проблема:** Платёжный сервис запускает ночную сверку — сопоставляет транзакции с банковской выпиской. Два экземпляра сервиса одновременно стартуют cron-джоб. Если запустить параллельно — дублирование записей, некорректные итоги. Нужно: «только один экземпляр выполняет сверку в любой момент времени».

Какую строку заблокировать FOR UPDATE? Сверка читает тысячи строк и создаёт новые записи. Нет одной строки, которую можно заблокировать — нет row lock.

**Решение: advisory locks** — блокировки, которые PostgreSQL не берёт автоматически. Их запрашивает приложение для своих целей.

```sql
SELECT pg_advisory_lock(42);     -- взять блокировку
-- критическая секция (сверка)
SELECT pg_advisory_unlock(42);   -- освободить
```

Число 42 — произвольный идентификатор. PostgreSQL не знает, что оно означает. Это договорённость между частями приложения: «42 = блокировка ночной сверки».

Второй экземпляр вызывает `pg_advisory_lock(42)` и ждёт, пока первый освободит. Если ждать не нужно — `pg_try_advisory_lock(42)` возвращает `false` без ожидания, и второй экземпляр просто пропускает запуск.

**Session vs. transaction scope.** `pg_advisory_lock` — session-scoped: блокировка живёт до явного `pg_advisory_unlock` или до конца сессии (разрыва соединения). Она не освобождается при COMMIT или ROLLBACK. Если приложение забудет вызвать `pg_advisory_unlock`, блокировка останется на всё время жизни соединения — а при connection pooling соединение может жить часами.

`pg_advisory_xact_lock` — transaction-scoped: автоматически освобождается при COMMIT/ROLLBACK, как обычные row-level locks. Для большинства случаев transaction-scoped вариант безопаснее — не требует ручного освобождения.

## Deadlock — взаимная блокировка

**Deadlock** возникает, когда транзакции ждут друг друга циклически.

```text
T1: UPDATE accounts SET balance = balance - 500 WHERE id = 1;  -- lock на строку 1
T2: UPDATE accounts SET balance = balance - 300 WHERE id = 2;  -- lock на строку 2
T1: UPDATE accounts SET balance = balance + 500 WHERE id = 2;  -- ждёт T2 (строка 2 занята)
T2: UPDATE accounts SET balance = balance + 300 WHERE id = 1;  -- ждёт T1 (строка 1 занята)
-- Цикл! Никто не может продолжить.
```

**Ключевое:** Deadlock возникает из-за автоматических блокировок при UPDATE. Никаких явных FOR UPDATE — просто два UPDATE в разном порядке.

**Обнаружение:** PostgreSQL периодически проверяет [граф ожидания](../../../algorithms-and-data-structures/non-linear/00-graph.md) (параметр `deadlock_timeout`, по умолчанию 1 секунда). При обнаружении цикла — откатывает одну из транзакций с ошибкой.

**Предотвращение:** Обновлять строки в предсказуемом порядке. Если транзакция обновляет несколько строк — порядок UPDATE определяет порядок блокировок.

```ruby
# Плохо: порядок зависит от аргументов
def transfer(from_id, to_id, amount)
  Account.find(from_id).decrement!(:balance, amount)
  Account.find(to_id).increment!(:balance, amount)
end
# transfer(1, 2) берёт lock 1, потом 2
# transfer(2, 1) берёт lock 2, потом 1 → deadlock!

# Хорошо: всегда обновляем в порядке возрастания id
def transfer(from_id, to_id, amount)
  ids = [from_id, to_id].sort
  accounts = Account.where(id: ids).order(:id).lock("FOR UPDATE")
  # Теперь обе транзакции берут locks в одном порядке
  from_account = accounts.find { |a| a.id == from_id }
  to_account = accounts.find { |a| a.id == to_id }
  from_account.decrement!(:balance, amount)
  to_account.increment!(:balance, amount)
end
```

**Почему FOR UPDATE в "хорошем" примере?** Без него каждый `find` + `update` — отдельная блокировка. С FOR UPDATE мы явно берём все нужные блокировки сразу, в правильном порядке, до начала изменений.

Блокировки дают механизм координации. Выбор между блокировками и уровнями изоляции зависит от конкретного сценария — [практические паттерны](04-patterns.md) помогают сделать этот выбор.

## Sources

- PostgreSQL Documentation (пример: v16): Explicit Locking, `pg_locks`, advisory locks. <https://www.postgresql.org/docs/16/explicit-locking.html>, <https://www.postgresql.org/docs/16/view-pg-locks.html>, <https://www.postgresql.org/docs/16/functions-admin.html>
