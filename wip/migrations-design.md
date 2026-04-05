---
phase: design
status: approved
topic: Database Migrations
files:
  - databases/migrations/index.md
  - databases/migrations/00-safe-schema-changes.md
  - databases/migrations/01-schema-evolution.md
---

# Design: Database Migrations

## Черновик объяснения

**Объяснение.** Читатель знает DDL-команды и lock-механику. Но он работал с пустыми таблицами — ADD COLUMN мгновенный, CREATE INDEX тривиальный. Миграции — это те же команды, но в контексте, где всё меняется: таблица содержит 50M строк, в неё пишут 400 раз в секунду, параллельно работает старый код. Тот же ALTER TABLE, который в dev-среде занял миллисекунды, в production может заблокировать все запросы на минуты. Миграции — дисциплина безопасного изменения схемы в этих условиях.

**Главная сложность.** Читатель переоценивает свою защищённость. Он знает lock_timeout и CONCURRENTLY, и думает: «значит всё ок». Но lock_timeout не помогает с операциями, которые держат блокировку (table rewrite). CONCURRENTLY не работает для ALTER TABLE. А главное — ни lock_timeout, ни CONCURRENTLY не решают проблему координации кода и схемы при rolling deploy. Сложность в **синтезе**: нужно соединить знания из DDL, блокировок и транзакций в одну согласованную практику.

**Момент понимания.** Когда читатель видит, что одна и та же команда (ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT ...) ведёт себя радикально по-разному в зависимости от: версии PG (10 vs 11+), типа default-выражения (volatile vs non-volatile), размера таблицы, текущего трафика, и версии работающего кода. DDL-знание говорит «что написать», а миграционная дисциплина говорит «безопасно ли это написать прямо сейчас и что будет с приложением».

## Перспектива читателя

**Наивная модель:** «Миграция — это набор DDL-команд, выполняемых по порядку на живой базе. Если знаешь lock_timeout и CONCURRENTLY — основная опасность снята.»

**Ожидания читателя:**
- Хочет узнать про тулинг (migration files, up/down, runner) — OUT OF SCOPE, но нужно явно обозначить рамку
- Центральный вопрос: «как координировать изменение схемы с изменением кода?» — это файл 01
- Думает, что DDL в транзакции = атомарно — нужно показать ограничения (CONCURRENTLY не работает в транзакции)

**Расхождения с черновиком:**
- Читатель фокусируется на tooling/versioning — мы фокусируемся на SQL-механике и паттернах
- Читатель думает «lock_timeout спасает» — мы ломаем эту модель в файле 00
- Читатель не подозревает о проблеме code compatibility — мы раскрываем в файле 01

**Вопросы читателя, которые нужно адресовать:**
1. «Как отслеживать, какие миграции применены?» → intro: «это задача фреймворка, здесь — SQL-механика под любым фреймворком»
2. «Как откатывать?» → файл 01, reversibility
3. «Как не положить production?» → файл 00, cost profile + safe patterns + timeouts
4. «Как координировать код и схему?» → файл 01, expand-contract

## Грубый эскиз

- **Домен:** `databases/migrations/`
- **Слой:** прикладной (опирается на DDL + concurrency, фокус — практика)
- **Scope:** серия из 2 файлов + index.md
- **Пол:** DDL-синтаксис, lock-механика, транзакции — не переобъясняем
- **Потолок:** безопасные схемные изменения и координация с кодом. Не учим: конкретные фреймворки (AR, Flyway, Alembic), CI/CD, blue-green deployments

## Педагогический дизайн

### Граница знаний

**Знает (из предпосылок):**
- ALTER TABLE: ADD COLUMN, DROP COLUMN, ALTER COLUMN, RENAME (syntax)
- ADD COLUMN с DEFAULT в PG11+ мгновенно (упоминание в tables-and-types)
- ALTER COLUMN TYPE может требовать перезаписи всей таблицы (упоминание)
- Constraints: NOT NULL, FK, CHECK, DEFERRABLE, CASCADE (семантика)
- «Ограничения стоят I/O и создают ожидания блокировок» (общее понимание)
- CREATE INDEX: types, composite, partial, expression (syntax + когда помогает)
- CREATE INDEX CONCURRENTLY: SHARE UPDATE EXCLUSIVE, два прохода, не в транзакции, INVALID при сбое
- «В production всегда CONCURRENTLY» (правило)
- Table-level locks: ACCESS SHARE (SELECT), ROW EXCLUSIVE (DML), SHARE (INDEX), ACCESS EXCLUSIVE (DDL)
- Очередь блокировок: ALTER TABLE ждёт → все SELECT встают за ним
- lock_timeout для DDL (SET lock_timeout = '5s')
- Advisory locks: pg_advisory_lock, session vs transaction scope
- Транзакции: BEGIN, COMMIT, ROLLBACK, SAVEPOINT, isolation levels

