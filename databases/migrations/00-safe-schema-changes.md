# Безопасные изменения схемы

<details>
<summary>Предпосылки</summary>

[Таблицы и типы](../sql/schema/00-tables-and-types.md) (ALTER TABLE, DEFAULT), [ограничения](../sql/schema/01-constraints.md) (NOT NULL, FK, CHECK), [индексы](../sql/schema/04-indexes.md) (CREATE INDEX), [транзакции](../sql/modification/01-transactions.md) (BEGIN/COMMIT/ROLLBACK), [индексы в production](../sql/postgresql/04-index-operations.md) (CONCURRENTLY, INVALID), [блокировки](../postgresql/concurrency/03-locks.md) (уровни блокировок, очередь, lock_timeout).

</details>

← [Обзор серии](index.md) | [Эволюция схемы](01-schema-evolution.md) →

Добавить столбец на таблицу в dev — мгновенно. На `orders` с 50 миллионами строк та же операция может занять минуты и заблокировать все запросы. Разница — не в команде, а в том, что PostgreSQL делает под блокировкой: обновить запись в системном каталоге — микросекунды, или перезаписать каждую строку таблицы — минуты.

## Стоимость DDL-операций

Безопасность операции определяют три характеристики: уровень блокировки, тип действия (metadata / scan / rewrite) и длительность.

**Столбцы и переименование:**

| Операция | Блокировка | Действие | Длительность |
|----------|-----------|----------|-------------|
| ADD COLUMN (без default или DEFAULT вычисляется один раз, PG 11+) | ACCESS EXCLUSIVE | metadata | мгновенно |
| ADD COLUMN (DEFAULT вычисляется для каждой строки, или PG < 11) | ACCESS EXCLUSIVE | table rewrite | пропорционально размеру |
| DROP COLUMN | ACCESS EXCLUSIVE | metadata | мгновенно |
| ALTER COLUMN TYPE (перезапись) | ACCESS EXCLUSIVE | rewrite + index rebuild | пропорционально размеру |
| ALTER COLUMN TYPE (расширение varchar, varchar → text) | ACCESS EXCLUSIVE | metadata | мгновенно; index rebuild, если индексы зависят от типа |
| ALTER COLUMN SET NOT NULL | ACCESS EXCLUSIVE | full table scan | пропорционально размеру |
| RENAME COLUMN | ACCESS EXCLUSIVE | metadata | мгновенно |

**Ограничения:**

| Операция | Блокировка | Действие | Длительность |
|----------|-----------|----------|-------------|
| ADD CHECK (validated) | ACCESS EXCLUSIVE | scan | пропорционально размеру |
| ADD UNIQUE (validated) | ACCESS EXCLUSIVE | scan | пропорционально размеру |
| ADD FOREIGN KEY (validated) | SHARE ROW EXCLUSIVE (обе таблицы) | scan | пропорционально размеру |
| ADD CHECK ... NOT VALID | ACCESS EXCLUSIVE | metadata | мгновенно |
| ADD FK ... NOT VALID | SHARE ROW EXCLUSIVE (обе таблицы) | metadata | мгновенно |
| VALIDATE CONSTRAINT (CHECK) | SHARE UPDATE EXCLUSIVE | scan | пропорционально размеру |
| VALIDATE CONSTRAINT (FK) | SHARE UPDATE EXCLUSIVE (child) + ROW SHARE (parent) | scan обеих таблиц | пропорционально размеру |

**Индексы:**

| Операция | Блокировка | Действие | Длительность |
|----------|-----------|----------|-------------|
| CREATE INDEX | SHARE | build | пропорционально размеру; блокирует writes |
| CREATE INDEX CONCURRENTLY | SHARE UPDATE EXCLUSIVE | two-phase build | дольше; не блокирует DML |

ACCESS EXCLUSIVE на микросекунды (metadata) — не проблема. ACCESS EXCLUSIVE на минуты (rewrite или full scan) — катастрофа. Длительность зависит не от уровня блокировки, а от типа действия.

При этом даже мгновенный ACCESS EXCLUSIVE попадает в [очередь блокировок](../postgresql/concurrency/03-locks.md). Если в момент ALTER TABLE долгий SELECT держит ACCESS SHARE, ALTER TABLE ждёт — а все последующие запросы выстраиваются за ним. Ожидание в секунды терпимо. В минуты — весь трафик к таблице встаёт.

