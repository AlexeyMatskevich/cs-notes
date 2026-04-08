---
tags:
  - domain/sql
  - theme/data-representation
  - theme/performance
  - type/concept
aliases:
  - Writable CTE
  - UPDATE...FROM
  - DELETE...USING
  - MERGE
order: 30
---

# Составные DML в PostgreSQL

> [!info]- Предпосылки
> [Составные DML-операции](../modification/compound-dml.md) (INSERT...SELECT, VALUES, MERGE), [DML](../modification/dml.md) (RETURNING, INSERT ON CONFLICT), [подзапросы и CTE](../querying/subqueries-and-cte.md) (WITH).

Стандартный SQL решает вставку новых товаров и условное обновление через MERGE. Полная синхронизация включает ещё: массовое обновление цен через JOIN, удаление снятых товаров, архивирование с логированием. PostgreSQL добавляет инструменты для каждого шага.

Таблицы из [base-note](../modification/compound-dml.md) и две дополнительных для архивирования:

```sql
-- Из base-note:
products(id, sku, name, price, updated_at)
supplier_catalog(sku, name, price)

-- Для архивирования и аудита:
products_archive(id, sku, name, price, removed_at)
audit_log(id, action, entity, entity_id, created_at)
```

## UPDATE...FROM — массовое обновление через JOIN

Стандартный SQL обновляет через коррелированный подзапрос в SET:

```sql
-- Стандартный SQL
UPDATE products
SET price = (SELECT sc.price FROM supplier_catalog sc WHERE sc.sku = products.sku),
    updated_at = CURRENT_TIMESTAMP
WHERE EXISTS (
    SELECT 1 FROM supplier_catalog sc
    WHERE sc.sku = products.sku AND sc.price <> products.price
);
```

PostgreSQL добавляет FROM-клаузу — UPDATE с JOIN:

```sql
UPDATE products p
SET price = sc.price,
    updated_at = now()
FROM supplier_catalog sc
WHERE p.sku = sc.sku
  AND sc.price <> p.price
RETURNING p.id, p.sku, p.price;
```

FROM читается яснее при обновлении нескольких столбцов — не нужно повторять подзапрос для каждого. RETURNING сразу возвращает обновлённые строки.

Та же конструкция работает с VALUES для небольших batch'ей из приложения:

```sql
UPDATE products p
SET price = v.new_price, updated_at = now()
FROM (VALUES ('SKU-001', 1500), ('SKU-002', 2300)) AS v(sku, new_price)
WHERE p.sku = v.sku
RETURNING p.id, p.sku, p.price;
```

## DELETE...USING — удаление через JOIN

Поставщик помечает снятые товары нулевой ценой. Аналог UPDATE...FROM для DELETE:

```sql
DELETE FROM products p
USING supplier_catalog sc
WHERE p.sku = sc.sku AND sc.price <= 0
RETURNING p.id, p.sku, p.name;
```

USING определяет таблицу для JOIN; условие WHERE фильтрует строки для удаления. Паттерн аналогичен UPDATE...FROM.

## Writable CTEs — цепочки операций

Удалённые товары нужно не просто удалить, а переместить в архив и записать в лог. Три операции, которые стандартный SQL выполнил бы тремя отдельными запросами. PostgreSQL позволяет поместить DML в WITH:

```sql
WITH removed AS (
    DELETE FROM products p
    USING supplier_catalog sc
    WHERE p.sku = sc.sku AND sc.price <= 0
    RETURNING p.*
),
archived AS (
    INSERT INTO products_archive (id, sku, name, price, removed_at)
    SELECT id, sku, name, price, now()
    FROM removed
    RETURNING id
)
INSERT INTO audit_log (action, entity, entity_id, created_at)
SELECT 'archive', 'product', id, now()
FROM archived;
```

Три DML-операции: DELETE → INSERT в архив → INSERT в лог. Каждый шаг использует RETURNING предыдущего как источник. Одна транзакция, один round-trip.

Writable CTEs — расширение PostgreSQL (не SQL-стандарт). Стандартный SQL ограничивает WITH только SELECT-запросами.

## MERGE: полная синхронизация с DELETE (PostgreSQL 17)

[Base-note](../modification/compound-dml.md) показывает стандартный MERGE (MATCHED + NOT MATCHED). PostgreSQL 17 добавляет третью ветку:

```sql
MERGE INTO products p
USING supplier_catalog sc ON p.sku = sc.sku
WHEN MATCHED AND sc.price <> p.price THEN
    UPDATE SET price = sc.price, updated_at = now()
WHEN NOT MATCHED THEN
    INSERT (sku, name, price, updated_at)
    VALUES (sc.sku, sc.name, sc.price, now())
WHEN NOT MATCHED BY SOURCE THEN
    DELETE;
```

Полная синхронизация в одном операторе: новые вставить, изменённые обновить, отсутствующие в источнике — удалить. `WHEN NOT MATCHED BY SOURCE` — расширение PostgreSQL 17, не часть SQL:2003.

## ON CONFLICT + SELECT как источник

[DML](../modification/dml.md) показывает ON CONFLICT с VALUES. PostgreSQL позволяет комбинировать ON CONFLICT с SELECT-источником — upsert данных из другой таблицы:

```sql
INSERT INTO products (sku, name, price, updated_at)
SELECT sc.sku, sc.name, sc.price, now()
FROM supplier_catalog sc
ON CONFLICT (sku)
DO UPDATE SET price = EXCLUDED.price, updated_at = now()
WHERE products.price <> EXCLUDED.price;
```

Та же синхронизация, что и MERGE, но через PostgreSQL-специфичный синтаксис. ON CONFLICT + SELECT — привычный паттерн для PG-разработчиков; MERGE — стандартный и более гибкий.

## Sources

- PostgreSQL Documentation (v16): UPDATE. <https://www.postgresql.org/docs/16/sql-update.html>
- PostgreSQL Documentation (v16): DELETE. <https://www.postgresql.org/docs/16/sql-delete.html>
- PostgreSQL Documentation (v17): MERGE. <https://www.postgresql.org/docs/17/sql-merge.html>
- PostgreSQL Documentation (v16): INSERT ON CONFLICT. <https://www.postgresql.org/docs/16/sql-insert.html#SQL-ON-CONFLICT>
