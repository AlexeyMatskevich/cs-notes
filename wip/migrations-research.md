---
phase: research
status: draft
topic: Database Migrations
files: []
---

# Research: Database Migrations

## Состояние репозитория

### DDL-покрытие (хорошее, 8 файлов)

**Core DDL** — `databases/sql/schema/` (5 файлов, ~584 строк):
- `00-tables-and-types.md` — CREATE TABLE, типы, DEFAULT, SERIAL/IDENTITY, ALTER TABLE, DROP TABLE
- `01-constraints.md` — NOT NULL, PK, UNIQUE, FK, CHECK, DEFERRABLE, CASCADE
- `02-partitioning.md` — логическое/физическое разделение, RANGE/LIST/HASH, trade-offs
- `03-views.md` — CREATE VIEW, обновляемые views, views как слой доступа
- `04-indexes.md` — CREATE INDEX, composite, partial, expression, INCLUDE, когда помогает/вредит

**PG-расширения SQL** — `databases/sql/postgresql/` (3 файла, ~143 строк production DDL):
- `04-index-operations.md` — CREATE INDEX CONCURRENTLY, типы блокировок, INVALID-индексы, REINDEX CONCURRENTLY
- `06-partitioning.md` — декларативное партиционирование, partition pruning, retention через DROP
- `07-materialized-views.md` — материализованные views, REFRESH CONCURRENTLY

**Смежный контент в `databases/postgresql/`:**
- `concurrency/03-locks.md` — уровни блокировок, матрица совместимости, lock queue, lock_timeout, advisory locks
- `storage/01-pages-and-tuples.md` — формат tuple, почему rewrite дорогой
- `maintenance/00-vacuum.md` — VACUUM, bloat

### Качество существующих заметок

Высокое. Паттерны, которые работают:
- **Scenario-first:** constraints открывается с «три микросервиса пишут невалидные данные»
- **Causal pedagogy:** проблема → почему это важно → решение → trade-off
- **Этимология и binding:** «PRIMARY KEY = UNIQUE + NOT NULL», «DEFERRABLE (англ. 'отложенная')»
- **Конкретные числа:** 50M строк, 400MB индексы, EXPLAIN output с реальными cost
- **Trade-off transparency:** «Индекс ускоряет чтение, но замедляет запись»
- **Предпосылки contract:** каждый файл явно объявляет зависимости

Слабости: `02-partitioning.md` краток (40 строк), нет cross-links к concurrency-контенту из DDL-заметок.

### Миграции в репозитории

**Ноль.** Ни одного файла. Слово «миграция» встречается только в контексте Redis cluster (миграция реплик) и Linux (kernel threads). Материал по миграциям БД отсутствует полностью.

### Пробелы, которые заполнит новый материал

Текущие DDL-заметки учат **что** менять. Отсутствует полностью: **как** менять безопасно, когда есть данные и трафик. Конкретно:
- ALTER TABLE locking behavior и длительность по операциям
- Безопасное добавление NOT NULL, constraints, indexes на существующих таблицах
- Expand-contract паттерн
- Deploy-migrate ordering
- Schema vs data миграции
- Backfilling
- Reversibility

## Зависимости

### Кандидаты в предпосылки (прямые)

| Файл | Что даёт |
|------|----------|
| `databases/sql/schema/00-tables-and-types.md` | CREATE TABLE, ALTER TABLE, DROP TABLE, DEFAULT |
| `databases/sql/schema/01-constraints.md` | NOT NULL, UNIQUE, FK, CHECK, DEFERRABLE, CASCADE |
| `databases/sql/schema/04-indexes.md` | CREATE INDEX, composite, partial, expression |
| `databases/sql/modification/01-transactions.md` | Транзакции, COMMIT, ROLLBACK |
| `databases/sql/postgresql/04-index-operations.md` | CONCURRENTLY, INVALID, REINDEX |
| `databases/postgresql/concurrency/03-locks.md` | Уровни блокировок, матрица совместимости, lock queue |

### Файлы, которые потребуют каскадных обновлений

