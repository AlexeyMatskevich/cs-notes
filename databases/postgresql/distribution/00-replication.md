# Репликация в PostgreSQL: physical vs logical

**Предпосылки:** [распределение данных](../../distribution.md), [WAL](../durability/00-wal.md), [ACID](../storage/00-acid.md).

Общие свойства репликации (lag, асинхронность/синхронность, failover и split brain) описаны в [распределении данных](../../distribution.md). В PostgreSQL важнее всего различать два режима репликации: physical и logical — они решают разные задачи и по-разному ведут себя при восстановлении и переключениях.

## Physical replication (streaming / WAL shipping)

Physical replication строится вокруг WAL: реплика получает поток WAL-записей и применяет их, воспроизводя те же изменения страниц данных. Это репликация всего кластера как «бинарного» состояния: таблицы, индексы и системные структуры получаются такими же, как на primary.

Обычно physical replication используют для:

- standby-узлов под высокую доступность;
- чтений с реплики (read-only), если допустим lag.

## Logical replication (publication / subscription)

Logical replication передаёт логические изменения строк (`INSERT/UPDATE/DELETE`) и применяет их к выбранным таблицам. Это удобно, когда нужна доставка данных «частями»: например, только несколько таблиц, или поток изменений в другой кластер.

Практический нюанс: DDL «сам по себе» не реплицируется, а некоторые эффекты требуют отдельного дизайна (например, работа с sequence, если значения являются частью контракта между системами).

## Синхронное подтверждение в PostgreSQL

PostgreSQL умеет ждать реплику при подтверждении транзакции (synchronous replication). Это уменьшает окно потери данных при отказе primary, но добавляет задержку записи и может снижать доступность, если синхронные реплики недоступны.

## Как понять, реплика это или primary

```sql
SELECT pg_is_in_recovery(); -- true на реплике, false на primary
```

## Sources

- PostgreSQL Documentation (пример: v16): High Availability, Replication, Warm Standby. <https://www.postgresql.org/docs/16/high-availability.html>, <https://www.postgresql.org/docs/16/warm-standby.html>
- PostgreSQL Documentation (пример: v16): Logical Replication. <https://www.postgresql.org/docs/16/logical-replication.html>
