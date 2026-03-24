# Триггеры

**Предпосылки:** [функции и процедуры](03-functions-and-procedures.md) (PL/pgSQL, RETURNS, BEGIN...END).

← [Функции и процедуры](03-functions-and-procedures.md)

Функции и процедуры вызываются явно — приложение решает, когда выполнить `SELECT func()` или `CALL proc()`. Но некоторые инварианты нужно поддерживать при каждом изменении данных, независимо от того, кто его сделал: приложение, миграция, ручной SQL в psql. Триггер (trigger, англ. «спусковой крючок») — функция, которую PostgreSQL вызывает автоматически при INSERT, UPDATE или DELETE.

## Автоматическое обновление `modified_at`

Таблица `orders` хранит время последнего изменения. Если обновлять `modified_at` в приложении, каждый UPDATE-запрос должен помнить об этом. Один забытый UPDATE — и аудит-лог показывает устаревшее время. Триггер решает задачу на уровне базы:

```sql
CREATE FUNCTION update_modified_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.modified_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER set_modified_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION update_modified_at();
```

При каждом UPDATE строки в `orders` PostgreSQL автоматически устанавливает `modified_at` в текущее время. `NEW` — ссылка на новую версию строки (после изменения), `OLD` — на старую (до изменения). `RETURNS TRIGGER` — специальный тип возврата для триггерных функций.

## BEFORE и AFTER

`BEFORE` — триггер выполняется до записи изменений. Функция может изменить `NEW` (как в примере выше) или вернуть `NULL`, чтобы отменить операцию. `AFTER` — триггер выполняется после записи. Строка уже сохранена, изменять `NEW` бессмысленно, но можно выполнить побочный эффект: записать в аудит-таблицу, отправить NOTIFY.

Правило выбора: если триггер модифицирует саму строку (автозаполнение полей, валидация) — `BEFORE`. Если выполняет побочный эффект на основе уже сохранённых данных — `AFTER`.

## FOR EACH ROW и FOR EACH STATEMENT

`FOR EACH ROW` — функция вызывается для каждой затронутой строки. `UPDATE orders SET status = 'shipped' WHERE batch_id = 42` затрагивает 500 строк — триггер выполнится 500 раз. `FOR EACH STATEMENT` — один вызов на весь SQL-оператор, независимо от количества строк. В statement-level триггерах `NEW` и `OLD` недоступны.

## Удаление триггера

```sql
DROP TRIGGER set_modified_at ON orders;
DROP TRIGGER IF EXISTS set_modified_at ON orders;
```

Триггер привязан к конкретной таблице — при удалении указывается и имя триггера, и таблица. Триггерная функция (`update_modified_at`) удаляется отдельно через `DROP FUNCTION`, если она больше не используется.

## Sources

- PostgreSQL Documentation (v16): CREATE TRIGGER. <https://www.postgresql.org/docs/16/sql-createtrigger.html>
- PostgreSQL Documentation (v16): Trigger Functions. <https://www.postgresql.org/docs/16/plpgsql-trigger.html>

---

← [Функции и процедуры](03-functions-and-procedures.md)