**Не знает:**
- Полный cost profile: какие ALTER TABLE операции мгновенные (metadata) vs медленные (rewrite/scan)
- NOT VALID / VALIDATE CONSTRAINT паттерн для CHECK и FK
- Безопасный NOT NULL через CHECK NOT VALID → VALIDATE → SET NOT NULL (PG12+)
- PG11 fast default детали: volatile vs non-volatile default expression
- statement_timeout в контексте миграций (в отличие от lock_timeout)
- Retry strategy для DDL с lock_timeout
- Schema vs data migration separation (почему нельзя мешать)
- Backfilling strategies (batched, background, lazy)
- Backward compatibility constraint (старый код + новая схема)
- Deploy-migrate ordering (migrate-first vs deploy-first)
- Expand-contract pattern
- Forward-only vs reversible migrations
- Migration versioning concepts (up/down) — out of scope, но нужно обозначить

**Граница:** читатель знает отдельные операции и lock-механику. Не знает, как соединить это в безопасную, координированную практику.

### Мотивация

Источник: **ломающаяся наивная модель**. Читатель думает: «знаю ALTER TABLE + знаю lock_timeout = готов к production». Модель ломается на первом же реальном кейсе: ALTER TABLE ... ADD COLUMN region TEXT NOT NULL DEFAULT 'unknown' на 50M строк. В dev — мгновенно. В production — зависит от версии PG, типа default, размера таблицы, трафика, и работающего кода. DDL-знание не отвечает на вопрос «безопасно ли ЭТО запускать СЕЙЧАС».

### Точка входа

**File 00:** Ты знаешь ALTER TABLE — можешь добавить столбец, создать индекс, навесить ограничение. На пустой таблице в dev-среде всё работает мгновенно. Но таблица orders — 50 миллионов строк, 400 записей в секунду. Приложение обслуживает пользователей, остановить его нельзя. Тот же ALTER TABLE, который в dev занял миллисекунды, в production может заблокировать все запросы на минуты.

**File 01:** Ты можешь безопасно добавить столбец, создать индекс, навесить ограничение — по одному. Но нужно: добавить столбец `region`, заполнить его данными для 50 миллионов строк, поставить NOT NULL. Три шага. Между первым и третьим — старый код, который не знает про `region` и вставляет строки без него. К третьему шагу в столбце появляются новые NULL.

### Сценарий

Тип: **сценарий ограничения** — DDL (известное решение) перестаёт работать в новом контексте (live production database с данными и трафиком).

Сквозной сценарий: эволюция таблицы `orders` в работающей e-commerce системе. 50M строк, 400 writes/sec, rolling deploy, PostgreSQL.

### Дуга

**File 00: Безопасные операции**

Нить: цепочка компромиссов.

1. **DDL ≠ instant.** ALTER TABLE в dev = мгновенно. ALTER TABLE в production на 50M строк = зависит. Одна и та же команда — разное поведение.
   → Нужно: знать стоимость каждой операции

2. **Cost profile.** Таблица операций: что берёт какой lock, что делает (metadata / rewrite / scan), какова длительность. ACCESS EXCLUSIVE на микросекунды (metadata) ≠ ACCESS EXCLUSIVE на минуты (rewrite). Длительность важнее уровня блокировки.
   → Одни операции безопасны, другие опасны. Но опасные нужны.
   → Нужно: safe alternatives для опасных операций

