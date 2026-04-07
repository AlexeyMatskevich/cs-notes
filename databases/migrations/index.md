# Миграции

<details>
<summary>Предпосылки</summary>

Полный список предпосылок — в каждой заметке серии. Для входа в серию достаточно: [таблицы и типы](../sql/schema/00-tables-and-types.md) (ALTER TABLE, DEFAULT), [ограничения](../sql/schema/01-constraints.md) (NOT NULL, FK, CHECK), [индексы](../sql/schema/04-indexes.md) (CREATE INDEX), [транзакции](../sql/modification/01-transactions.md) (BEGIN/COMMIT/ROLLBACK), [блокировки](../postgresql/concurrency/03-locks.md) (уровни блокировок, очередь, lock_timeout).

</details>

Добавить столбец, создать индекс, навесить ограничение — на пустой таблице в dev-среде всё мгновенно. Но таблица `orders` — 50 миллионов строк, 400 записей в секунду. Приложение обслуживает пользователей, остановить его нельзя. Тот же ALTER TABLE, который в dev занял миллисекунды, в production может заблокировать все запросы.

Миграции — дисциплина безопасного изменения схемы на рабочей базе данных: с данными, трафиком и несколькими версиями кода одновременно. DDL (Data Definition Language — ALTER TABLE, CREATE INDEX, DROP TABLE) описывает *что* менять. Миграции — *как* менять безопасно, не блокируя DML (Data Manipulation Language — INSERT, UPDATE, DELETE). Результат серии: читатель может спланировать любую миграцию — от добавления столбца до смены типа — без остановки приложения.

Концепции (expand-contract, разделение schema/data, совместимость кода и схемы, обратимость) универсальны для любой RDBMS. Операционные паттерны (уровни блокировок per DDL, NOT VALID/VALIDATE, CONCURRENTLY, fast defaults) специфичны для PostgreSQL и привязаны к версиям — PG-специфика маркирована в тексте версией и командой.

Конкретные фреймворки миграций (ActiveRecord, Flyway, Alembic) за пределами серии. Этот материал — SQL-фундамент, на котором строится работа с любым из них.

## Порядок изучения

- [Безопасные изменения схемы](00-safe-schema-changes.md) — стоимость DDL-операций, безопасные паттерны, timeout discipline
- [Эволюция схемы](01-schema-evolution.md) — schema vs data, совместимость кода, expand-contract, backfilling, обратимость

## Среда выполнения

Безопасные паттерны из серии работают при определённых условиях. Если среда им не соответствует, паттерны не гарантируют безопасность.

1. **Прямое подключение к PostgreSQL**, не через PgBouncer в transaction mode. PgBouncer — connection pooler (промежуточный слой между приложением и PostgreSQL, переиспользующий соединения). В transaction mode он переназначает серверное соединение между транзакциями. Session-level `SET` (lock_timeout, statement_timeout) и [advisory locks](../postgresql/concurrency/03-locks.md#advisory-locks--когда-row-level-locks-недостаточно) привязаны к серверному соединению; после переназначения настройки и блокировки теряются.

2. **DDL вне транзакции.** [CREATE INDEX CONCURRENTLY](../sql/postgresql/04-index-operations.md#create-index-concurrently) и REINDEX CONCURRENTLY не работают внутри BEGIN/COMMIT. Migration runner не должен оборачивать такие операции в транзакцию.

3. **Ответственность за session state.** После `SET statement_timeout = '30min'` для долгой операции значение нужно вернуть обратно. Если операция упадёт до сброса, сессия останется с расширенным timeout. Безопасные варианты: ensure/finally в коде или отдельное соединение, которое закрывается после операции.

4. **Batched backfill — серия коротких транзакций.** Один батч = одна транзакция с explicit COMMIT. Не одна большая транзакция (держит блокировки и мешает [VACUUM](../postgresql/maintenance/00-vacuum.md)) и не без транзакций.

## Версии PostgreSQL

Основные рецепты рассчитаны на PostgreSQL 12+:

| Паттерн | Версия | Fallback |
|---------|--------|----------|
| Fast default (значение вычисляется один раз) | PG 11+ | ADD COLUMN без default → backfill → SET DEFAULT |
| Safe NOT NULL через CHECK | PG 12+ | Downtime: SET NOT NULL под ACCESS EXCLUSIVE |
| Non-blocking VALIDATE | PG 9.4+ | VALIDATE под ACCESS EXCLUSIVE |
| CREATE INDEX CONCURRENTLY | PG 8.2+ | Maintenance window |
| DROP INDEX CONCURRENTLY | PG 9.2+ | DROP INDEX (ACCESS EXCLUSIVE) |
| REINDEX CONCURRENTLY | PG 12+ | CREATE INDEX CONCURRENTLY + DROP старый |

## Как всё связано

**Безопасность vs скорость.** Безопасные паттерны (NOT VALID → VALIDATE, CONCURRENTLY, batched backfill) работают дольше прямых DDL-команд. Цена — время и сложность. Выигрыш — приложение продолжает работать.

**Одиночная операция vs workflow.** Добавить столбец — одна команда, может быть безопасна сама по себе. Но реальная миграция — несколько шагов: добавить столбец, заполнить данными, поставить ограничение. Между шагами работает старый код, который не знает о новом столбце. Чем больше шагов, тем важнее координация схемы, данных и приложения.

## См. также

- [PostgreSQL: внутреннее устройство](../postgresql/index.md) — storage, concurrency, lock manager (механизмы, на которых строятся миграционные паттерны)
- [ACID](../acid.md) — транзакционный контракт

## Sources

- PostgreSQL Documentation (v17): ALTER TABLE. <https://www.postgresql.org/docs/17/sql-altertable.html>
- PostgreSQL Documentation (v17): CREATE INDEX. <https://www.postgresql.org/docs/17/sql-createindex.html>
- PostgreSQL Documentation (v17): Explicit Locking. <https://www.postgresql.org/docs/17/explicit-locking.html>
- Martin Fowler: Parallel Change. <https://martinfowler.com/bliki/ParallelChange.html>