| Файл | Что менять |
|------|-----------|
| `databases/sql/index.md` | Добавить `migrations/` в study order и навигацию |
| `databases/sql/schema/00-tables-and-types.md` | Cross-link на миграции в секции ALTER TABLE |
| `databases/sql/schema/01-constraints.md` | Cross-link: «добавление constraints на существующие таблицы → migrations» |
| `databases/sql/schema/04-indexes.md` | Cross-link на миграции для production-сценариев |
| `databases/sql/postgresql/04-index-operations.md` | Cross-link на миграции (контекст: зачем CONCURRENTLY) |
| `databases/postgresql/concurrency/03-locks.md` | Cross-link на миграции (DDL и блокировки на практике) |
| `CLAUDE.md` | Обновить file map (добавить `databases/migrations/`) |

## Характеристики

- **Слой знания:** прикладной (опирается на механизмы DDL и concurrency, но фокус — практика безопасных изменений)
- **Scope:**

**IN:**
- Почему DDL недостаточно (4 оси: данные, трафик, несколько версий кода, необратимость)
- Safe/unsafe операции с PG-спецификой (lock levels per DDL, fast defaults PG11+, safe NOT NULL через CHECK PG12+, NOT VALID/VALIDATE)
- Expand-contract паттерн
- Deploy-migrate ordering и backward compatibility constraint
- Schema vs data миграции (и почему их нельзя мешать)
- Backfilling strategies (batched, lazy, background)
- lock_timeout / statement_timeout в контексте миграций
- Forward-only vs reversible миграции

**OUT:**
- Конкретные фреймворки (ActiveRecord, Flyway, Alembic, Diesel) — будущие курсы поверх этого фундамента
- Blue-green deployments (system-design)
- Feature flags (отдельная тема)
- CI/CD pipeline для миграций
- Репликация и миграции (уже покрыто в distribution/)
- Monitoring в деталях (полные dashboards, alerting) — но минимальный операционный checklist (pg_locks, pg_index.indisvalid, replication lag, idle-in-transaction) IN scope
- Partitioning migrations (слишком специфично)

## Внешние источники

### Универсальные концепции

**Schema vs data миграции.** Schema migration меняет структуру (ADD COLUMN, CREATE INDEX). Data migration меняет значения (backfill, transform, merge). Смешивание в одной миграции создаёт проблемы: schema change блокирует таблицу, data backfill держит эту блокировку минутами. Best practice: разделять.

**Expand-contract (parallel change).** Пять шагов со строгими gates:
1. **Expand schema:** добавить новую структуру рядом со старой.
2. **Deploy dual-write:** rolling deploy кода, который пишет в оба столбца. **Invariant: atomic dual-write** — оба столбца обновляются в одной транзакции (один UPDATE с обоими столбцами, или trigger/view на стороне базы). Два отдельных statement без транзакции могут diverge при partial failure → inconsistency. **Gate: ВСЕ instances обновлены** — ни один writer не пишет только в старый столбец. Без этого gate backfill бесполезен.
3. **Backfill:** заполнить старые строки + tail-sweep для late-commit. **Gate: начинать только после п.2.**
4. **Switch reads:** переключить чтение на новый столбец. Два gate-а:
   **Gate A — transaction drain:** убедиться, что pre-rollout транзакции (начатые до deploy dual-write) завершились. Без этого они могут коммитить строки без нового столбца после tail-sweep. Проверка по `xact_start` (начало транзакции, НЕ `backend_start` — это время подключения):
   **Предпочтительный вариант: application-level deploy barrier** — все instances подтвердили переход на dual-write, `$deploy_timestamp` берётся из базы через `SELECT clock_timestamp()` в fresh autocommit connection (`now()` возвращает время начала транзакции, не wall clock — если вызвать внутри существующей транзакции, cutoff будет неточным). Это надёжнее pg_stat_activity.

   **Fallback: pg_stat_activity** (valid только при полном inventory writers — все приложения, job workers, ETL, admin scripts используют одинаковый application_name или подключаются через один role; если есть неизвестные writers — fallback ненадёжен, нужен application barrier):
   ```sql
   SELECT count(*) FROM pg_stat_activity
   WHERE xact_start < $deploy_timestamp
     AND xact_start IS NOT NULL
     AND datname = current_database()
     AND pid <> pg_backend_pid()
     AND application_name LIKE 'myapp%';  -- scope к приложению
   ```
   Ждать пока count = 0. Без scope по datname/application_name на shared cluster любая unrelated транзакция блокирует cutover. Edge case: `pg_stat_activity` не показывает prepared transactions (2PC) — если используется distributed transactions, проверять также `pg_prepared_xacts`. Не полагаться на `idle_in_transaction_session_timeout` — он часто 0 (отключён) по умолчанию.

   **Replica catch-up gate (advanced — требует знание [репликации](../../postgresql/distribution/00-replication.md)):** если приложение читает с replicas — LSN barrier capture непосредственно перед Switch reads (ПОСЛЕ drain + convergence, не после backfill — между backfill и switch reads проходят drain/convergence, за это время трафик продолжается):
   ```sql
   -- На primary: capture barrier НЕПОСРЕДСТВЕННО перед switch reads
   SELECT pg_current_wal_lsn();  -- $cutover_lsn
   -- На каждой replica: ждать replay
   SELECT pg_last_wal_replay_lsn() >= $cutover_lsn;
   ```
   Ждать пока ВСЕ serving replicas replay >= $cutover_lsn. Caveat: hot-standby snapshots — уже открытые транзакции на replica сохраняют старый snapshot даже после replay catch-up. Для типичных web-приложений (short-lived autocommit reads) это не проблема — новые запросы получают fresh snapshot. Для long-lived replica transactions (reporting, analytics) — drain перед cutover или перенаправить на primary. Если приложение читает только с primary — gate не нужен.
   **Gate B — convergence verified (stable):** критерий зависит от типа миграции, проверяется ДВАЖДЫ с интервалом ≥ max transaction lifetime:
   - Простое добавление столбца: `COUNT(*) WHERE new_col IS NULL = 0`
   - Rename/copy: `COUNT(*) WHERE new_col IS DISTINCT FROM old_col = 0`
   - Type change с transform: валидация формата/значений в новом столбце
   - Split: проверка что все строки присутствуют в целевых таблицах
   Если повторная проверка показывает новые расхождения — late commits, нужен ещё один tail-sweep + повторная проверка.
   Non-NULL ≠ correct: столбец может быть заполнен stale или default значениями при неполном dual-write.