3. **Safe patterns per operation type.**
   - CHECK constraints: NOT VALID → VALIDATE (NOT VALID убирает scan, но CHECK NOT VALID всё равно берёт ACCESS EXCLUSIVE — операция мгновенная, lock на микросекунды)
   - FK constraints: NOT VALID → VALIDATE (FK NOT VALID берёт SHARE ROW EXCLUSIVE — слабее, чем CHECK)
   - NOT NULL: CHECK NOT VALID → VALIDATE → SET NOT NULL (PG12+)
   - UNIQUE / PRIMARY KEY: CREATE UNIQUE INDEX CONCURRENTLY → ADD CONSTRAINT ... USING INDEX (обходит блокирующий ADD UNIQUE)
   - Defaults: PG11+ fast default, volatile vs non-volatile
   - Index: CONCURRENTLY (углубление контекста: уже знает, но теперь в миграционной картине)
   → Даже «безопасные» операции берут ACCESS EXCLUSIVE на микросекунды
   → Нужно: protection from lock queue even for fast operations

4. **Timeout discipline.** lock_timeout (уже знает — но теперь конкретный паттерн с retry). statement_timeout (новое: оставлять конечным по умолчанию, поднимать точечно для CONCURRENTLY/VALIDATE). Два антипаттерна: (1) blanket `statement_timeout = '0'` убирает защиту после получения блокировки; (2) SET без ensure/finally — при сбое CONCURRENTLY session остаётся с расширенным timeout, следующие шаги теряют защиту. Безопасный путь: отдельное соединение для долгих операций или guarantee сброса.
   → Читатель может классифицировать любую DDL-операцию в один из трёх тиров (с PG-версией и fallback):
     · **Safe pattern exists (online):**
       - NOT VALID → VALIDATE для CHECK и FK (PG9.4+ для non-blocking VALIDATE; CHECK NOT VALID = ACCESS EXCLUSIVE мгновенно; fallback на PG<9.4: VALIDATE берёт ACCESS EXCLUSIVE)
       - CONCURRENTLY для индексов (появился в PG8.2, стабильное non-blocking поведение с PG9.2+; fallback: maintenance window)
       - USING INDEX для UNIQUE (не-partitioned; PG9.2+; **conditionally safe**: online только если uniqueness уже enforced или writes quiesced на время build; при первичном создании uniqueness — writes могут создать дубликаты → INVALID index; fallback: low-traffic window + retry)
       - USING INDEX для PRIMARY KEY (не-partitioned; PG9.2+; **conditionally safe** + **hard precondition: столбец уже NOT NULL** — если nullable, PG выполнит implicit SET NOT NULL с full table scan под ACCESS EXCLUSIVE (блокирующий!); если столбец nullable — сначала safe NOT NULL через CHECK-паттерн, потом USING INDEX)
       - Fast default (PG11+; fallback: add без default → backfill → set default)
       - Safe NOT NULL через CHECK (PG12+; fallback на PG<12: add column nullable → backfill → downtime SET NOT NULL)
     · **Metadata-only, queue-sensitive** — ADD COLUMN без default (мгновенно, но ACCESS EXCLUSIVE → lock queue; нужен lock_timeout + retry)
     · **DDL-fast, но app-unsafe** — DROP COLUMN, RENAME (ACCESS EXCLUSIVE на микросекунды, но ломают running code при rolling deploy; требуют expand-contract или координированного deploy, даже если DDL мгновенный)
     · **Requires expand-contract или downtime** — ALTER TYPE (кроме binary-coercible исключений), любая операция без safe alternative на данной версии PG

**Мост:** «Ты теперь знаешь, какие операции безопасны online, какие мгновенны но опасны из-за очереди, а какие требуют другого подхода. Но реальная миграция — это три шага. Между первым и третьим старый код вставляет данные по старой схеме. Проблема не в отдельных операциях — а во взаимодействии схемы, данных и работающего кода.»

**File 01: Эволюция схемы**

Нить: цепочка компромиссов.

5. **Schema vs data.** Добавить столбец — schema change. Заполнить его — data migration. В одном шаге = блокировки дольше, WAL больше, риск выше. Разделение — базовый принцип.
   → Нужно: координация с приложением (ПРЕЖДЕ чем заполнять данные)

6. **Code compatibility.** Между миграцией и deploy — окно, когда одна версия кода работает с обеими схемами. Backward compatibility constraint. Migrate-first vs deploy-first. Примеры: нельзя добавить NOT NULL без DEFAULT (старый код не пишет в новый столбец), нельзя удалить столбец, который старый код читает.
   → Нужно: паттерн для orchestration (expand → backfill → contract)

