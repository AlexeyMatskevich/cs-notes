---
tags:
  - domain/migrations
  - theme/schema-evolution
  - theme/reliability
  - type/concept
aliases:
  - Schema Evolution
  - Expand-Contract
  - Backfilling
order: 1
---

# Эволюция схемы

**Предпосылки:** [безопасные изменения схемы](safe-schema-changes.md) (стоимость DDL, safe patterns, timeout discipline), [транзакции](../sql/modification/transactions.md) (уровни изоляции).

← [Безопасные изменения схемы](safe-schema-changes.md)

В [предыдущей заметке](safe-schema-changes.md) каждая отдельная DDL-команда рассматривалась сама по себе. Но [миграция](migrations.md) почти никогда не состоит из одной команды. Нужно: добавить столбец `region` в `orders`, начать писать в него из приложения, заполнить старые строки, потом запретить `NULL`. Между этими шагами база продолжает жить, а код в production видит промежуточные состояния схемы.

Главная проблема этой заметки — не синтаксис команд, а совместимость во время rollout: как пройти через промежуточные состояния так, чтобы старый и новый код не ломали друг друга.

## Совместимость кода и схемы

Безопасные отдельные команды не спасают сами по себе. Между ними проходит время, и в этом окне работает код, который ничего не знает о промежуточном состоянии схемы.

Добавили столбец `region`. Следующий шаг — deploy нового кода, который пишет в `region`. Между [миграцией](migrations.md) и завершением deploy — окно, в котором одна версия кода работает с двумя состояниями схемы.

При rolling deploy (постепенная замена экземпляров приложения: новые поднимаются, старые останавливаются по одному) окно ещё шире: часть экземпляров работает со старым кодом, часть с новым — одновременно. Каждая версия должна корректно работать с текущей схемой. Это **backward compatibility constraint** (англ. «ограничение обратной совместимости»).

Два порядка выполнения:

**Migrate-first** — сначала миграция, потом deploy. Старый код должен работать с новой схемой. Добавить nullable столбец — безопасно: старый код не знает про `region`, INSERT без `region` проставит NULL. Добавить NOT NULL без DEFAULT — старый код не пишет `region`, INSERT вернёт ошибку.

**Deploy-first** — сначала deploy, потом миграция. Новый код должен работать со старой схемой. Код уже обращается к `region`, но столбца ещё нет — SELECT вернёт ошибку.

В обоих случаях: **каждый шаг [миграции](migrations.md) проверять на совместимость с текущим и предыдущим кодом.** Примеры нарушений:

| Операция | Почему ломает |
|----------|--------------|
| ADD COLUMN ... NOT NULL (без DEFAULT) | Старый код не пишет в новый столбец → INSERT fails |
| DROP COLUMN | Старый код читает удалённый столбец → SELECT fails |
| RENAME COLUMN | Старый код использует старое имя → ошибка |

