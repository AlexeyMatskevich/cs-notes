---
tags:
  - domain/sql
  - theme/data-representation
  - theme/performance
  - type/concept
aliases:
  - Compound DML
  - INSERT...SELECT
  - MERGE
  - VALUES
order: 20
---

# Составные DML-операции

> [!info]- Предпосылки
> [DML](dml.md) (INSERT, UPDATE, DELETE), [подзапросы](../querying/subqueries-and-cte.md) (EXISTS, подзапрос в FROM), [соединения](../querying/joins.md).

← [Транзакции](transactions.md) | [PostgreSQL: расширения SQL](../postgresql/pg-extensions.md) →

[Транзакции](transactions.md) делают серию команд атомарной: BEGIN, 1000 UPDATE, COMMIT — либо все, либо ни один. Но атомарность не убирает round-trip'ы: каждый UPDATE — отдельный запрос к базе. Приложение получает от поставщика 1000 обновлений цен. Наивный подход: цикл в коде — SELECT текущую цену, вычислить разницу, UPDATE. 1000 итераций × 2 запроса = 2000 round-trip'ов. При latency 5 мс — 10 секунд только на сеть. Хуже: между SELECT и UPDATE — окно, в которое другая транзакция может изменить цену.

Составные DML-операции решают обе проблемы: один SQL-запрос читает, трансформирует и записывает данные за один round-trip. Окна между чтением и записью нет.

Все примеры ниже работают с двумя таблицами — каталог интернет-магазина и staging-таблица с данными поставщика:

```sql
-- Каталог магазина
products(id, sku, name, price, updated_at)

-- Staging-таблица с данными от поставщика (загружена через COPY/import)
supplier_catalog(sku, name, price)
```

Поставщик ежедневно выгружает свой каталог в `supplier_catalog`. Задача: сравнить с `products`, вставить новые товары, обновить существующие.

## INSERT...SELECT — вставка из запроса

Первый шаг синхронизации: вставить товары, которых ещё нет в каталоге.

```sql
INSERT INTO products (sku, name, price, updated_at)
SELECT sc.sku, sc.name, sc.price, CURRENT_TIMESTAMP
FROM supplier_catalog sc
WHERE NOT EXISTS (
    SELECT 1 FROM products p WHERE p.sku = sc.sku
);
```

Данные не покидают базу: SELECT читает из `supplier_catalog`, фильтрует по `products`, INSERT записывает результат. Одна операция вместо цикла «прочитать → проверить в коде → вставить».

[DML](dml.md) показывает базовый INSERT...SELECT (архивирование заказов). Здесь добавлено: подзапрос для фильтрации дубликатов, вычисление `CURRENT_TIMESTAMP` на лету.

В PostgreSQL INSERT...SELECT можно дополнить `RETURNING` для получения вставленных строк без отдельного SELECT — подробнее в [составных DML в PostgreSQL](../postgresql/compound-dml.md).

## VALUES как источник данных из приложения

Не всегда данные уже в staging-таблице. Небольшие batch'и (ручные корректировки, точечные добавления) приложение может передать прямо в запросе — через VALUES как виртуальную таблицу:

```sql
INSERT INTO products (sku, name, price, updated_at)
SELECT v.sku, v.name, v.price, CURRENT_TIMESTAMP
FROM (VALUES
    ('SKU-NEW-1', 'Widget', 1500),
    ('SKU-NEW-2', 'Gadget', 2300)
) AS v(sku, name, price)
WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.sku = v.sku);
```

VALUES создаёт таблицу прямо в SQL — без staging. Приложение формирует запрос с нужными значениями, база фильтрует дубликаты и записывает. Один round-trip вместо цикла «проверить → вставить».

VALUES удобен для небольших payload'ов в памяти приложения (десятки-сотни строк). Для крупных синхронизаций (десятки тысяч строк) — staging table + COPY: загрузить данные во временную таблицу, затем оперировать ею как обычной. Бесконечно растущий VALUES — антипаттерн: парсинг SQL дорожает линейно с размером запроса.

## MERGE — условная синхронизация

Вставка новых товаров — только первый шаг. Существующие товары тоже нужно обновить: цена могла измениться. [INSERT ON CONFLICT](dml.md) решает upsert, но привязан к уникальному индексу и не поддерживает условные ветки.

MERGE (SQL:2003, PostgreSQL 15+) — стандартный способ условной синхронизации:

```sql
MERGE INTO products p
USING supplier_catalog sc ON p.sku = sc.sku
WHEN MATCHED AND sc.price <> p.price THEN
    UPDATE SET price = sc.price, updated_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN
    INSERT (sku, name, price, updated_at)
    VALUES (sc.sku, sc.name, sc.price, CURRENT_TIMESTAMP);
```

Две ветки в одном операторе: MATCHED (обновить, если цена изменилась), NOT MATCHED (вставить новый). MERGE работает с любым JOIN-условием (не только уникальный индекс) и поддерживает фильтры в каждой ветке — `AND sc.price <> p.price` пропускает строки, где цена не менялась.

| | ON CONFLICT | MERGE |
|---|---|---|
| Действия | INSERT + UPDATE | INSERT + UPDATE |
| Условие совпадения | Уникальный индекс/constraint | Любой JOIN |
| Условные ветки | Нет | WHEN ... AND условие |
| Стандарт SQL | Нет (PostgreSQL) | Да (SQL:2003) |

ON CONFLICT проще для upsert по уникальному ключу. MERGE — когда нужен произвольный JOIN или условная логика в ветках.

PostgreSQL 17 добавляет `WHEN NOT MATCHED BY SOURCE` (удаление строк без пары в источнике) — подробнее в [составных DML в PostgreSQL](../postgresql/compound-dml.md).

## Когда оставить обработку в приложении

Составные DML эффективны для чистых трансформаций данных: перемещение, обогащение, агрегация → запись. Но не всё стоит переносить в SQL:

- Побочные эффекты между шагами (HTTP-вызовы, отправка email) — база не может выполнить.
- Сложная ветвящаяся бизнес-логика — читаемее и тестируемее в коде приложения.
- Отладка — stack trace информативнее, чем ошибка в многострочном SQL.

PostgreSQL расширяет составные DML: UPDATE через JOIN, цепочки DML-операций, полная синхронизация с удалением — [составные DML в PostgreSQL](../postgresql/compound-dml.md).

## Sources

- PostgreSQL Documentation (v16): INSERT. <https://www.postgresql.org/docs/16/sql-insert.html>
- PostgreSQL Documentation (v16): MERGE. <https://www.postgresql.org/docs/16/sql-merge.html>
- SQL Standard (ISO/IEC 9075): MERGE statement (SQL:2003)

---

← [Транзакции](transactions.md) | [PostgreSQL: расширения SQL](../postgresql/pg-extensions.md) →
