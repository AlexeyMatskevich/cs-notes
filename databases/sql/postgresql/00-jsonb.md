# JSONB

<details>
<summary>Предпосылки</summary>

[SELECT и фильтрация](../querying/00-select-and-filtering.md), [соединения](../querying/03-joins.md), [индексы](../schema/04-indexes.md) (CREATE INDEX, типы индексов).

</details>

← [PostgreSQL: расширения](index.md) | [Массивы и диапазоны](01-arrays-and-ranges.md) →

E-commerce платформа принимает платежи через 50 провайдеров. Каждый возвращает свой JSON: Stripe — `charge_id`, `balance_transaction`, `receipt_url`; PayPal — `payer_id`, `capture_id`, `links[]`. Создавать 50 nullable-столбцов (в основном NULL для каждой строки) — нормализация вредит: схема раздувается, ALTER TABLE на каждого нового провайдера, 95% значений пустые.

Решение: нормализованные поля для общих данных (`amount`, `status`, `provider`) + JSONB-столбец `provider_data` для provider-specific ответа.

PostgreSQL хранит JSON в двух типах: `json` (текст, сохраняется «как есть») и `jsonb` (binary, парсится при записи). JSONB быстрее для чтения и поддерживает индексы — на практике почти всегда выбирается JSONB.

## Создание и вставка

```sql
CREATE TABLE events (
    id      BIGSERIAL PRIMARY KEY,
    payload JSONB NOT NULL
);

INSERT INTO events (payload) VALUES
('{"type": "click", "page": "/products", "user_id": 42}'),
('{"type": "purchase", "total": 150, "items": ["book", "pen"]}'),
('{"type": "click", "page": "/about", "user_id": 42, "referrer": "google"}');
```

## Операторы доступа

`->` — извлечение по ключу, результат JSONB:

```sql
SELECT payload -> 'type' FROM events;
```

```
   ?column?
-----------
 "click"
 "purchase"
 "click"
```

`->>` — извлечение по ключу, результат TEXT:

```sql
SELECT payload ->> 'type' FROM events;
```

```
 ?column?
----------
 click
 purchase
 click
```

Разница: `->` возвращает JSONB (с кавычками), `->>` — TEXT (без кавычек). Для сравнений в WHERE обычно нужен `->>`:

```sql
SELECT * FROM events WHERE payload ->> 'type' = 'click';
```

### Вложенные ключи

```sql
SELECT payload -> 'items' -> 0 FROM events WHERE id = 2;
```

```
 ?column?
----------
 "book"
```

`-> 0` — доступ к элементу массива по индексу.

### Путь через #> и #>>

```sql
SELECT payload #>> '{items, 0}' FROM events WHERE id = 2;
```

Результат: `book` (TEXT). `#>` и `#>>` принимают путь как массив ключей.

## Операторы проверки

`@>` — содержит (contains):

```sql
SELECT * FROM events WHERE payload @> '{"type": "click"}';
```

Возвращает строки, где `payload` содержит ключ `type` со значением `click`.

`?` — существует ключ:

```sql
SELECT * FROM events WHERE payload ? 'referrer';
```

Только третья строка — у неё есть ключ `referrer`.

`?|` — существует хотя бы один из ключей. `?&` — существуют все указанные ключи.

## Функции

`jsonb_each(jsonb)` — разворачивает объект в строки key/value:

```sql
SELECT key, value
FROM events, jsonb_each(payload)
WHERE id = 1;
```

```
   key   |    value
---------+-------------
 type    | "click"
 page    | "/products"
 user_id | 42
```

`jsonb_array_elements(jsonb)` — разворачивает массив в строки:

```sql
SELECT jsonb_array_elements(payload -> 'items')
FROM events
WHERE id = 2;
```

```
 jsonb_array_elements
---------------------
 "book"
 "pen"
```

`jsonb_set(target, path, new_value)` — создаёт новый JSONB с изменённым значением:

```sql
UPDATE events
SET payload = jsonb_set(payload, '{page}', '"/new-page"')
WHERE id = 1;
```

## Индексирование JSONB

Для эффективного поиска по JSONB — [GIN индекс](../../postgresql/indexes/01-gin.md):

```sql
CREATE INDEX events_payload_idx ON events USING gin (payload);
```

По умолчанию GIN использует класс операторов `jsonb_ops` — поддерживает `@>`, `?`, `?|`, `?&`. Индексирует каждый ключ и значение на каждом уровне вложенности.

Альтернатива — `jsonb_path_ops`:

```sql
CREATE INDEX events_payload_path_idx ON events USING gin (payload jsonb_path_ops);
```

`jsonb_path_ops` поддерживает **только** оператор `@>`, но индекс компактнее и быстрее — хранит хеши путей вместо отдельных ключей и значений. Если все запросы используют `@>` (containment) — `jsonb_path_ops` предпочтительнее.

Для поиска по **конкретному ключу** с `=` — expression B-tree эффективнее обоих вариантов GIN:

```sql
CREATE INDEX events_type_idx ON events ((payload ->> 'type'));
```

Поддерживает `WHERE payload ->> 'type' = 'click'` через обычный B-tree — точное совпадение, range-запросы и сортировка.

## Когда JSONB, а когда столбцы

JSONB оправдан, когда: структура **варьируется между строками** (ответы разных провайдеров), набор ключей **непредсказуем** (пользовательские настройки, metadata), или данные **читаются целиком** и редко фильтруются по отдельным полям.

Обычные столбцы лучше, когда: структура **стабильна** (amount, status — одинаковы для всех строк), поле участвует в **WHERE, JOIN или ORDER BY** (B-tree на столбце эффективнее GIN на JSONB-ключе), нужны **CHECK constraints** или **FK** (JSONB не поддерживает ни то, ни другое).

Главная gotcha: UPDATE JSONB выглядит точечным — `jsonb_set(payload, '{status}', '"paid"')` меняет один ключ. Но PostgreSQL записывает **новый tuple с полным значением** JSONB. Если payload = 10 КБ и обновляется раз в секунду, каждое обновление пишет 10 КБ в WAL и создаёт dead tuple. Для часто обновляемых полей — выносить в обычные столбцы.

## Sources

- PostgreSQL Documentation (v16): JSON Types. <https://www.postgresql.org/docs/16/datatype-json.html>
- PostgreSQL Documentation (v16): JSON Functions and Operators. <https://www.postgresql.org/docs/16/functions-json.html>

---

← [PostgreSQL: расширения](index.md) | [Массивы и диапазоны](01-arrays-and-ranges.md) →
