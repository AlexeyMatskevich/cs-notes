# Индексы в production

**Предпосылки:** [индексы](../schema/04-indexes.md) (CREATE INDEX, типы индексов), [таблицы и типы](../schema/00-tables-and-types.md).

← [Функции и процедуры](03-functions-and-procedures.md) | [EXCLUSION](05-exclusion-constraints.md) →

CREATE INDEX на пустой таблице — мгновенная операция. Но таблица `orders` — 50 млн строк, 400 записей в секунду. Обычный `CREATE INDEX` блокирует все записи на время построения. Как создать, обслуживать и пересобрать индекс, не останавливая запись?

## Блокировки при создании

`CREATE INDEX` берёт SHARE (англ. «разделяемый») lock на таблицу — **блокирует INSERT, UPDATE и DELETE** на всё время создания. На таблице 50 млн строк это минуты.

Проблема усугубляется: ожидающий `SHARE` lock блокирует все последующие запросы — SELECT встают в очередь за ним. Подробнее о механизме блокировок — в [блокировках PostgreSQL](../../postgresql/concurrency/03-locks.md).

## CREATE INDEX CONCURRENTLY

```sql
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);
```

CONCURRENTLY (англ. «одновременно, параллельно») берёт `SHARE UPDATE EXCLUSIVE` lock — **не блокирует DML**. INSERT, UPDATE и DELETE продолжают работать во время создания индекса.

PostgreSQL делает два прохода по таблице. Первый сканирует существующие строки. Второй собирает изменения, сделанные во время первого прохода. Цена: работает в 2–3 раза дольше, требует больше ресурсов, **нельзя использовать внутри транзакции** (поэтому транзакционный DDL здесь не работает — см. [функции и процедуры](03-functions-and-procedures.md)).

Правило: в production **всегда CONCURRENTLY**. Обычный CREATE INDEX — только для пустых таблиц или maintenance windows.

## Сбой при CONCURRENTLY — INVALID индекс

При сбое CONCURRENTLY оставляет индекс в состоянии INVALID (англ. «недействительный»). Такой индекс не используется для запросов, но занимает место и замедляет запись — каждый INSERT и UPDATE обновляет его. Нужно удалить (`DROP INDEX idx_name`) и создать заново.

Проверка:

```sql
SELECT indexrelid::regclass, indisvalid
FROM pg_index
WHERE NOT indisvalid;
```

## REINDEX — пересоздание раздувшегося индекса

После массового DELETE или UPDATE индекс разрастается (index bloat) — B-tree содержит пустые страницы, но не отдаёт их ОС. Индекс на 400 МБ может эффективно использовать только 200 МБ — остальное пустые страницы, замедляющие обход дерева.

```sql
REINDEX INDEX idx_orders_customer;
```

`REINDEX` берёт ACCESS EXCLUSIVE (англ. «монопольный доступ») lock — блокирует **всё**, включая SELECT. На production это неприемлемо.

```sql
REINDEX INDEX CONCURRENTLY idx_orders_customer;  -- PostgreSQL 12+
```

`REINDEX CONCURRENTLY` — неблокирующий аналог. Создаёт новый индекс рядом со старым, затем подменяет. Альтернативный подход: создать новый индекс CONCURRENTLY с другим именем, затем DROP старый.

## Sources

- PostgreSQL Documentation (v16): CREATE INDEX. <https://www.postgresql.org/docs/16/sql-createindex.html>
- PostgreSQL Documentation (v16): REINDEX. <https://www.postgresql.org/docs/16/sql-reindex.html>


---

← [Функции и процедуры](03-functions-and-procedures.md) | [EXCLUSION](05-exclusion-constraints.md) →