5. **Contract:** удалить старую структуру. **Gate: все readers и writers на новом столбце.**

Универсален для любой RDBMS. Примеры: rename column, change type, split table. Источник: Martin Fowler, Parallel Change (bliki).

**Deploy-migrate ordering.** Migrate-first: сначала миграция, потом deploy. Старый код должен работать с новой схемой. Deploy-first: сначала deploy, потом миграция. Новый код должен работать со старой схемой. В обоих случаях — есть окно, когда одна версия кода работает с обеими схемами. **Backward compatibility constraint** — ключевое следствие.

**Forward-only vs reversible.** Reversible (Rails `change`) удобен для простых операций. Но DROP COLUMN, data transformations, type changes практически необратимы. Forward-only честнее: заставляет планировать recovery path. Практика: reversible для add column/index, forward-only для destructive.

**Backfilling strategies:**
- Single UPDATE — просто, но блокирует строки, генерирует WAL, может перегрузить базу
- Batched (restart-safe) — PG не поддерживает `UPDATE ... LIMIT`. Два паттерна в зависимости от типа ключа:

  **Sequential integer PK (id BIGINT):** range windows + idempotent predicate:
  ```sql
  UPDATE orders SET region = 'unknown'
  WHERE id BETWEEN 1 AND 10000 AND region IS NULL;
  -- пауза для снижения нагрузки
  UPDATE orders SET region = 'unknown'
  WHERE id BETWEEN 10001 AND 20000 AND region IS NULL;
  ```
  Предусловие: PK numeric (BIGSERIAL, IDENTITY). На sparse IDs (пробелы от удалений) строки НЕ теряются — просто часть батчей будет пустой (waste, не loss). На UUID ключах range windows неприменимы (нет числового BETWEEN). **Late-commit caveat (как у high-water-mark):** sequence values выделяются до commit и не откатываются — транзакция может выделить id=5000, коммитить после прохода batch 1..10000. Mandatory tail-sweep `WHERE region IS NULL` после основного прохода обязателен для обоих паттернов (range windows и cursor-based).

  **Любой монотонный PK (BIGSERIAL, IDENTITY):** cursor-based batch с high-water mark. Примечание: UUID v7 time-ordered, но не гарантирует total order across generators/skewed clocks — использовать как watermark key только с mandatory tail-sweep; безопаснее относить к «любой PK» и использовать CTE-batch без high-water mark. Cursor-based batch — отслеживаем последний обработанный ключ, чтобы не сканировать с начала на каждом батче. Guard `AND region IS NULL` повторяется в outer UPDATE для защиты от race condition (другой процесс мог заполнить region между SELECT и UPDATE):
  ```sql
  -- Батч: обработать следующие 10K строк после $last_id
  WITH batch AS (
    SELECT id FROM orders
    WHERE region IS NULL AND id > $last_id
    ORDER BY id LIMIT 10000
  )
  UPDATE orders SET region = 'unknown'
  FROM batch
  WHERE orders.id = batch.id AND orders.region IS NULL;
  -- $last_id = MAX(id) из batch CTE
  -- Повторять пока batch не пуст
  ```
  `$last_id` — persisted cursor (переменная приложения или checkpoint-таблица). Без него каждый батч сканирует с начала таблицы. `orders.region IS NULL` в outer UPDATE — idempotent guard: если между SELECT и UPDATE строка уже заполнена другим процессом, она пропускается, а не перезаписывается. Предполагает single worker и один монотонно-упорядоченный ключ (BIGSERIAL, IDENTITY); для composite PK нужен tuple cursor `(col1, col2) > ($last_col1, $last_col2)`, для параллельных workers — claiming (FOR UPDATE SKIP LOCKED или work table).

  **Late-commit hazard:** high-water mark не гарантирует полный охват. Транзакция может выделить id, не коммитить пока backfill пройдёт мимо, и коммитить позже — строка останется с `region IS NULL` навсегда. Решение: **batched tail-sweep** — после основного прохода с high-water mark выполнить финальный проход без cursor (по умолчанию — batched, чтобы не создать тот же full-table UPDATE, от которого мы уходили):
  ```sql
  -- Batched tail-sweep (дефолт): CTE с PK-order для предсказуемого I/O
  WITH batch AS (
    SELECT id FROM orders WHERE region IS NULL ORDER BY id LIMIT 10000
  )
  UPDATE orders SET region = 'unknown'
  FROM batch WHERE orders.id = batch.id AND orders.region IS NULL;
  -- Повторять пока batch не пуст
  ```
  PK-order помогает планировщику выбрать Index Scan вместо Seq Scan (PK index поддерживает ORDER BY id), но это не гарантия — планировщик может выбрать Seq Scan при определённых условиях (высокая доля NULL-строк, устаревшая статистика). Проверять через `EXPLAIN` перед запуском на production. Для очень sparse residuals (единицы строк на миллионы) — partial index `CREATE INDEX CONCURRENTLY ON orders(id) WHERE region IS NULL` ускорит поиск (CONCURRENTLY обязателен на live-таблице; plain CREATE INDEX блокирует writes). One-shot `UPDATE ... WHERE region IS NULL` допустим только при подтверждённо малом остатке (`SELECT COUNT(*) ... IS NULL` < ~1000 строк).

  Общее: idempotent predicate (`WHERE region IS NULL`) гарантирует, что при повторе батча строки не обрабатываются дважды. Пауза между батчами ограничивает lock duration, WAL volume, replication lag.