7. **Expand-contract.** Пять шагов со строгими gates:
   1. **Expand schema** — добавить новую структуру (ADD COLUMN, etc.)
   2. **Deploy dual-write** — rolling deploy кода, который пишет в оба столбца. **Gate: ВСЕ instances обновлены** (ни один writer не пишет только в старый столбец)
   3. **Backfill** — заполнить старые строки. **Gate: начинать только после п.2** + post-rollout tail-sweep для late-commit строк
   4. **Switch reads** — переключить чтение на новый столбец. **Три gate-а:** (A) transaction drain — все pre-rollout транзакции завершены (application barrier или scoped `pg_stat_activity.xact_start`); (B) convergence verified stable — проверяется дважды, критерий по типу миграции; (C, advanced) replica catch-up — если читают с replicas (требует знание [репликации](../postgresql/distribution/00-replication.md)): capture `pg_current_wal_lsn()` непосредственно перед switch reads, ждать все serving replicas >= этот LSN. Primary-only reads — gate не нужен
   5. **Contract** — удалить старую структуру. **Gate: все readers и writers на новом столбце**

   Ключевое: без строгих gates между шагами — stale reads, потеря записей, failed validation. Примеры: переименование столбца, смена типа, разделение таблицы. Универсальный паттерн.
   → Gates определяют КОГДА можно делать backfill. Теперь — как.

8. **Backfilling.** Один UPDATE на 50M строк = locks, WAL explosion, replication lag. Альтернативы: batched (N строк за раз), background job (асинхронно), lazy (при следующем чтении/записи). Trade-offs каждого. Backfill выполняется ВНУТРИ expand-фазы, после установки dual-write — иначе новые строки расходятся.
   → Структуру, данные и код можно менять безопасно.
   → Но не всё можно откатить

9. **Reversibility.** DROP COLUMN уничтожает данные. ALTER TYPE может потерять precision. Data transformations необратимы. Forward-only vs reversible. Планирование recovery path. Какие операции обратимы, какие нет.

### Карта деталей

| Деталь | Шаг дуги |
|--------|----------|
| Таблица операций (lock / действие / длительность) | 2 — cost profile |
| NOT VALID / VALIDATE для CHECK (ACCESS EXCLUSIVE, но мгновенно) и FK (SHARE ROW EXCLUSIVE) | 3 — safe patterns |
| CHECK NOT VALID → VALIDATE → SET NOT NULL (PG12+) | 3 — safe patterns |
| pg_attribute.attmissingval (cross-ref) | 3 — safe patterns (PG11 fast default) |
| Volatile vs non-volatile default expression | 3 — safe patterns |
| Operationally safe ≠ semantically correct (fast default + audit columns) | 3 — safe patterns |
| SET lock_timeout + конечный statement_timeout (поднимать точечно) | 4 — timeout discipline |
| Антипаттерн: blanket statement_timeout = 0 | 4 — timeout discipline |
| Retry strategy для DDL | 4 — timeout discipline |
| Schema migration vs data migration | 5 — separation |
| Backward compatibility constraint | 6 — code compatibility |
| Migrate-first vs deploy-first | 6 — code compatibility |
| Expand phase (add new alongside old + dual-write) | 7 — expand-contract |
| Migrate phase (backfill + verify convergence + switch reads) | 7 — expand-contract |
| Contract phase (remove old, только после обновления ВСЕХ писателей) | 7 — expand-contract |
| Dual-write: почему без него stale reads / lost writes | 7 — expand-contract |
| Batched UPDATE (PK-range windows + idempotent predicate + пауза) | 8 — backfilling |
| Background job pattern | 8 — backfilling |
| Lazy backfill | 8 — backfilling |
| WAL generation при массовом UPDATE | 8 — backfilling |
| CREATE UNIQUE INDEX CONCURRENTLY + ADD CONSTRAINT USING INDEX | 3 — safe patterns |
| Rename column через expand-contract (пример) | 8 — expand-contract |
| Change type через expand-contract (пример) | 8 — expand-contract |
| Forward-only vs reversible | 9 — reversibility |
| Необратимые операции (DROP COLUMN, type change, data transform) | 9 — reversibility |

### Связи

