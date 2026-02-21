# Индексы

**Предпосылки:** [таблицы и типы](00-tables-and-types.md) (CREATE TABLE), [ограничения](01-constraints.md) (PRIMARY KEY, UNIQUE).

Таблица `orders` — 50 млн строк. Запрос `SELECT * FROM orders WHERE customer_id = 42` выполняется секунды: PostgreSQL читает **все** строки (Seq Scan) и проверяет условие для каждой. Ради одной строки сканируются миллионы — это как перебирать весь массив вместо обращения к хеш-таблице по ключу.

Индекс — структура данных (обычно B-tree), которая позволяет найти нужные строки без полного сканирования.

## CREATE INDEX

```sql
CREATE INDEX idx_orders_customer ON orders (customer_id);
```

После создания индекса PostgreSQL использует Index Scan вместо Seq Scan — проходит по дереву индекса и сразу находит строки с `customer_id = 42`, не трогая остальные 49 999 999 строк.

Проверка через EXPLAIN:

```
-- До индекса:
Seq Scan on orders  (cost=0.00..1125000.00 rows=50 width=120)
  Filter: (customer_id = 42)

-- После индекса:
Index Scan using idx_orders_customer on orders  (cost=0.56..8.58 rows=50 width=120)
  Index Cond: (customer_id = 42)
```

Стоимость снизилась на порядки — вместо чтения всей таблицы PostgreSQL обходит B-tree.

## Уникальный индекс

```sql
CREATE UNIQUE INDEX idx_users_email ON users (email);
```

UNIQUE INDEX запрещает дубликаты — функционально эквивалентен UNIQUE constraint из [ограничений](01-constraints.md). PostgreSQL реализует UNIQUE constraint через уникальный индекс.

## Составной индекс

```sql
CREATE INDEX idx_orders_customer_date ON orders (customer_id, created_at);
```

Составной (composite) индекс по нескольким столбцам. B-tree отсортирован сначала по первому столбцу, внутри каждого значения — по второму. Индекс `(customer_id, created_at)` — как телефонная книга, упорядоченная по фамилии, а внутри фамилии — по имени.

Отсюда **leftmost prefix principle**: индекс эффективен для запросов, использующих столбцы слева направо. Запрос по `customer_id` — да, по `customer_id + created_at` — да, **только** по `created_at` — традиционно нет, потому что без customer_id дерево не знает, в какую ветку идти.

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

INCLUDE (SQL:2016) добавляет дополнительные столбцы в leaf pages индекса:

```sql
CREATE INDEX idx_orders_covering
ON orders (customer_id, created_at) INCLUDE (total);
```

Теперь СУБД может ответить на запрос только из индекса — обращение к таблице не нужно (в PostgreSQL это называется Index Only Scan). Столбцы в INCLUDE не влияют на сортировку — они просто хранятся рядом с записями индекса.

В PostgreSQL эффективность зависит от visibility map: после массовых UPDATE она содержит «грязные» страницы, и движок делает fallback на обычный Index Scan с обращением к таблице — пока [VACUUM](../../postgresql/maintenance/00-vacuum.md) не обновит метаданные. Подробнее о структуре индекса — в [B-tree](../../postgresql/indexes/00-btree.md).

## Блокировки при создании индекса

`CREATE INDEX` берёт `SHARE` lock на таблицу — **блокирует INSERT, UPDATE и DELETE** на всё время создания. На таблице 50 млн строк это минуты. Пользователи не могут ничего записать, пока индекс строится.

Проблема усугубляется lock queue: ожидающий `SHARE` lock блокирует все последующие запросы, включая SELECT — они встают в очередь за ним. Подробнее о механизме блокировок — в [блокировках PostgreSQL](../../postgresql/concurrency/03-locks.md).

## CREATE INDEX CONCURRENTLY

```sql
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);
```

CONCURRENTLY (англ. «одновременно, параллельно») берёт `SHARE UPDATE EXCLUSIVE` lock — **не блокирует DML**. INSERT, UPDATE и DELETE продолжают работать во время создания индекса.

Механизм: PostgreSQL делает два прохода по таблице. Первый сканирует существующие строки. Второй собирает изменения, сделанные во время первого прохода. Цена: работает в 2–3 раза дольше, требует больше ресурсов, **нельзя использовать внутри транзакции** (поэтому транзакционный DDL здесь не работает — см. [функции и процедуры](../postgresql/03-functions-and-procedures.md)).

При сбое CONCURRENTLY оставляет индекс в состоянии `INVALID`. Такой индекс не используется для запросов, но занимает место. Нужно удалить его (`DROP INDEX idx_name`) и создать заново.

Правило: в production **всегда CONCURRENTLY**. Обычный CREATE INDEX — только для пустых таблиц или maintenance windows.

## REINDEX — пересоздание индекса

Зачем: после массового DELETE или UPDATE индекс может разрастись (bloat) — B-tree содержит пустые страницы, но не отдаёт их ОС.

```sql
REINDEX INDEX idx_orders_customer;
```

`REINDEX` берёт `ACCESS EXCLUSIVE` lock — блокирует **всё**, включая SELECT. На production это неприемлемо.

```sql
REINDEX INDEX CONCURRENTLY idx_orders_customer;  -- PostgreSQL 12+
```

`REINDEX CONCURRENTLY` — неблокирующий аналог. Создаёт новый индекс рядом со старым, затем подменяет. Альтернативный подход: создать новый индекс CONCURRENTLY с другим именем, затем DROP старый.

## Когда индекс не нужен

Индекс ускоряет чтение, но **замедляет запись**: каждый INSERT и UPDATE обновляет все индексы таблицы.

Индекс не поможет, если столбец имеет **низкую селективность**: boolean с распределением 50/50 — PostgreSQL выбирает Seq Scan, потому что половина таблицы подходит под условие. Индекс не поможет и для **маленьких таблиц** (сотни строк) — Seq Scan быстрее за счёт sequential I/O.

Если запрос возвращает большую долю таблицы (например, 70% строк), [планировщик](../../postgresql/query-processing/00-planner.md) может решить, что Seq Scan дешевле — читать всё подряд быстрее, чем прыгать по индексу.

## Типы индексов — обзор

По умолчанию PostgreSQL создаёт **B-tree** — покрывает операции `=`, `<`, `>`, `<=`, `>=`, `BETWEEN`, `IN`, `IS NULL`. Подробности — в [B-tree](../../postgresql/indexes/00-btree.md).

Для поиска **внутри составных значений** (JSONB `@>`, `?`; массивы `@>`, `&&`; полнотекстовый поиск `@@`) — [GIN](../../postgresql/indexes/01-gin.md).

Для **диапазонных типов и геометрии** (`&&`, `@>`, EXCLUSION constraints) — [GiST](../../postgresql/indexes/02-gist.md).

Для поиска **только по равенству** (`=`) — [Hash](../../postgresql/indexes/03-hash.md). Компактнее B-tree, но не поддерживает range-запросы.

Для **огромных таблиц с физически упорядоченными данными** (таблица логов с хронологической вставкой) — [BRIN](../../postgresql/indexes/04-brin.md). Крошечный индекс, но требует корреляции между физическим порядком строк и значениями.

## Sources

- PostgreSQL Documentation (v16): CREATE INDEX. <https://www.postgresql.org/docs/16/sql-createindex.html>
- PostgreSQL Documentation (v16): REINDEX. <https://www.postgresql.org/docs/16/sql-reindex.html>
- PostgreSQL Documentation (v16): Index Types. <https://www.postgresql.org/docs/16/indexes-types.html>
