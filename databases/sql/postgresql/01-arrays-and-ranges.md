# Массивы и диапазоны

**Предпосылки:** [SELECT и фильтрация](../querying/00-select-and-filtering.md), [агрегация](../querying/02-aggregation.md) (array_agg).

← [JSONB](00-jsonb.md) | [Полнотекстовый поиск](02-full-text-search.md) →

Товару нужны теги: «electronics», «portable», «sale». Классический подход — junction table: `product_tags(product_id, tag_id)`, отдельная таблица `tags(id, name)`. Это три таблицы и два JOIN для получения тегов товара. Для простых атомарных меток без атрибутов и без двусторонних запросов («какие товары у тега?» не нужно) массив `TEXT[]` проще — одна таблица, один столбец, без JOIN.

## ARRAY — массив значений

Любой тип данных PostgreSQL может быть массивом:

```sql
CREATE TABLE products (
    id   BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}'
);

INSERT INTO products (name, tags) VALUES
('Ноутбук', ARRAY['electronics', 'portable']),
('Книга',   '{books, education}'),
('Монитор', ARRAY['electronics']);
```

Две формы литерала: `ARRAY[...]` и `'{...}'`.

### Доступ к элементам

Индексация с 1 (не с 0):

```sql
SELECT name, tags[1] AS first_tag FROM products;
```

```
 name    | first_tag
---------+------------
 Ноутбук | electronics
 Книга   | books
 Монитор | electronics
```

### Операторы

`@>` — содержит:

```sql
SELECT name FROM products WHERE tags @> ARRAY['portable'];
```

```
 name
---------
 Ноутбук
```

`&&` — пересечение (overlap):

```sql
SELECT name FROM products WHERE tags && ARRAY['books', 'portable'];
```

Строки, где `tags` содержит хотя бы один из указанных элементов.

`ANY` — элемент равен значению:

```sql
SELECT name FROM products WHERE 'electronics' = ANY(tags);
```

### unnest — разворачивание массива

`unnest(array)` превращает массив в набор строк:

```sql
SELECT name, unnest(tags) AS tag
FROM products;
```

```
 name    | tag
---------+------------
 Ноутбук | electronics
 Ноутбук | portable
 Книга   | books
 Книга   | education
 Монитор | electronics
```

Каждый элемент массива — отдельная строка. Обратная операция — `array_agg()`.

### Массив vs таблица связи

Массив подходит, когда: элементы — **атомарные метки** без собственных атрибутов (теги, роли, категории), количество элементов **невелико** (десятки, не тысячи), нет необходимости в **FK** (массив не может ссылаться на другую таблицу), и запросы идут **от владельца к элементам** («теги товара»), а не наоборот.

Junction table лучше, когда: у связи есть **атрибуты** (дата добавления тега, приоритет), нужны **двусторонние запросы** («все товары с тегом X» через индекс на tag_id), или элементы — сущности со своими данными (пользователи, категории с описаниями).

UPDATE массива перезаписывает **всё значение** — как и JSONB. Добавление одного тега к массиву из 100 элементов записывает в WAL все 100. Для часто изменяемых коллекций junction table эффективнее.

### Индексирование массивов

[GIN индекс](../../postgresql/indexes/01-gin.md) для операторов `@>`, `&&`:

```sql
CREATE INDEX products_tags_idx ON products USING gin (tags);
```

## Range types — диапазоны

Range type хранит диапазон значений: от и до, с указанием включения/исключения границ.

Встроенные типы:

| Тип | Элементы |
|---|---|
| `int4range` | integer |
| `int8range` | bigint |
| `numrange` | numeric |
| `tsrange` | timestamp |
| `tstzrange` | timestamptz |
| `daterange` | date |

```sql
CREATE TABLE bookings (
    id      BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL,
    during  TSRANGE NOT NULL
);

INSERT INTO bookings (room_id, during) VALUES
(1, '[2024-03-15 09:00, 2024-03-15 11:00)'),
(1, '[2024-03-15 11:00, 2024-03-15 13:00)'),
(2, '[2024-03-15 09:00, 2024-03-15 12:00)');
```

`[` — включая границу, `)` — исключая границу. `[09:00, 11:00)` — от 9:00 (включительно) до 11:00 (не включая).

### Операторы диапазонов

`&&` — пересечение (overlap):

```sql
SELECT * FROM bookings
WHERE during && '[2024-03-15 10:00, 2024-03-15 12:00)';
```

Строки, диапазон которых пересекается с указанным.

`@>` — содержит значение:

```sql
SELECT * FROM bookings WHERE during @> '2024-03-15 10:30'::timestamp;
```

`<@` — содержится в диапазоне. `-|-` — смежность (adjacent).

### EXCLUDE constraint — защита от пересечений

Два пользователя одновременно бронируют комнату 1 на пересекающееся время. Без constraint оба INSERT проходят — в базе два конфликтующих бронирования. Проверка на уровне приложения (`SELECT ... WHERE during && ...` перед INSERT) не спасает: между SELECT и INSERT другая транзакция может вставить свою запись (race condition).

EXCLUDE constraint решает проблему на уровне базы:

```sql
ALTER TABLE bookings
ADD CONSTRAINT bookings_no_overlap
EXCLUDE USING gist (room_id WITH =, during WITH &&);
```

Для `room_id WITH =` необходимо расширение `btree_gist` — подробнее в [EXCLUSION](05-exclusion-constraints.md).

`room_id WITH =` — ограничение на одну и ту же комнату. `during WITH &&` — диапазоны не должны пересекаться. [GiST индекс](../../postgresql/indexes/02-gist.md) обеспечивает эффективную проверку — PostgreSQL не сканирует все бронирования, а проверяет только потенциальные конфликты через дерево.

Для нескольких ресурсов (комната + оборудование) — дополнительные столбцы в EXCLUDE:

```sql
EXCLUDE USING gist (
    room_id      WITH =,
    equipment_id WITH =,
    during       WITH &&
);
```

Подробнее — в [ограничениях](../schema/01-constraints.md).

### Индексирование диапазонов

[GiST индекс](../../postgresql/indexes/02-gist.md) для операторов `&&`, `@>`, `<@`:

```sql
CREATE INDEX bookings_during_idx ON bookings USING gist (during);
```

## Sources

- PostgreSQL Documentation (v16): Arrays. <https://www.postgresql.org/docs/16/arrays.html>
- PostgreSQL Documentation (v16): Range Types. <https://www.postgresql.org/docs/16/rangetypes.html>

---

← [JSONB](00-jsonb.md) | [Полнотекстовый поиск](02-full-text-search.md) →
