---
tags:
  - domain/sql
  - theme/indexing
  - theme/performance
  - type/concept
aliases:
  - Indexes
  - CREATE INDEX
  - B-tree
  - Covering Index
order: 16
---

# Индексы

**Предпосылки:** [таблицы и типы](tables-and-types.md) (CREATE TABLE), [ограничения](constraints.md) ([PRIMARY KEY](constraints.md), [UNIQUE](constraints.md)).

← [Представления](views.md) | [Пагинация](../querying/pagination.md) →

Таблица `orders` — 50 млн строк. Запрос `SELECT * FROM orders WHERE customer_id = 42` выполняется секунды: PostgreSQL читает **все** строки (Seq Scan) и проверяет условие для каждой. Ради одной строки сканируются миллионы — это как перебирать весь массив вместо обращения к хеш-таблице по ключу.

Индекс — структура данных (обычно B-tree), которая позволяет найти нужные строки без полного сканирования.

## CREATE INDEX

```sql
CREATE INDEX idx_orders_customer ON orders (customer_id);
```

После создания индекса PostgreSQL использует Index Scan вместо Seq Scan — проходит по дереву индекса и сразу находит строки с `customer_id = 42`, не трогая остальные 49 999 999 строк.

Проверка через EXPLAIN — команду PostgreSQL, которая показывает план выполнения запроса (какие шаги СУБД предпримет и какова их ожидаемая стоимость):

```
-- До индекса:
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;

Seq Scan on orders  (cost=0.00..1125000.00 rows=50 width=120)
  Filter: (customer_id = 42)

-- После индекса:
Index Scan using idx_orders_customer on orders  (cost=0.56..8.58 rows=50 width=120)
  Index Cond: (customer_id = 42)
```

`Seq Scan` — последовательный просмотр всей таблицы, `Index Scan` — поиск через индекс. Стоимость снизилась на порядки. Подробнее о чтении планов — в [EXPLAIN](../../postgresql/query-processing/explain.md).

## Уникальный индекс

```sql
CREATE UNIQUE INDEX idx_users_email ON users (email);
```

UNIQUE INDEX запрещает дубликаты — функционально эквивалентен UNIQUE [constraint](constraints.md) из [ограничений](constraints.md). PostgreSQL реализует UNIQUE [constraint](constraints.md) через уникальный индекс.

## Составной индекс

```sql
CREATE INDEX idx_orders_customer_date ON orders (customer_id, created_at);
```

Составной (composite) индекс по нескольким столбцам. B-tree отсортирован сначала по первому столбцу, внутри каждого значения — по второму. Индекс `(customer_id, created_at)` — как телефонная книга, упорядоченная по фамилии, а внутри фамилии — по имени.

Отсюда **leftmost prefix principle**: индекс эффективен для запросов, использующих столбцы слева направо. Запрос по `customer_id` — да, по `customer_id + created_at` — да, **только** по `created_at` — традиционно нет, потому что без customer_id индекс не может эффективно сузить область поиска.

```
-- оба столбца: Index Scan
EXPLAIN SELECT * FROM orders
WHERE customer_id = 42 AND created_at >= '2026-01-01';

Index Scan using idx_orders_customer_date on orders
  Index Cond: (customer_id = 42 AND created_at >= '2026-01-01')

-- только первый столбец: Index Scan
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;

Index Scan using idx_orders_customer_date on orders
  Index Cond: (customer_id = 42)

-- только второй столбец: Seq Scan (или Skip Scan в PG 18)
EXPLAIN SELECT * FROM orders WHERE created_at = '2026-02-01';

Seq Scan on orders
  Filter: (created_at = '2026-02-01')
```

**Skip scan:** если leading column имеет мало уникальных значений (low cardinality), некоторые СУБД умеют перебирать все distinct значения и использовать индекс. В PostgreSQL (начиная с версии 18) индекс `(status, created_at)` где status ∈ {active, pending, done} — планировщик выполнит 3 отдельных index scan'а. Но если leading column — customer_id с миллионом уникальных значений, skip scan неэффективен. Порядок столбцов по-прежнему критичен — skip scan оптимизация для частного случая, а не отмена правила.

