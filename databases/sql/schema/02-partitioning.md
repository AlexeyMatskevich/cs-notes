# Партиционирование

**Предпосылки:** [таблицы и типы](00-tables-and-types.md) (CREATE TABLE), [ограничения](01-constraints.md) (PRIMARY KEY, UNIQUE).

Сервис аналитики записывает события: клики, просмотры, покупки. За год накопилось 500 млн строк — 120 ГБ данных. Запросы по дате работают через индекс, но VACUUM на 120 ГБ занимает минуты, а удаление данных старше 90 дней через DELETE создаёт миллионы dead tuples и bloat.

Партиционирование решает эту проблему: вместо одной огромной таблицы — набор отдельных таблиц (партиций), разделённых по значению ключа. Удаление старых данных — `DROP TABLE events_2025_11`, мгновенная операция.

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
CREATE TABLE events_p0 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE events_p1 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 1);
```

## Partition pruning

Partition pruning (англ. «отсечение партиций») — отбрасывание партиций, заведомо не содержащих нужных строк:

```sql
SELECT *
FROM events
WHERE created_at >= '2026-02-10'
  AND created_at <  '2026-02-11';
```

PostgreSQL читает только `events_2026_02`. При 12 месячных партициях — 1/12 данных вместо всех.

Pruning бывает двух видов. **Plan-time pruning** работает, когда границы известны из текста запроса (литералы). **Runtime pruning** — когда условие зависит от параметра (`$1`). Оба отсеивают партиции, но plan-time делает это раньше и точнее.

## Ограничения уникальности

PostgreSQL требует, чтобы уникальные ограничения на партиционированной таблице **включали ключ партиционирования**. `UNIQUE(id)` без `created_at` невозможен — уникальность проверяется только внутри одной партиции:

```sql
-- Ошибка: UNIQUE(id) невозможен
-- Допустимо:
ALTER TABLE events ADD PRIMARY KEY (id, created_at);
```

## Retention — мгновенное удаление старых данных

Главный операционный выигрыш: `DROP TABLE events_2025_11` вместо `DELETE FROM events WHERE created_at < '2025-12-01'`. DROP — мгновенная DDL-операция без dead tuples.

## Цена партиционирования

PostgreSQL **не создаёт** будущие партиции автоматически. Если `events_2026_03` не существует к 1 марта — INSERT упадёт с ошибкой.

Запросы **без фильтра по ключу** партиционирования сканируют все партиции. `SELECT * FROM events WHERE user_id = 42` без ограничения по `created_at` — 36 отдельных сканов вместо одного.

Инженерная дисциплина: почти каждый запрос к партиционированной таблице должен явно ограничивать диапазон ключа партиционирования.

Подробнее о внутренней механике pruning и типовых ошибках — в заметках по [планировщику запросов](../../postgresql/query-processing/00-planner.md).

## Выбор ключа партиционирования

Таблица events партиционирована по `created_at` (помесячно). Аналитика по датам — pruning отсекает ненужные месяцы. Появляется новое требование: «все события customer_id = 42 за год». Запрос `WHERE customer_id = 42 AND created_at >= '2025-01-01'` ограничивает pruning до 12 партиций, но внутри каждой — index scan или seq scan по customer_id. Без ограничения по дате — все 36 партиций.

Ключ партиционирования должен присутствовать в WHERE **подавляющего большинства** запросов. Если большинство запросов фильтрует по дате — партиционирование по дате. Если по customer_id — по customer_id. Но партиционирование по customer_id делает невозможным retention через DROP — данные всех дат перемешаны в каждой партиции, и удаление старых записей снова требует DELETE.

Sub-partitioning решает проблему частично: `RANGE(created_at)` на первом уровне, `HASH(customer_id)` на втором. 12 месяцев × 8 хеш-партиций = 96 партиций. Retention работает (DROP целого месяца), запросы по customer_id сужаются до одной хеш-партиции внутри каждого месяца.

Цена: больше партиций — больше файлов, дольше планирование. При сотнях и тысячах партиций overhead планировщика становится ощутимым — он проверяет каждую партицию для pruning.

## Операции с партициями и блокировки

### ATTACH PARTITION

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

### DETACH PARTITION

```sql
ALTER TABLE events DETACH PARTITION events_2025_11;
DROP TABLE events_2025_11;
```

DETACH + DROP — альтернатива `DELETE FROM events WHERE created_at < '2025-12-01'`. DELETE создаёт миллионы dead tuples, DROP — мгновенная DDL-операция.

`DETACH PARTITION CONCURRENTLY` (PostgreSQL 14+) — неблокирующий detach. Не берёт `ACCESS EXCLUSIVE` на родительскую таблицу, но нельзя использовать внутри транзакции.

## Sources

- PostgreSQL Documentation (v16): Partitioning. <https://www.postgresql.org/docs/16/ddl-partitioning.html>