- Background job — асинхронно. Код обрабатывает и NULL, и заполненные строки
- Lazy backfill — значение вычисляется при следующем чтении/записи

### PostgreSQL-специфика

**ALTER TABLE lock levels.** Почти все ALTER TABLE подкоманды берут ACCESS EXCLUSIVE. Ключевое: **длительность** важнее уровня блокировки. ACCESS EXCLUSIVE на микросекунды (metadata-only) — ок. ACCESS EXCLUSIVE на минуты (table rewrite) — катастрофа.

Таблица операций:

| Операция | Lock | Что делает | Длительность |
|----------|------|-----------|-------------|
| ADD COLUMN (no default / non-volatile default PG11+) | ACCESS EXCLUSIVE | metadata | мгновенно |
| ADD COLUMN (volatile default) | ACCESS EXCLUSIVE | table rewrite | пропорционально размеру |
| DROP COLUMN | ACCESS EXCLUSIVE | metadata | мгновенно |
| ALTER COLUMN TYPE (rewrite case) | ACCESS EXCLUSIVE | table rewrite + index rebuild | пропорционально размеру |
| ALTER COLUMN TYPE (no-rewrite exceptions: binary-coercible, varchar(N)→varchar(M) M>N, some domain) | ACCESS EXCLUSIVE | no heap rewrite, но index rebuild возможен если индексы зависят от типа | мгновенно для heap, но index rebuild может занять время; не считать online-safe по умолчанию |
| ALTER COLUMN SET NOT NULL | ACCESS EXCLUSIVE | full table scan | пропорционально размеру |
| RENAME COLUMN | ACCESS EXCLUSIVE | metadata | мгновенно |
| ADD CHECK/NOT NULL/UNIQUE (validated) | ACCESS EXCLUSIVE | scan | пропорционально размеру |
| ADD FOREIGN KEY (validated) | SHARE ROW EXCLUSIVE (на обеих таблицах) | scan | пропорционально размеру |
| ADD CHECK ... NOT VALID | ACCESS EXCLUSIVE | metadata (без scan) | мгновенно (lock сильный, но держится микросекунды) |
| ADD FOREIGN KEY ... NOT VALID | SHARE ROW EXCLUSIVE (на обеих таблицах: child + parent) | metadata (без scan) | мгновенно, но queue-sensitive на parent table |
| VALIDATE CONSTRAINT (CHECK) | SHARE UPDATE EXCLUSIVE | scan | пропорционально размеру; не блокирует DML, но конфликтует с VACUUM и другим DDL |
| VALIDATE CONSTRAINT (FK) | SHARE UPDATE EXCLUSIVE (child) + ROW SHARE (parent) | scan обеих таблиц | пропорционально размеру; не блокирует DML, но берёт lock на обеих таблицах — учитывать при планировании DDL на parent |
| CREATE INDEX | SHARE | build | пропорционально размеру, блокирует writes |
| CREATE INDEX CONCURRENTLY | SHARE UPDATE EXCLUSIVE | two-phase build | дольше; не блокирует DML, но конфликтует с VACUUM и другим DDL |

