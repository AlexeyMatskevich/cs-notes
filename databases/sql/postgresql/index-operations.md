---
tags:
  - domain/sql
  - theme/indexing
  - theme/performance
  - type/concept
aliases:
  - CONCURRENTLY
  - REINDEX
  - Index Operations
order: 26
---

# Индексы в production

**Предпосылки:** [индексы](../schema/indexes.md) (CREATE INDEX, типы индексов), [таблицы и типы](../schema/tables-and-types.md).

← [Функции и процедуры](functions-and-procedures.md) | [EXCLUSION](exclusion-constraints.md) →

CREATE INDEX на пустой таблице — мгновенная операция. Но таблица `orders` — 50 млн строк, 400 записей в секунду. Обычный `CREATE INDEX` блокирует все записи на время построения. Как создать, обслуживать и пересобрать индекс, не останавливая запись?

## Блокировки при создании

`CREATE INDEX` берёт SHARE (англ. «разделяемый») lock на таблицу — **блокирует INSERT, UPDATE и DELETE** на всё время создания. На таблице 50 млн строк это минуты.

Проблема усугубляется: ожидающий `SHARE` lock блокирует все последующие запросы — SELECT встают в очередь за ним. Подробнее о механизме блокировок — в [блокировках PostgreSQL](../../postgresql/concurrency/locks.md#table-level-locks--защита-структуры-таблицы).

## CREATE INDEX CONCURRENTLY

```sql
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);
```

CONCURRENTLY (англ. «одновременно, параллельно») берёт `SHARE UPDATE EXCLUSIVE` lock — **не блокирует DML**. INSERT, UPDATE и DELETE продолжают работать во время создания индекса.

PostgreSQL делает два прохода по таблице. Первый сканирует существующие строки. Второй собирает изменения, сделанные во время первого прохода. Для обычного индекса это просто более долгий build. Для unique index есть важная особенность: во втором проходе PostgreSQL уже может начать отклонять новые дубликаты ещё до завершения команды. Цена: работает в 2–3 раза дольше, требует больше ресурсов, **нельзя использовать внутри транзакции** (поэтому транзакционный DDL здесь не работает — см. [транзакционный DDL](functions-and-procedures.md#транзакционный-ddl)).

Правило: в production **всегда CONCURRENTLY**. Обычный CREATE INDEX — только для пустых таблиц или maintenance windows.

## Сбой при CONCURRENTLY — INVALID индекс

При сбое CONCURRENTLY оставляет индекс в состоянии INVALID (англ. «недействительный»). Такой индекс не используется планировщиком для запросов, но занимает место и замедляет запись — каждый INSERT и UPDATE обновляет его. Для уникальных индексов INVALID-состояние может быть особенно опасным. Если сбой произошёл во второй фазе build-а (индекс уже помечен `indisready = true` в `pg_index`), PostgreSQL продолжает проверять уникальность при INSERT даже через INVALID-индекс, отклоняя строки-дубликаты. Если сбой в первой фазе (`indisready = false`), индекс не enforce uniqueness, но всё равно замедляет запись. Поэтому после любого failed `CREATE UNIQUE INDEX CONCURRENTLY` первым действием должен быть `DROP INDEX CONCURRENTLY idx_name`: сначала убрать сломанный индекс, и только потом повторять build или возвращать обычный write traffic. Обычный `DROP INDEX` берёт ACCESS EXCLUSIVE и блокирует все запросы; как и CREATE INDEX CONCURRENTLY, DROP INDEX CONCURRENTLY не работает внутри транзакции.

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

## USING INDEX — привязка индекса к constraint

`ADD UNIQUE(col)` и `ADD PRIMARY KEY(col)` строят уникальный индекс под ACCESS EXCLUSIVE — блокировка на всё время построения. USING INDEX позволяет привязать уже существующий индекс к constraint без повторного построения:

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_orders_external_id ON orders (external_id);

ALTER TABLE orders ADD CONSTRAINT orders_external_id_uq
  UNIQUE USING INDEX idx_orders_external_id;
```

Первый шаг — неблокирующее построение (SHARE UPDATE EXCLUSIVE). Второй — мгновенная привязка (ACCESS EXCLUSIVE на микросекунды). Ограничение: не работает для партиционированных таблиц (PostgreSQL 9.2+, только не-партиционированные).

**Предусловие для live-таблиц:** если uniqueness создаётся впервые, до второго прохода CONCURRENTLY build дубликаты ещё могут проскочить, а во втором проходе PostgreSQL уже может начать отклонять новые конфликты. На таблице с активными writes необходимо приостановить запись в столбец + дождаться завершения in-flight транзакций перед запуском build. Полный workflow с защитой от дубликатов и cleanup после fail — в [миграциях](../../migrations/safe-schema-changes.md#уникальные-ограничения-и-первичные-ключи).

Для PRIMARY KEY столбец должен быть NOT NULL до USING INDEX — иначе PostgreSQL выполнит implicit SET NOT NULL с полным сканированием таблицы под ACCESS EXCLUSIVE. Безопасное добавление NOT NULL — там же.

## Sources

- PostgreSQL Documentation (v16): CREATE INDEX. <https://www.postgresql.org/docs/16/sql-createindex.html>
- PostgreSQL Documentation (v16): REINDEX. <https://www.postgresql.org/docs/16/sql-reindex.html>


---

← [Функции и процедуры](functions-and-procedures.md) | [EXCLUSION](exclusion-constraints.md) →
