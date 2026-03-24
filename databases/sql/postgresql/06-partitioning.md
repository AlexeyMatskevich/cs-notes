# Партиционирование в PostgreSQL

**Предпосылки:** [партиционирование](../schema/02-partitioning.md) (концепция, выбор ключа), [таблицы и типы](../schema/00-tables-and-types.md) (CREATE TABLE).

← [EXCLUSION](05-exclusion-constraints.md) | [Материализованные представления](07-materialized-views.md) →

В [партиционировании](../schema/02-partitioning.md) рассмотрена идея: логическая таблица из физических частей, DROP вместо DELETE. PostgreSQL реализует её через декларативный DDL — PARTITION BY.

## Декларативное партиционирование

```sql
CREATE TABLE events (
    id         BIGSERIAL,
    created_at TIMESTAMP NOT NULL,
    user_id    BIGINT NOT NULL,
    payload    JSONB NOT NULL
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_01 PARTITION OF events
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE events_2026_02 PARTITION OF events
FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

Для приложения таблица остаётся `events`: INSERT и SELECT пишутся как обычно. PostgreSQL сам выбирает нужную партицию при вставке и отфильтровывает лишние при чтении.

## Типы партиционирования

**RANGE** — по диапазону значений. Подходит для дат и последовательных данных. Самый частый тип.

**LIST** — по конкретным значениям:

```sql
CREATE TABLE orders (
    id     BIGINT,
    region TEXT NOT NULL,
    total  INTEGER
) PARTITION BY LIST (region);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('EU', 'UK');
```

**HASH** — по хешу значения. Равномерное распределение строк по партициям:

```sql
PARTITION BY HASH (user_id);
-- MODULUS (англ. «модуль») и REMAINDER (англ. «остаток») задают хеш-распределение
CREATE TABLE events_p0 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE events_p1 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 1);
```

## Partition pruning — отсечение ненужных партиций

PostgreSQL автоматически пропускает партиции, не содержащие нужных строк:

```sql
SELECT *
FROM events
WHERE created_at >= '2026-02-10'
  AND created_at <  '2026-02-11';
```

PostgreSQL читает только `events_2026_02`. При 12 месячных партициях запрос по одному месяцу читает 1/12 данных.

## Ограничения уникальности

PostgreSQL требует, чтобы уникальные ограничения на партиционированной таблице **включали ключ партиционирования**. `UNIQUE(id)` без `created_at` невозможен — уникальность проверяется только внутри одной партиции:

```sql
-- Ошибка: UNIQUE(id) невозможен
-- Допустимо:
ALTER TABLE events ADD PRIMARY KEY (id, created_at);
```

## Retention — мгновенное удаление

`DROP TABLE events_2025_11` вместо `DELETE FROM events WHERE created_at < '2025-12-01'`. DROP — мгновенная DDL-операция: нет сканирования строк, нет нагрузки на фоновые процессы очистки.

## Sub-partitioning

Таблица events партиционирована по `created_at` (помесячно). Появляется новое требование: «все события customer_id = 42 за год». Запрос `WHERE customer_id = 42 AND created_at >= '2025-01-01'` ограничивает pruning до 12 партиций, но внутри каждой — полный скан по customer_id.

`RANGE(created_at)` на первом уровне, `HASH(customer_id)` на втором. 12 месяцев × 8 хеш-партиций = 96 партиций. Retention работает (DROP целого месяца), запросы по customer_id сужаются до одной хеш-партиции внутри каждого месяца.

Цена: больше партиций — больше файлов, дольше планирование. При сотнях и тысячах партиций overhead планировщика становится ощутимым.

## ATTACH и DETACH PARTITION

### ATTACH PARTITION — присоединение

```sql
ALTER TABLE events ATTACH PARTITION events_2026_03
FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

`ATTACH PARTITION` берёт `SHARE UPDATE EXCLUSIVE` на родительскую таблицу и `ACCESS EXCLUSIVE` на дочернюю. Если в дочерней таблице данные не проверены, PostgreSQL сканирует её, чтобы убедиться, что все строки удовлетворяют constraint партиции — на большой таблице это долгая блокировка.

Решение: сначала добавить CHECK constraint на дочернюю таблицу, потом ATTACH. PostgreSQL пропускает проверку, если CHECK уже гарантирует соответствие:

```sql
ALTER TABLE events_2026_03
ADD CONSTRAINT check_range CHECK (
    created_at >= '2026-03-01' AND created_at < '2026-04-01'
);

-- Теперь ATTACH мгновенный -- проверка пропущена
ALTER TABLE events ATTACH PARTITION events_2026_03
FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

### DETACH PARTITION — отсоединение

```sql
ALTER TABLE events DETACH PARTITION events_2025_11;
DROP TABLE events_2025_11;
```

`DETACH PARTITION CONCURRENTLY` (PostgreSQL 14+) — неблокирующий detach. Не берёт `ACCESS EXCLUSIVE` на родительскую таблицу, но нельзя использовать внутри транзакции.

## Sources

- PostgreSQL Documentation (v16): Partitioning. <https://www.postgresql.org/docs/16/ddl-partitioning.html>

---

← [EXCLUSION](05-exclusion-constraints.md) | [Материализованные представления](07-materialized-views.md) →