DROP COLUMN и RENAME COLUMN — мгновенный DDL, но ломают работающий код. Из [[databases/migrations/safe-schema-changes#практические-правила|классификации]]: «DDL-fast, app-unsafe». Для таких операций нужен expand-contract.

Один из базовых приёмов сохранить совместимость — не смешивать изменение схемы и массовую переработку данных в одну длинную транзакцию.

## Schema и data — два типа [миграций](migrations.md)

Schema [migration](migrations.md) меняет структуру: ADD COLUMN, CREATE INDEX, ADD CONSTRAINT. Data [migration](migrations.md) меняет значения: заполнить столбец, преобразовать формат, перенести данные между таблицами.

Если объединить оба типа в одной [транзакции](../sql/modification/transactions.md), `ALTER TABLE` берёт `ACCESS EXCLUSIVE`, и транзакция удерживает эту блокировку до `COMMIT` — включая весь `UPDATE` на 50M строк:

```sql
-- Антипаттерн: schema + data в одной транзакции
BEGIN;
ALTER TABLE orders ADD COLUMN region TEXT;           -- ACCESS EXCLUSIVE уже взят
UPDATE orders SET region = 'unknown';                -- UPDATE сам по себе берёт ROW EXCLUSIVE,
                                                     -- но более строгая блокировка от ALTER TABLE всё ещё удерживается
COMMIT;                                              -- ACCESS EXCLUSIVE снят
```

Важно: проблема не в том, что `UPDATE` внезапно стал `ACCESS EXCLUSIVE`. Проблема в том, что более строгая блокировка, взятая первым оператором, живёт до конца транзакции. Поэтому все запросы к `orders` — включая `SELECT` — заблокированы на время `UPDATE`. На 50M строк — минуты.

Если разделить:

```sql
-- Транзакция 1: schema (ACCESS EXCLUSIVE, мгновенно)
ALTER TABLE orders ADD COLUMN region TEXT;

-- Транзакция 2: data (ROW EXCLUSIVE, не блокирует чтение)
UPDATE orders SET region = 'unknown' WHERE region IS NULL;
```

Schema change берёт ACCESS EXCLUSIVE на микросекунды. Data change берёт [[databases/postgresql/concurrency/locks#автоматические-блокировки-при-записи|ROW EXCLUSIVE]] — уровень блокировки, который PostgreSQL автоматически берёт при UPDATE. ROW EXCLUSIVE совместим с ACCESS SHARE (SELECT), поэтому чтение продолжает работать. Даже UPDATE на 50M строк лучше разбить на батчи (см. Backfilling ниже), но принцип ясен: **одна миграция — один тип изменения**.

## Expand-contract

Expand-contract (англ. «расширить — сжать»; также parallel change) — универсальный паттерн для несовместимых изменений, обеспечивающий [zero-downtime deploy](../../system-design/reliability-patterns.md). Идея: новая структура существует рядом со старой, пока все данные и весь код не переключены.

Пять шагов на примере добавления `region` с NOT NULL:

**1. Expand schema** — добавить новую структуру:

```sql
ALTER TABLE orders ADD COLUMN region TEXT;  -- nullable, без DEFAULT
```

Столбец nullable и без DEFAULT. Если добавить DEFAULT (например, `'unknown'`), все существующие строки сразу получат non-NULL значение — и backfill не сможет отличить уже обработанные строки от необработанных (`WHERE region IS NULL` ничего не найдёт).

**2. Deploy dual-write** (англ. «двойная запись» — код пишет и в старую, и в новую структуру) — rolling deploy кода, который при каждом INSERT и UPDATE начинает заполнять `region`, не ломая старый путь записи. В этом примере старой структурой остаются поля-источники, из которых вычисляется `region`.

**Gate:** все экземпляры приложения обновлены. Ни один writer не вставляет строки без `region`. Без этого gate backfill бесполезен — новые строки без `region` появляются быстрее, чем backfill их заполняет. Но этого gate недостаточно для переключения чтения: в системе ещё может жить хвост транзакций, начатых до rollout.

**3. Backfill** — заполнить старые строки. Батчами, с паузами (подробности — ниже).

**Gate:** начинать **только после п.2** — иначе незафиксированные строки от old-code writers пропустят backfill.

**4. Switch reads** — переключить чтение на `region`. Перед этим нужно доказать три вещи: старый код больше не создаёт новые `NULL`, хвост старых транзакций уже дошёл, и читающие узлы видят заполненный столбец. Отсюда и три gate перед read cutover:

**Gate A — transaction drain.** Транзакции, начатые до deploy dual-write, могут закоммитить строки без `region` уже после основного backfill. Поэтому перед переключением чтения нужно пережить хвост старых транзакций. Нужен явный барьер rollout: система deploy должна подтвердить, что все экземпляры приложения перешли на dual-write. `pg_stat_activity` не заменяет такой барьер — запрос может начаться до rollout, но открыть транзакцию позже, и `xact_start` будет новее cutoff.

> [!info]- Операционные детали transaction drain
> `$deploy_timestamp` фиксируется в момент подтверждения последнего экземпляра приложения:
>
> ```sql
> -- В отдельном соединении без явного BEGIN/COMMIT
> SELECT clock_timestamp();  -- wall-clock время, не now()
> ```
>
> `now()` возвращает время начала текущей транзакции. `clock_timestamp()` — реальное время вызова.
>
> `pg_stat_activity` — вспомогательная телеметрия для обнаружения забытых транзакций:
>
> ```sql
> SELECT count(*) FROM pg_stat_activity
> WHERE xact_start < $deploy_timestamp
>   AND xact_start IS NOT NULL
>   AND datname = current_database()
>   AND pid <> pg_backend_pid();
> ```

**Gate B — convergence.** После transaction drain сделать дополнительный проход по `WHERE region IS NULL` (tail-sweep) и проверить, что новый столбец стабильно заполнен. Если переключить чтение раньше, код увидит NULL в строках, которые основной backfill или поздние коммиты ещё не закрыли. Критерий зависит от типа миграции:

```sql
-- Добавление столбца: все строки заполнены
SELECT COUNT(*) FROM orders WHERE region IS NULL;  -- должен быть 0
```

Проверять **дважды** с интервалом >= максимальное время жизни транзакции (для web-приложений: 30-60 секунд). Если повторная проверка показывает новые NULL — хвост ещё не сошёлся: нужен ещё один дополнительный проход по `WHERE region IS NULL` + повторная проверка.

**Gate C — replica catch-up** (если приложение читает с [реплик](../postgresql/distribution/replication.md)). Без этого gate приложение переключит чтение на `region`, но replica ещё не применила backfill — запросы увидят NULL вместо данных. Захватить LSN (Log Sequence Number — позиция в WAL) на primary непосредственно перед переключением чтения:

```sql
-- На primary:
SELECT pg_current_wal_lsn();  -- $cutover_lsn

-- На каждой replica: ждать replay
SELECT pg_last_wal_replay_lsn() >= $cutover_lsn;  -- true = caught up
```

Ждать пока все serving replicas replay >= `$cutover_lsn`. Транзакции с [[databases/sql/modification/transactions#уровни-изоляции|REPEATABLE READ]] на replica сохраняют старый snapshot даже после catch-up (snapshot фиксируется на BEGIN). Для коротких web-запросов в READ COMMITTED это не проблема — каждый новый statement берёт свежий snapshot. Для long-lived analytics-транзакций (REPEATABLE READ) — завершить их на replica перед cutover или перенаправить analytics-запросы на primary. Если приложение читает только с primary — gate не нужен.

**5. Contract** — убрать старую структуру:

```sql
-- Через safe CHECK-паттерн (см. [[databases/migrations/safe-schema-changes#not-null|NOT NULL]])
ALTER TABLE orders ADD CONSTRAINT orders_region_nn CHECK (region IS NOT NULL) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT orders_region_nn;
ALTER TABLE orders ALTER COLUMN region SET NOT NULL;
ALTER TABLE orders DROP CONSTRAINT orders_region_nn;
```

**Gate:** все readers и writers используют `region`.

### Expand-contract для rename и type change

Тот же паттерн, другие детали:

**Rename** `orders.region` → `orders.shipping_region`:
1. ADD COLUMN shipping_region
2. Dual-write: код пишет в оба
3. Backfill: `UPDATE orders SET shipping_region = region WHERE shipping_region IS NULL`
4. Switch reads + convergence: `WHERE shipping_region IS DISTINCT FROM region` (NULL-safe сравнение — `<>` вернул бы NULL при NULL в любом столбце)
5. Deploy: код переключается на `shipping_region`-only (readers и writers)
6. DROP COLUMN region — только после того, как **все readers и writers** на `shipping_region`

**Type change** `orders.amount INTEGER` → `orders.amount BIGINT`:
Безопасная часть паттерна та же: добавить `amount_new BIGINT` → dual-write → backfill → switch reads и writers на `amount_new`. На этом шаге смена типа уже завершена. Дальше есть выбор:

- оставить новое имя `amount_new` и убрать старый столбец позже;
- если старое имя `amount` принципиально важно, считать финальный rename отдельным несовместимым cutover со своим deploy plan или maintenance window.

Иначе легко получить ложное ощущение «rename тоже прозрачен онлайн». Он не прозрачен: после `RENAME COLUMN amount_new TO amount` код, который ещё обращается к `amount_new`, сразу ломается. Перед DROP старого столбца нужно также перенести его зависимости: индексы, constraints, defaults, views.

Ключевое: без строгих gates между шагами — stale reads, потеря записей, failed validation.

## Backfilling

Backfill выполняется внутри expand-фазы, после deploy dual-write (шаг 3). Один UPDATE на 50M строк — ROW EXCLUSIVE, но: блокирует строки на время UPDATE, генерирует гигабайты [WAL](../postgresql/durability/wal.md) (Write-Ahead Log — журнал, в который PostgreSQL записывает изменения до их применения к данным), может вызвать replication lag и помешать [VACUUM](../postgresql/maintenance/vacuum.md) (фоновой очистке мёртвых версий строк).

**Правило: столбец для backfill добавляется nullable, без DEFAULT.** Если ADD COLUMN с DEFAULT (например, `DEFAULT 'unknown'`), все существующие строки сразу получают non-NULL значение → `WHERE region IS NULL` ничего не находит → backfill считает себя завершённым, хотя данные содержат placeholder, а не реальные значения.

### Batch по диапазонам

Для таблиц с числовым PK ([[databases/sql/schema/tables-and-types#конкурентная-вставка--serial-и-identity|BIGSERIAL, IDENTITY]]) — разбить на range windows:

```sql
UPDATE orders SET region = compute_region(shipping_address)
WHERE id BETWEEN 1 AND 10000 AND region IS NULL;
-- пауза (снижение нагрузки, WAL, replication lag)
UPDATE orders SET region = compute_region(shipping_address)
WHERE id BETWEEN 10001 AND 20000 AND region IS NULL;
```

`AND region IS NULL` — idempotent guard: при повторе батча (restart, ошибка) строки не обрабатываются дважды. Пауза между батчами ограничивает lock duration, WAL volume и replication lag.

На sparse PK (пробелы от удалений) часть батчей будет пустой — лишняя работа, не потеря данных. Для UUID ключей range windows не применимы — нужен другой подход.

### Cursor-based batch

Cursor с high-water mark работает для любого монотонного PK, включая sparse. `$last_id` — последний обработанный ключ (переменная приложения или checkpoint-таблица):

```sql
WITH batch AS (
  SELECT id FROM orders
  WHERE region IS NULL AND id > $last_id
  ORDER BY id LIMIT 10000
)
UPDATE orders SET region = compute_region(shipping_address)
FROM batch
WHERE orders.id = batch.id AND orders.region IS NULL;
-- $last_id = MAX(id) из batch; повторять пока batch не пуст
```

`orders.region IS NULL` в outer UPDATE — защита от race condition: если между SELECT и UPDATE другой процесс заполнил строку, она пропускается, а не перезаписывается.

Каждый батч = отдельная транзакция с explicit COMMIT. Не одна большая транзакция (удерживает snapshot, мешает VACUUM) и не без транзакций.

### Late-commit и tail-sweep

Sequence выделяет id до commit и не откатывает его. Транзакция может получить id = 5000, но не коммитить. Cursor-based batch проходит `id > 4000 LIMIT 10000` — строки с id = 5000 ещё нет (транзакция не закоммичена, строка невидима). Cursor двигает `$last_id` дальше. Транзакция коммитит позже — строка появляется с `region IS NULL`, но backfill уже ушёл вперёд. Строка останется незаполненной навсегда. Это **late-commit hazard**. Range windows подвержены той же проблеме: батч `WHERE id BETWEEN 4001 AND 14000` не увидит незакоммиченную строку с id = 5000.

Решение — **tail-sweep** после основного прохода. Финальный батчированный проход без cursor, по `WHERE region IS NULL`:

```sql
WITH batch AS (
  SELECT id FROM orders WHERE region IS NULL ORDER BY id LIMIT 10000
)
UPDATE orders SET region = compute_region(shipping_address)
FROM batch WHERE orders.id = batch.id AND orders.region IS NULL;
-- повторять пока batch не пуст
```

Tail-sweep обязателен для любого батчированного backfill — и range windows, и cursor-based.

### Background и lazy backfill

**Background job** — backfill выполняется асинхронно (отдельный процесс, job queue). Код приложения обрабатывает и NULL, и заполненные значения. Подходит для [миграций](migrations.md), которые могут длиться часы или дни.

**Lazy backfill** — значение вычисляется при следующем чтении или записи строки. Нет отдельного backfill-процесса, но код сложнее: каждый read/write path должен обрабатывать отсутствие значения.

## Обратимость

Некоторые операции необратимы:

- **DROP COLUMN** уничтожает данные — восстановить можно только из backup.
- **ALTER COLUMN TYPE** с потерей precision (NUMERIC → INTEGER) — обратное преобразование не восстанавливает исходные значения.
- **Data transformations** (merge столбцов, split таблицы) — обратная трансформация может быть неоднозначной.

**Forward-only vs reversible.** ADD COLUMN, CREATE INDEX — reversible на уровне DDL (DROP COLUMN, DROP INDEX откатывает). Но если в столбец уже записаны данные (dual-write, backfill), DROP COLUMN уничтожит их — на уровне rollout это уже forward-only. DROP COLUMN, type change с потерей precision, data transformations — forward-only в обоих смыслах.

Практика: для destructive операций — планировать recovery path до выполнения. Backup перед DROP COLUMN. Expand-contract для type change (старый столбец сохраняется до подтверждения корректности нового).

## Практические правила

1. **Schema и data — отдельно.** Одна [миграция](migrations.md) меняет структуру или данные, не то и другое.
2. **Backward compatibility.** Каждый шаг совместим с текущим и предыдущим кодом.
3. **Expand-contract** для любой несовместимой операции: добавить новое → dual-write → backfill → switch reads → убрать старое. Gates между шагами обязательны.
4. **Backfill: nullable, без DEFAULT; батчами; tail-sweep.** Каждый батч — отдельная транзакция. Idempotent predicate (`WHERE col IS NULL`).
5. **Планировать recovery.** Для irreversible операций — backup или expand-contract с сохранением старого до подтверждения.

## Sources

- Martin Fowler: Parallel Change. <https://martinfowler.com/bliki/ParallelChange.html>
- PostgreSQL Documentation (v17): Date/Time Functions and Operators. <https://www.postgresql.org/docs/17/functions-datetime.html>
- PostgreSQL Documentation (v17): pg_stat_activity. <https://www.postgresql.org/docs/17/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW>
- PostgreSQL Documentation (v17): System Administration Functions. <https://www.postgresql.org/docs/17/functions-admin.html>
- GoCardless: Zero-downtime Postgres migrations — the hard parts. <https://gocardless.com/blog/zero-downtime-postgres-migrations-the-hard-parts/>

---

← [Безопасные изменения схемы](safe-schema-changes.md)