**PG11 fast default.** До PG11: `ADD COLUMN ... DEFAULT 42` перезаписывал каждую строку. PG11+: default хранится в `pg_attribute.attmissingval`, строки не трогаются, операция мгновенна. Условие: default expression non-volatile (константы, `CURRENT_TIMESTAMP` — ок, `random()` — rewrite). Источник: Brandur, "Fast Column Creation with Defaults".

**Operationally safe ≠ semantically correct.** Fast default с `CURRENT_TIMESTAMP` мгновенный по блокировкам, но все существующие строки получают ОДИН timestamp — момент выполнения ALTER TABLE. Для audit-колонок (`created_at`, `updated_at`) это тихое искажение: миллионы строк получают одинаковое время, не соответствующее реальности.

**Backfill invariant: столбец для backfill добавляется nullable без DEFAULT.** Если ADD COLUMN с DEFAULT (например `DEFAULT 'unknown'`), все существующие строки сразу получают non-NULL значение → `WHERE region IS NULL` ничего не находит → backfill считает себя завершённым, хотя данные содержат placeholder. Правильная последовательность:
1. ADD COLUMN nullable, без DEFAULT
2. Backfill реальными значениями (WHERE col IS NULL работает корректно)
3. SET DEFAULT для будущих записей (если нужен)
4. SET NOT NULL (через safe CHECK-паттерн)

Это правило применяется к ЛЮБОМУ столбцу, который нужно backfill-ить — будь то audit-колонка, computed value, или data migration.

**Safe NOT NULL (PG12+).**
```sql
ALTER TABLE t ADD CONSTRAINT c_not_null CHECK (c IS NOT NULL) NOT VALID;  -- ACCESS EXCLUSIVE, но мгновенно (metadata)
ALTER TABLE t VALIDATE CONSTRAINT c_not_null;                             -- scan, не блокирует
ALTER TABLE t ALTER COLUMN c SET NOT NULL;                                -- мгновенно (PG видит validated CHECK)
ALTER TABLE t DROP CONSTRAINT c_not_null;                                 -- cleanup
```
Без этого паттерна SET NOT NULL сканирует всю таблицу под ACCESS EXCLUSIVE.