**Предпосылки серии:**
- `databases/sql/schema/00-tables-and-types.md` — ALTER TABLE syntax, DEFAULT
- `databases/sql/schema/01-constraints.md` — NOT NULL, FK, CHECK
- `databases/sql/schema/04-indexes.md` — CREATE INDEX, типы
- `databases/sql/modification/01-transactions.md` — BEGIN/COMMIT/ROLLBACK
- `databases/sql/postgresql/04-index-operations.md` — CONCURRENTLY, INVALID
- `databases/postgresql/concurrency/03-locks.md` — lock levels, lock queue, lock_timeout

**Зависимости внутри серии:**
- 00 ← все предпосылки серии
- 01 ← 00

**Cross-references на PG internals (не предпосылки, а углубление):**
- `databases/postgresql/storage/01-pages-and-tuples.md` — почему table rewrite дорогой
- `databases/postgresql/concurrency/03-locks.md` — матрица совместимости блокировок (углубление)

## Валидация

1. Граница знаний — **PASS**: чётко разделено знает/не знает, привязано к конкретным файлам
2. Мотивация — **PASS**: ломающаяся наивная модель («lock_timeout + CONCURRENTLY = готов»)
3. Точка входа — **PASS**: начинаем с ALTER TABLE (знакомое) → ломаем модель на 50M строк
4. Дуга — **PASS**: причинная цепочка без декоративных звеньев, каждый шаг порождает следующий
5. Структура — **PASS**: разрыв на «одиночные операции» → «workflow» — естественная точка ветвления
6. Интеграция — **APPROVED** автором

## Файловая структура из дуги

```
databases/migrations/
├── index.md                      рамка, study order, scope
├── 00-safe-schema-changes.md     одиночные операции: cost profile, safe patterns, timeouts
└── 01-schema-evolution.md        multi-step: separation, backfill, compatibility, expand-contract
```

## Дизайн файлов

### index.md

Рамка серии:
- **Что это:** дисциплина безопасного изменения схемы на рабочей базе с данными и трафиком.
- **Универсальное vs PG-specific:** концепции (expand-contract, schema vs data, deploy ordering, reversibility) универсальны для любой RDBMS. Операционные паттерны (lock levels, NOT VALID, CONCURRENTLY, fast defaults) специфичны для PostgreSQL и привязаны к версиям. PG-специфика явно маркируется в тексте (версия, команда) — читатель не должен принять PG-рецепт за generic SQL.
- **Что не покрыто:** конкретные фреймворки (AR, Flyway, Alembic) — этот материал является SQL-фундаментом для любого фреймворка.
- **Execution environment contract:** паттерны из этой серии предполагают: (1) прямое подключение к PostgreSQL (не через PgBouncer в transaction mode — advisory locks и session-level SET не работают через transaction pooling); (2) CONCURRENTLY выполняется вне транзакции (runner не должен оборачивать в BEGIN/COMMIT); batched backfill выполняется как серия коротких транзакций (один батч = одна транзакция с explicit COMMIT), а не как одна большая транзакция и не без транзакций вовсе; (3) ответственность за сброс session-level настроек (statement_timeout) лежит на вызывающем коде (ensure/finally или отдельное соединение). Эта секция — не тулинг-гайд, а контракт: если среда исполнения не удовлетворяет этим условиям, safe patterns не гарантируют безопасность.
- **Version floor:** mainline рецепты предполагают PostgreSQL 12+ (safe NOT NULL через CHECK, non-blocking VALIDATE, fast defaults PG11+). Для PG < 12 — compact fallback matrix в index.md (какие паттерны недоступны, что использовать вместо).
- **Study order:** 00 → 01.
- **Как всё связано:** trade-off безопасность/скорость, trade-off простота/координация.

### 00-safe-schema-changes.md