Правило: ставьте столбцы с фильтрацией по `=` первыми, столбцы с range-фильтрацией (`BETWEEN`, `<`, `>`) — последними.

## Частичный индекс

```sql
CREATE INDEX idx_orders_active ON orders (customer_id)
WHERE status = 'active';
```

Partial index индексирует **подмножество** строк. 50 млн заказов, из них 0.1% имеют `status = 'active'`. Полный индекс по customer_id — ~400 МБ. Partial index с `WHERE status = 'active'` индексирует только 50 000 строк — меньше 1 МБ. INSERT завершённого заказа (`status = 'completed'`) вообще не трогает этот индекс.

PostgreSQL использует partial index, только если WHERE запроса является **подмножеством** предиката индекса. `WHERE status = 'active' AND customer_id = 42` — да, планировщик понимает, что все результаты попадают в индекс. `WHERE status IN ('active', 'pending')` — нет, pending не покрыт предикатом.

## Expression-индекс

```sql
CREATE INDEX idx_orders_payload_type ON orders ((payload ->> 'type'));
```

Индекс по выражению — для вычисляемых значений. Полезен для JSONB-полей и функций (`lower(email)`).

## Покрывающий индекс (INCLUDE)

Запрос `SELECT created_at, total FROM orders WHERE customer_id = 42` с индексом `(customer_id, created_at)` находит строки через индекс, но за значением `total` обращается к основной таблице. Каждое такое обращение — random I/O.

INCLUDE добавляет дополнительные столбцы в leaf pages индекса:

```sql
CREATE INDEX idx_orders_covering
ON orders (customer_id, created_at) INCLUDE (total);
```

Теперь СУБД может ответить на запрос только из индекса — обращение к таблице не нужно (в PostgreSQL это называется Index Only Scan). Столбцы в INCLUDE не влияют на сортировку — они просто хранятся рядом с записями индекса.

После массовых обновлений СУБД может обращаться к таблице для проверки видимости строк — Index Only Scan временно теряет преимущество. Подробности — в [[databases/postgresql/indexes/btree#index-only-scan-обход-без-heap|B-tree]].

## Когда индекс не нужен

Индекс ускоряет чтение, но **замедляет запись**: каждый INSERT и UPDATE обновляет все индексы таблицы.

Индекс не поможет, если столбец имеет **низкую селективность**: boolean с распределением 50/50 — СУБД выбирает полный просмотр таблицы, потому что половина строк подходит под условие. Индекс не поможет и для **маленьких таблиц** (сотни строк) — полный просмотр быстрее за счёт sequential I/O.

Если запрос возвращает большую долю таблицы (например, 70% строк), СУБД выбирает полный просмотр — читать всё подряд дешевле, чем прыгать по индексу при низкой селективности.

По умолчанию СУБД создаёт B-tree — подходит для `=`, `<`, `>`, `BETWEEN`, `IN`. Для поиска внутри составных значений (JSONB, массивы, полнотекстовый поиск) применяется GIN, для диапазонных типов и геометрии — GiST, для поиска только по равенству — Hash, для огромных append-only таблиц — BRIN. Подробности каждого типа — в [PostgreSQL: индексы](../../postgresql/indexes/btree.md).

Создание и обслуживание индексов на production-таблицах требует осторожности — [PostgreSQL: индексы в production](../postgresql/index-operations.md). Создание индексов как часть миграции (включая уникальные индексы для constraints) — [миграции](../../migrations/safe-schema-changes.md).

## Sources

- PostgreSQL Documentation (v16): CREATE INDEX. <https://www.postgresql.org/docs/16/sql-createindex.html>
- PostgreSQL Documentation (v16): Index Types. <https://www.postgresql.org/docs/16/indexes-types.html>

---

← [Представления](views.md) | [Пагинация](../querying/pagination.md) →