**NOT VALID / VALIDATE CONSTRAINT.** Двухшаговый паттерн для CHECK и FK. NOT VALID регистрирует constraint без проверки существующих строк (новые INSERT/UPDATE проверяются). VALIDATE сканирует под SHARE UPDATE EXCLUSIVE — не блокирует SELECT/INSERT/UPDATE/DELETE, но конфликтует с VACUUM и другим DDL (другой VALIDATE, CREATE INDEX CONCURRENTLY). На таблицах с активным autovacuum долгий VALIDATE может задержать очистку мёртвых строк. Важный нюанс: CHECK NOT VALID всё равно берёт ACCESS EXCLUSIVE — NOT VALID убирает scan, но не снижает уровень блокировки. Операция мгновенная (metadata), поэтому lock держится микросекунды. FK NOT VALID берёт более слабый SHARE ROW EXCLUSIVE.

**CREATE INDEX CONCURRENTLY.** Многофазный: первый scan → ждёт завершения старых транзакций → второй scan → mark valid. Trade-offs: дольше, не работает в транзакции, может упасть оставив INVALID-индекс.

**Safe UNIQUE / PRIMARY KEY (не-partitioned таблицы).** Обычный `ALTER TABLE ... ADD UNIQUE(col)` или `ADD PRIMARY KEY(col)` берёт ACCESS EXCLUSIVE и сканирует таблицу (строит уникальный индекс). На больших таблицах — блокировка на минуты. Безопасный путь: создать уникальный индекс неблокирующим способом, затем привязать constraint к готовому индексу:
```sql
-- Шаг 1: неблокирующее создание индекса
CREATE UNIQUE INDEX CONCURRENTLY idx_orders_external_id ON orders (external_id);

-- Шаг 2: привязать constraint к готовому индексу (мгновенно, ACCESS EXCLUSIVE на микросекунды)
ALTER TABLE orders ADD CONSTRAINT orders_external_id_uq UNIQUE USING INDEX idx_orders_external_id;
```
Для PRIMARY KEY аналогично, но столбец должен быть NOT NULL **до** USING INDEX. Если столбец nullable:
- `ADD PRIMARY KEY ... USING INDEX` — PG выполняет **implicit SET NOT NULL с full table scan** под ACCESS EXCLUSIVE (документация: «That requires a full table scan to verify the column(s) contain no nulls»). Это блокирующая операция, которая ломает «online» характер рецепта.
- `ADD PRIMARY KEY(col)` без USING INDEX — аналогично implicit SET NOT NULL + построение индекса, всё блокирующее.
В обоих случаях: если столбец nullable — сначала safe NOT NULL через CHECK-паттерн (см. выше), потом USING INDEX. Только так рецепт остаётся online.

**Предусловие — uniqueness на протяжении build.** CREATE UNIQUE INDEX CONCURRENTLY работает в две фазы. В первой фазе (первый scan) PG строит предварительный индекс — uniqueness ещё НЕ enforced, дубликаты могут быть вставлены. Во второй фазе (второй scan) PG начинает enforce uniqueness для новых записей — INSERT с дубликатом получит ошибку или build упадёт. Итого: между началом build и началом второго скана есть окно, в которое дубликаты могут проскочить и вызвать сбой build. После сбоя INVALID index может продолжать enforce uniqueness (reject inserts) до явного DROP.

Проверка существующих данных (учитывая NULL-семантику: PG UNIQUE по умолчанию допускает multiple NULLs, поэтому NULL-строки не являются дубликатами):
```sql
SELECT external_id, COUNT(*)
FROM orders
WHERE external_id IS NOT NULL  -- NULL допустим в UNIQUE, не считается дубликатом
GROUP BY external_id
HAVING COUNT(*) > 1;
```
Для UNIQUE с `NULLS NOT DISTINCT` (PG15+) убрать фильтр по NULL.

Защита от новых дубликатов во время build:
- **Уже есть unique constraint/index на этот столбец:** ON CONFLICT работает, дубликаты не появятся. Но если мы СОЗДАЁМ uniqueness впервые — ON CONFLICT бесполезен (ему нужен существующий unique index для арбитража).
- **Uniqueness создаётся впервые:** до завершения CONCURRENTLY build нет database-enforced гарантии. **Safe path** (единственный online-safe вариант):
  - Временная блокировка writes на уровне приложения (feature flag) — writes в столбец приостанавливаются на время build
  **Unsafe compromises** (не online-safe, failure mode = INVALID index + manual cleanup + write errors до DROP):
  - Build в период низкого трафика (ночь) — минимизирует окно для дубликатов, не устраняет. При сбое: INVALID index продолжает reject inserts до явного DROP CONCURRENTLY
  - Accept risk — если дубликаты крайне маловероятны по бизнес-логике. При сбое: тот же failure mode. Это осознанный компромисс, не safe pattern
