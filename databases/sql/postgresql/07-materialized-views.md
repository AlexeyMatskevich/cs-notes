# Материализованные представления

**Предпосылки:** [представления](../schema/03-views.md) (CREATE VIEW), [индексы](../schema/04-indexes.md) (UNIQUE INDEX).

← [Партиционирование](06-partitioning.md) | [DISTINCT ON](08-distinct-on.md) →

VIEW выполняет запрос заново при каждом SELECT. Дашборд аналитики по 50 млн заказов — 30 секунд ожидания. Для отчёта, обновляемого раз в 5 минут, допустимо показывать данные с задержкой, но не ждать 30 секунд.

## MATERIALIZED VIEW — снимок данных

MATERIALIZED VIEW (англ. «материализованное представление», от «материализовать» — превратить в материю) сохраняет результат запроса **на диск**:

```sql
CREATE MATERIALIZED VIEW monthly_sales AS
SELECT date_trunc('month', created_at) AS month,
       SUM(total) AS revenue,
       COUNT(*) AS order_count
FROM orders
GROUP BY date_trunc('month', created_at);
```

В отличие от обычного view, данные вычисляются один раз и хранятся физически. Запросы к materialized view быстрые — это обычное чтение таблицы. Но данные могут устареть.

Конкретика: `monthly_sales` на 50 млн строк выполняется 30 секунд. Cron запускает REFRESH каждые 5 минут. Между рефрешами данные устарели максимум на 5 минут. Для аналитического дашборда — допустимо, для real-time отображения баланса — нет.

## REFRESH и блокировки

```sql
REFRESH MATERIALIZED VIEW monthly_sales;
```

Обычный REFRESH **блокирует чтение** materialized view на время выполнения. 30 секунд без доступа к данным на production неприемлемо.

## REFRESH CONCURRENTLY

```sql
CREATE UNIQUE INDEX monthly_sales_month_idx ON monthly_sales (month);
REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_sales;
```

CONCURRENTLY требует UNIQUE INDEX на materialized view. PostgreSQL вычисляет новые данные, сравнивает с существующими (diff), применяет изменения. Это медленнее обычного REFRESH, но не блокирует чтение. В самом конце — кратковременный lock для подмены данных (миллисекунды, не секунды). Без UNIQUE INDEX CONCURRENTLY невозможен — PostgreSQL не может вычислить diff без ключа для сопоставления строк.

## Когда использовать

Обычный view — когда данные должны быть всегда актуальны и запрос не слишком тяжёлый. Materialized view — для тяжёлых аналитических запросов, где допустима задержка в актуальности данных.

## Sources

- PostgreSQL Documentation (v16): CREATE MATERIALIZED VIEW. <https://www.postgresql.org/docs/16/sql-creatematerializedview.html>
- PostgreSQL Documentation (v16): REFRESH MATERIALIZED VIEW. <https://www.postgresql.org/docs/16/sql-refreshmaterializedview.html>

---

← [Партиционирование](06-partitioning.md) | [DISTINCT ON](08-distinct-on.md) →
