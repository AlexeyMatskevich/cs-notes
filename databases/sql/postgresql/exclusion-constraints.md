---
tags:
  - domain/sql
  - theme/schema-evolution
  - type/concept
aliases:
  - EXCLUSION
  - EXCLUDE USING
  - GiST
order: 27
---

# EXCLUSION — запрет пересечений

**Предпосылки:** [ограничения](../schema/constraints.md) (CHECK, UNIQUE), [индексы](../schema/indexes.md) (CREATE INDEX).

← [Индексы в production](index-operations.md) | [Партиционирование](partitioning.md) →

UNIQUE гарантирует: нет двух строк с одинаковым email. Но бронирование зала — другая задача: коворкинг на 200 залов, 50 000 бронирований в месяц. Два бронирования с разными id могут конфликтовать, если их временные диапазоны пересекаются. Стандартный SQL не имеет механизма проверки пересечений.

## EXCLUDE USING

EXCLUSION (англ. «исключение, невозможность одновременного существования») проверяет, что для любой пары строк заданные операторы не выполняются одновременно.

Оператор `=` для скалярных типов (integer, text) не поддерживается GiST нативно. Расширение `btree_gist` добавляет GiST-поддержку для обычных типов, чтобы их можно было комбинировать с диапазонными типами в одном constraint:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE bookings (
    room_id BIGINT NOT NULL,
    during  TSRANGE NOT NULL
);

ALTER TABLE bookings
ADD CONSTRAINT bookings_no_overlap
EXCLUDE USING gist (
    room_id WITH =,
    during  WITH &&
);
```

«Для одинакового `room_id` диапазоны `during` не могут пересекаться (`&&`)». Без `btree_gist` PostgreSQL не сможет создать GiST-индекс по `room_id WITH =` и вернёт ошибку. Структура GiST — в [GiST](../../postgresql/indexes/gist.md).

Поведение constraint на четырёх бронированиях:

```sql
INSERT INTO bookings (room_id, during)
VALUES (1, '[2026-03-01 10:00, 2026-03-01 12:00)');
-- OK — первое бронирование

INSERT INTO bookings (room_id, during)
VALUES (1, '[2026-03-01 11:00, 2026-03-01 13:00)');
-- ERROR: conflicting key value violates exclusion constraint "bookings_no_overlap"
-- пересечение: 11:00-12:00

INSERT INTO bookings (room_id, during)
VALUES (1, '[2026-03-01 12:00, 2026-03-01 14:00)');
-- OK — не пересекается: скобка ')' в первом бронировании означает «не включая 12:00»

INSERT INTO bookings (room_id, during)
VALUES (2, '[2026-03-01 11:00, 2026-03-01 13:00)');
-- OK — другая комната, constraint проверяет пересечение только при совпадении room_id
```

Третий INSERT — ключевой граничный случай: `[10:00, 12:00)` не включает 12:00, поэтому `[12:00, 14:00)` не пересекается. Нотация `[)` — полуоткрытый интервал, типичная конвенция для бронирований и слотов.

## Блокировки при добавлении

EXCLUDE USING GiST при добавлении на заполненную таблицу берёт SHARE (англ. «разделяемый») lock — блокирует запись на время создания GiST-индекса **и** проверки всех существующих строк на конфликты. На таблице 50 000 бронирований это ~30 секунд.

В отличие от UNIQUE и PRIMARY KEY, EXCLUSION constraint не поддерживает `ALTER TABLE ... USING INDEX` — PostgreSQL всегда создаёт индекс сам при добавлении constraint. Обойти блокировку нельзя: добавление EXCLUSION на большую таблицу требует maintenance window или периода низкой нагрузки.

## Sources

- PostgreSQL Documentation (v16): Exclusion Constraints. <https://www.postgresql.org/docs/16/ddl-constraints.html#DDL-CONSTRAINTS-EXCLUSION>
- PostgreSQL Documentation (v16): btree_gist. <https://www.postgresql.org/docs/16/btree-gist.html>

---

← [Индексы в production](index-operations.md) | [Партиционирование](partitioning.md) →