- **Во всех случаях:** если build упал — INVALID index, немедленный DROP, cleanup дубликатов, повтор.

Если дубликаты есть — сначала data cleanup (merge, delete), потом index build.

**Recovery при сбое — немедленный DROP.** Если CONCURRENTLY упал после начала второго скана, PG продолжает enforce uniqueness через INVALID-индекс: INSERT с дубликатом будет отвергнут, хотя constraint формально не создан. Это опасное полусостояние — нужно удалить INVALID-индекс сразу, не откладывая:
```sql
-- Проверить INVALID-индексы
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
-- Удалить немедленно
DROP INDEX CONCURRENTLY idx_orders_external_id;
-- Повторить build после устранения причины сбоя
```

**Ограничение:** `ADD CONSTRAINT ... USING INDEX` не поддерживается для partitioned таблиц. Для partitioned таблиц нужен другой workflow (создание индексов per-partition + ATTACH). Partitioned-table миграции выходят за рамки этой серии.

**lock_timeout vs statement_timeout.** Оба — session-scoped SET, оба требуют reset после миграции (или disposable connection). lock_timeout — максимум ожидания блокировки (ставить 2-5s для DDL, сбрасывать после). statement_timeout — максимум **общего** времени команды от прихода на сервер до завершения, **включая ожидание блокировки**. lock_timeout должен быть строго меньше statement_timeout — иначе statement_timeout сработает раньше и lock_timeout бесполезен (PG docs: «it is rather pointless to set lock_timeout to the same or larger value, since the statement timeout would always trigger first»). Оставлять конечным! По умолчанию — разумное значение для миграций, например 30s-60s. Поднимать точечно только для конкретных долгих операций: CONCURRENTLY, VALIDATE CONSTRAINT на больших таблицах — и сразу возвращать обратно. Антипаттерн: `SET statement_timeout = '0'` — убирает защиту; rewrite, плохой backfill или неожиданный full scan работают без ограничений. Паттерн:
```sql
SET lock_timeout = '5s';
-- для обычного DDL: statement_timeout остаётся конечным
ALTER TABLE t ADD COLUMN is_verified BOOLEAN DEFAULT false;  -- non-backfill column: default ok
```

Для долгих операций (CONCURRENTLY, VALIDATE на больших таблицах) timeout нужно поднимать точечно. Проблема: CONCURRENTLY не работает в транзакции, поэтому SET — session-scoped. Если операция упадёт до сброса timeout, сессия останется с 30-минутным лимитом, и следующие шаги миграции потеряют защиту.

```sql
-- Безопасный паттерн: ensure/finally или отдельное соединение
SET statement_timeout = '30min';
CREATE INDEX CONCURRENTLY idx_orders_region ON orders (region);
SET statement_timeout = '30s';  -- ОБЯЗАТЕЛЬНО: сбросить даже при ошибке выше
```

На уровне фреймворка это ensure/finally блок. Если фреймворк не гарантирует сброс — безопаснее выполнять долгую операцию в отдельном соединении, которое закрывается после неё (закрытие соединения сбрасывает все session-level SET).

**Advisory locks.** Миграционные фреймворки используют `pg_advisory_lock` (session-level) для предотвращения параллельного запуска миграций. Проблема с PgBouncer в transaction mode: session-level advisory locks привязаны к backend-соединению, а transaction pooling переназначает соединения между транзакциями — lock может «утечь» к другому клиенту или быть потерян. `pg_advisory_xact_lock` (transaction-scoped) здесь не помогает: миграции часто охватывают несколько транзакций (CONCURRENTLY не работает в транзакции, batched backfill — отдельные транзакции), и lock освободится между ними, позволив второму процессу войти. **Единственный надёжный вариант:** прямое подключение к PostgreSQL для миграций, минуя PgBouncer (или PgBouncer в session mode на отдельном порту).

### Типичные заблуждения (для педагогического дизайна)