Таблицы предполагают одно действие на один ALTER TABLE. При объединении нескольких действий (`ALTER TABLE t ADD COLUMN ..., ALTER COLUMN ...`) PostgreSQL берёт самую строгую блокировку и удерживает до конца — metadata в паре с rewrite получает блокировку на всё время rewrite.

Операции с полным сканированием или перезаписью таблицы под ACCESS EXCLUSIVE опасны. Но у многих есть безопасные альтернативы.

## Ограничения без полного сканирования

### CHECK и FK — NOT VALID и VALIDATE

NOT VALID регистрирует ограничение, но не проверяет существующие строки — новые INSERT и UPDATE проверяются сразу, а старые данные пока нет:

```sql
ALTER TABLE orders ADD CONSTRAINT orders_amount_positive
  CHECK (amount > 0) NOT VALID;
```

Операция мгновенная — только запись в каталог. Блокировка берётся и отпускается за микросекунды (уровни блокировок для CHECK и FK — в таблице стоимости выше).

Второй шаг — VALIDATE CONSTRAINT. PostgreSQL проходит по всем существующим строкам и проверяет каждую на соответствие условию. Если все строки проходят — ограничение помечается как полностью проверенное. Если хоть одна строка нарушает условие — команда падает с ошибкой, ограничение остаётся NOT VALID, нужно сначала исправить данные и повторить.

Проверка идёт под более лёгкой блокировкой — SELECT и DML продолжают работать:

```sql
ALTER TABLE orders VALIDATE CONSTRAINT orders_amount_positive;
```

Для FK — VALIDATE сканирует обе таблицы (дочернюю и родительскую). На больших таблицах VALIDATE конфликтует с [VACUUM](../postgresql/maintenance/00-vacuum.md) и другим DDL — долгий VALIDATE может задержать очистку.

### NOT NULL

PostgreSQL 12+ видит validated CHECK с условием `IS NOT NULL` и пропускает сканирование при SET NOT NULL:

```sql
-- 1. Зарегистрировать CHECK (ACCESS EXCLUSIVE, мгновенно)
ALTER TABLE orders
  ADD CONSTRAINT orders_region_nn CHECK (region IS NOT NULL) NOT VALID;

-- 2. Проверить существующие строки (SHARE UPDATE EXCLUSIVE)
ALTER TABLE orders VALIDATE CONSTRAINT orders_region_nn;

-- 3. SET NOT NULL — мгновенно, PG видит validated CHECK
ALTER TABLE orders ALTER COLUMN region SET NOT NULL;

-- 4. Убрать вспомогательный CHECK
ALTER TABLE orders DROP CONSTRAINT orders_region_nn;
```

На PostgreSQL < 12 обход не работает — SET NOT NULL сканирует таблицу независимо от наличия CHECK.

CHECK, FK и NOT NULL можно добавить в два шага. Уникальные ограничения и первичные ключи требуют другого механизма.

## Уникальные ограничения и первичные ключи

`ADD UNIQUE(col)` и `ADD PRIMARY KEY(col)` берут ACCESS EXCLUSIVE и строят уникальный индекс — блокировка на всё время построения. На 50M строк — минуты.

Безопасный путь: создать уникальный индекс [неблокирующим способом](../sql/postgresql/04-index-operations.md), затем привязать constraint к готовому индексу через USING INDEX:

```sql
-- 1. SHARE UPDATE EXCLUSIVE — не блокирует DML
CREATE UNIQUE INDEX CONCURRENTLY idx_orders_external_id
  ON orders (external_id);

-- 2. ACCESS EXCLUSIVE, но мгновенно — привязка готового индекса
ALTER TABLE orders ADD CONSTRAINT orders_external_id_uq
  UNIQUE USING INDEX idx_orders_external_id;
```