**Предпосылки:** все предпосылки серии (через ссылки).
**Мотивация:** ALTER TABLE на пустой таблице vs 50M строк — тот же SQL, разный результат.
**Точка входа:** dev vs production, знакомый ALTER TABLE.
**Под-дуга:** DDL ≠ instant → cost profile → safe patterns → timeout discipline.
**Эффект для читателя:** может классифицировать любую DDL-операцию по тиру безопасности и выбрать правильный подход: safe pattern, lock_timeout + retry, или expand-contract.
**Execution contract (повторяется из index, т.к. файл доступен через deep-link):** прямое подключение к PG (не transaction-pooled PgBouncer), DDL вне транзакции для CONCURRENTLY, ответственность за сброс session-level SET.
**Секции (ориентировочно):**
- Execution environment (контракт среды: прямое подключение, non-transactional DDL, session state cleanup)
- Вход: ALTER TABLE на 50M строк (мотивация)
- Стоимость операций (таблица: lock / действие / длительность; CHECK/NOT NULL/UNIQUE отдельно от FK)
- Безопасное добавление constraints (NOT VALID → VALIDATE; CHECK vs FK lock levels)
- Безопасный NOT NULL (CHECK workaround, PG12+)
- Безопасный UNIQUE / PRIMARY KEY (CONCURRENTLY + USING INDEX)
- Default-значения (PG11+ fast default, volatile/non-volatile)
- Timeout discipline (lock_timeout + statement_timeout + retry)
- Операционный checklist (минимальная диагностика: pg_locks для блокирующих транзакций, pg_index.indisvalid для INVALID-индексов, pg_stat_replication для replication lag при backfill, pg_stat_activity для idle-in-transaction)
- Практические правила (summary)

### 01-schema-evolution.md

**Предпосылки:** `00-safe-schema-changes.md`.
**Мотивация:** одну операцию выполнишь безопасно — но миграция это 3 шага, и между ними работает старый код.
**Точка входа:** сценарий с добавлением region + backfill + NOT NULL.
**Под-дуга:** schema vs data → code compatibility → expand-contract → backfilling (внутри expand) → reversibility.
**Эффект для читателя:** может спланировать и безопасно выполнить многошаговую эволюцию схемы на рабочей системе.
**Секции (ориентировочно):**
- Вход: три шага миграции, старый код между ними (мотивация)
- Schema vs data миграции (разделение)
- Совместимость кода и схемы (backward compatibility, deploy ordering)
- Expand-contract (три фазы с dual-write, cutover criteria, примеры: rename, change type)
- Backfilling (batched, background, lazy — внутри expand-фазы, после dual-write)
- Обратимость (forward-only vs reversible, необратимые операции)
- Практические правила (summary)

## Integration plan

| Файл | Что менять |
|------|-----------|
| `databases/sql/index.md` | Добавить `databases/migrations/` в study order после schema/ И после postgresql/ (серия требует `04-index-operations.md` и `03-locks.md` как prerequisites — навигация должна направлять читателя через PG-файлы до миграций) |
| `databases/sql/schema/00-tables-and-types.md` | Cross-link в секции ALTER TABLE на миграции. ALTER TYPE exceptions — PG-specific, идут в sql/postgresql/. |
| `databases/sql/schema/01-constraints.md` | Cross-link на миграции: «добавление constraints на существующие таблицы». Без нового контента — NOT VALID и VALIDATE живут в PG-слое. |
| `databases/sql/postgresql/04-index-operations.md` (расширение) | **Добавить:** USING INDEX для constraints (привязка constraint к существующему индексу). Логически связано с existing CONCURRENTLY content. |
| `databases/sql/postgresql/index.md` | Обновить описание `04-index-operations.md` если контент расширен. Если вместо расширения добавляется новый файл — добавить его в study order. |
| `databases/sql/schema/04-indexes.md` | Cross-link: «создание индексов на production → [миграции](../../migrations/00-safe-schema-changes.md)» (дополнение к существующей ссылке на index-operations) |
| `databases/sql/postgresql/04-index-operations.md` | **Fix:** заменить `DROP INDEX idx_name` на `DROP INDEX CONCURRENTLY idx_name` в секции INVALID-index recovery (plain DROP = ACCESS EXCLUSIVE, blocking на live table). Cross-link: CONCURRENTLY в контексте миграционного workflow → `../../migrations/01-schema-evolution.md` |
| `databases/postgresql/concurrency/03-locks.md` | Cross-link в секции table-level locks: «DDL-блокировки на практике → [миграции](../../migrations/00-safe-schema-changes.md)» |
| `CLAUDE.md` | Обновить file map: добавить `databases/migrations/` |

**Принцип распределения:**
- DDL-фичи используемые в миграциях (NOT VALID, VALIDATE, USING INDEX, ALTER TYPE exceptions, fast default) → `databases/sql/postgresql/` (всё PG-specific на практике, даже если NOT VALID формально в SQL:2011 — портируемость ненадёжна)
- Migrations ссылается на оба уровня и учит workflow: когда, в каком порядке, в сочетании с чем. Не дублирует DDL-определения.