1. «ADD COLUMN мгновенный» — да, PG11+ с non-volatile default. Volatile default — rewrite. И ACCESS EXCLUSIVE, даже кратко, встаёт в очередь за долгими запросами.
2. «NOT NULL — просто флаг» — нет, SET NOT NULL сканирует всю таблицу. Нужен CHECK workaround (PG12+).
3. «RENAME COLUMN безопасен» — DDL мгновенный, но код ломается при rolling deploy. Нужен expand-contract.
4. «Миграция в транзакции = атомарно» — но CONCURRENTLY не работает в транзакции. Data backfill в транзакции держит блокировки всё время.
5. «Если миграция упала — откатываем» — DROP COLUMN уничтожает данные. Partial backfill требует undo миллионов строк.
6. «Migrate-then-deploy = нет проблем совместимости» — старый код должен работать с новой схемой.
7. «Advisory locks решают все проблемы параллелизма» — только между процессами миграции. Не защищают от конфликтов с application queries. Ломаются с PgBouncer.
8. «Table rewrite = ACCESS EXCLUSIVE» — lock одинаковый, но длительность отличается на порядки. ADD COLUMN без default: микросекунды. ALTER TYPE: минуты.
9. «lock_timeout спасает» — предотвращает бесконечное ожидание, но нужна retry strategy. Не помогает с операциями, которые держат lock (rewrite).
10. «CREATE INDEX CONCURRENTLY всегда безопасен» — безопаснее, но может упасть с INVALID-индексом. Не работает в транзакции. Занимает больше времени.

### Ключевые источники

**Документация PostgreSQL:**
- ALTER TABLE — https://www.postgresql.org/docs/current/sql-altertable.html
- Explicit Locking — https://www.postgresql.org/docs/current/explicit-locking.html
- CREATE INDEX (CONCURRENTLY) — https://www.postgresql.org/docs/current/sql-createindex.html

**Инструменты и чеклисты:**
- strong_migrations (ankane) — https://github.com/ankane/strong_migrations — чеклист unsafe операций с safe альтернативами
- safe-pg-migrations (doctolib) — https://github.com/doctolib/safe-pg-migrations
- pgroll (xata) — https://github.com/xataio/pgroll — CLI для zero-downtime PG-миграций с expand-contract
- online_migrations (fatkodima) — https://github.com/fatkodima/online_migrations

**Статьи:**
- GoCardless: Zero-downtime Postgres migrations — the hard parts
- Brandur: Fast Column Creation with Defaults (PG11)
- PostgresAI: Zero-downtime schema migrations — lock_timeout and retries
- Xata: Schema changes and the Postgres lock queue
- Martin Fowler: Parallel Change (bliki)
- Prisma: Expand and Contract Pattern

## Видение автора

### Ключевое разделение DDL vs миграции

DDL учит *что* менять. Миграции учат *как* менять безопасно, когда есть данные и трафик. Это разные дисциплины, не расширение DDL. Поэтому — отдельный домен `databases/migrations/`, а не продолжение `databases/sql/schema/`.

### Разделение general/PG-specific

Следует существующему паттерну репозитория:
- `databases/sql/` (и `sql/postgresql/`) = как использовать SQL, включая PG-специфику на уровне практики
- `databases/postgresql/` = как устроен движок внутри (storage, MVCC, locks механизм)

В миграциях: general concepts + PG-specific practical patterns живут вместе в `databases/migrations/`. PG-специфика вплетена, как уже делается в `sql/postgresql/`. Внутренние механизмы PG (attmissingval, формат tuple, lock manager) — cross-references к существующим файлам в `databases/postgresql/`, новые файлы скорее всего не нужны.

**Важно:** в отличие от `databases/sql/postgresql/`, где PG-принадлежность очевидна из пути, `databases/migrations/` читается как generic. PG-специфика (lock levels, NOT VALID, CONCURRENTLY, fast defaults, version-gated features) должна быть явно маркирована в тексте — читатель не должен принять PG-рецепт за портируемый SQL.

**Execution environment contract:** safe patterns из этой серии предполагают прямое подключение к PG (не transaction-pooled PgBouncer), возможность выполнять DDL вне транзакции (для CONCURRENTLY), и ответственность за session-level state cleanup (statement_timeout). Это не тулинг — это контракт среды исполнения, без которого паттерны не работают.

### Файловая структура

Определяется на design-фазе. Количество файлов вытекает из narrative arc, не фиксируется заранее.

### Будущие курсы

Этот материал — фундамент. Поверх него планируются курсы по миграциям в конкретных фреймворках (ActiveRecord, Diesel, другие). Фреймворки полностью за пределами текущего scope.