USING INDEX привязывает существующий индекс к constraint без повторного построения. Работает только с plain B-tree индексами с default ordering — [частичные](../sql/schema/04-indexes.md#частичный-индекс) и [expression-индексы](../sql/schema/04-indexes.md#expression-индекс) привязать нельзя. Не поддерживается для партиционированных таблиц.

Для PRIMARY KEY — тот же рецепт, но столбец должен быть NOT NULL **до** USING INDEX. Если столбец nullable, PostgreSQL выполняет неявный SET NOT NULL с полным сканированием под ACCESS EXCLUSIVE — блокирующая операция. Безопасная последовательность: сначала safe NOT NULL через CHECK-паттерн (см. выше), затем USING INDEX.

### Дубликаты во время построения

Если на столбце уже есть уникальный constraint, дубликаты не появятся — существующий constraint защищает.

Если uniqueness создаётся впервые — перед запуском убедиться в отсутствии дубликатов:

```sql
SELECT external_id, COUNT(*)
FROM orders
WHERE external_id IS NOT NULL  -- NULL допустим в UNIQUE
GROUP BY external_id
HAVING COUNT(*) > 1;
```

[CONCURRENTLY build](../sql/postgresql/04-index-operations.md) проходит в две фазы. В первой уникальность ещё не проверяется — дубликаты, вставленные в это время, приведут к сбою build во второй фазе. Порядок:

1. Проверить дубликаты (SQL выше), вычистить если есть
2. Приостановить writes в столбец (переключатель в коде приложения), дождаться завершения in-flight транзакций
3. Запустить build
4. Если успех — возобновить writes
5. Если сбой — удалить [INVALID-индекс](../sql/postgresql/04-index-operations.md) (`DROP INDEX CONCURRENTLY`), разобраться с причиной, повторить с шага 3

Writes приостановлены на время build, не на время DROP — DROP просто убирает сломанный индекс.

Компромисс — build в период низкого трафика без приостановки writes. Окно для дубликатов короче, но не закрыто — если дубликат проскочит, build упадёт и нужно будет вычистить данные и повторить.

## Default-значения

ADD COLUMN с DEFAULT до PostgreSQL 11 перезаписывал каждую строку — table rewrite под ACCESS EXCLUSIVE.

PostgreSQL 11+ сохраняет default в системном каталоге: при чтении строки без этого столбца PostgreSQL подставляет сохранённое значение на лету. Строки не трогаются, операция мгновенная.

Условие: значение DEFAULT можно вычислить один раз и сохранить для всех строк. Константы (`42`, `'unknown'`) и `CURRENT_TIMESTAMP` — вычисляются один раз, мгновенно. `random()`, `gen_random_uuid()` — результат разный для каждой строки, PostgreSQL вынужден перезаписать каждую.

### Мгновенный — не значит корректный

Fast default с `CURRENT_TIMESTAMP` мгновенный по блокировкам, но все существующие строки получают **один** timestamp — время начала транзакции, в которой выполняется ALTER TABLE (потому что `CURRENT_TIMESTAMP` = `now()` = время начала транзакции). Для audit-столбцов (`created_at`, `updated_at`) это тихое искажение: миллионы строк с одинаковым временем, не соответствующим реальности.

Если существующие строки должны получить реальные значения — столбец добавляется nullable без DEFAULT, данные заполняются отдельно ([backfill](01-schema-evolution.md)), default ставится для будущих записей:

```sql
-- 1. Nullable, без DEFAULT (мгновенно)
ALTER TABLE orders ADD COLUMN region TEXT;

-- 2. Backfill реальными значениями (отдельная операция, см. Эволюция схемы)

-- 3. DEFAULT для будущих записей (опционально)
ALTER TABLE orders ALTER COLUMN region SET DEFAULT 'unknown';

-- 4. NOT NULL через safe CHECK-паттерн (если нужен)
```

## lock_timeout и statement_timeout

Добавить столбец, зарегистрировать CHECK NOT VALID, привязать USING INDEX — все эти операции мгновенны. Но каждая берёт ACCESS EXCLUSIVE. Если в момент выполнения долгий запрос держит ACCESS SHARE — ALTER TABLE встаёт в очередь, а за ним весь остальной трафик.

### lock_timeout — защита от очереди

[lock_timeout](../postgresql/concurrency/03-locks.md) ограничивает время ожидания блокировки. Если ALTER TABLE не получил блокировку за заданное время — операция отменяется, очередь не растёт:

```sql
SET lock_timeout = '5s';
ALTER TABLE orders ADD COLUMN is_verified BOOLEAN;
```

Не получил блокировку — повторить через несколько секунд. Если 3-5 попыток подряд неудачны — разобраться, какая транзакция держит блокировку (см. Диагностика).

### statement_timeout — защита от зависания

statement_timeout ограничивает **общее** время выполнения команды — от момента прихода на сервер до завершения, **включая ожидание блокировки**. Это важно: statement_timeout и lock_timeout перекрываются на фазе ожидания.

Если `statement_timeout` <= `lock_timeout`, lock_timeout бесполезен — statement_timeout сработает раньше. Правило: **lock_timeout строго меньше statement_timeout**:

```sql
SET lock_timeout = '5s';          -- ожидание блокировки: max 5 секунд
SET statement_timeout = '30s';    -- общее время (включая ожидание): max 30 секунд
ALTER TABLE orders ADD COLUMN is_verified BOOLEAN;
```

lock_timeout защищает от очереди (быстрый отказ, если блокировка занята). statement_timeout ограничивает общее время — если операция получила блокировку, но выполняется слишком долго (неожиданный scan, rewrite), statement_timeout остановит её.

**Антипаттерн:** `SET statement_timeout = '0'` в начале миграции. Убирает защиту: table rewrite, неожиданный full scan или ошибочный backfill работают без ограничений.

Для долгих операций (CREATE INDEX CONCURRENTLY, VALIDATE на больших таблицах) timeout нужно поднимать **точечно**:

```sql
SET lock_timeout = '5s';
SET statement_timeout = '30min';
CREATE INDEX CONCURRENTLY idx_orders_region ON orders (region);
SET statement_timeout = '30s';  -- вернуть обратно
```

CREATE INDEX CONCURRENTLY не работает в транзакции, поэтому SET — session-scoped. Если операция упадёт до сброса, сессия остаётся с 30-минутным timeout — следующие шаги миграции теряют защиту.

Безопасные варианты:
- ensure/finally в коде фреймворка (гарантирует сброс даже при ошибке)
- отдельное соединение для долгой операции (закрытие соединения сбрасывает все session-level SET)

## Диагностика

```sql
-- Долгие открытые транзакции (блокируют DDL, мешают VACUUM)
SELECT pid, usename, state, query,
       now() - xact_start AS tx_duration
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
  AND datname = current_database()
ORDER BY xact_start;
```

```sql
-- INVALID-индексы после сбоя CONCURRENTLY
SELECT indexrelid::regclass AS index_name
FROM pg_index
WHERE NOT indisvalid;
```

```sql
-- Забытые транзакции (idle in transaction)
SELECT pid, usename, now() - xact_start AS tx_duration
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND datname = current_database();
```

Если приложение использует [реплики](../postgresql/distribution/00-replication.md) — при длительных backfill-операциях следить за replication lag: массовые UPDATE генерируют [WAL](../postgresql/durability/00-wal.md) (Write-Ahead Log — журнал предзаписи), replica может отставать.

## Практические правила

Каждая DDL-операция попадает в одну из четырёх категорий:

**Safe online** — не блокирует DML:
- NOT VALID → VALIDATE (CHECK, FK)
- CHECK → VALIDATE → SET NOT NULL
- CREATE INDEX CONCURRENTLY
- CONCURRENTLY → USING INDEX (если uniqueness уже enforced)
- ADD COLUMN с DEFAULT, вычисляемым один раз

**Queue-sensitive** — мгновенно, но lock_timeout + retry:
- ADD COLUMN без DEFAULT
- ADD CHECK NOT VALID
- ADD FK NOT VALID (обе таблицы)

**App-unsafe** — DDL мгновенный, код ломается при rolling deploy:
- DROP COLUMN, RENAME COLUMN → [expand-contract](01-schema-evolution.md)

**Downtime / expand-contract:**
- ALTER COLUMN TYPE с перезаписью

Версии PG, ограничения паттернов (plain B-tree для USING INDEX, партиционированные таблицы) — в таблице стоимости выше и в [обзоре серии](index.md).

## Sources

- PostgreSQL Documentation (v17): ALTER TABLE. <https://www.postgresql.org/docs/17/sql-altertable.html>
- PostgreSQL Documentation (v17): CREATE INDEX. <https://www.postgresql.org/docs/17/sql-createindex.html>
- PostgreSQL Documentation (v17): Explicit Locking. <https://www.postgresql.org/docs/17/explicit-locking.html>
- Brandur Leach: Fast Column Creation with Defaults in PostgreSQL. <https://brandur.org/postgres-default>

---

← [Обзор серии](index.md) | [Эволюция схемы](01-schema-evolution.md) →
