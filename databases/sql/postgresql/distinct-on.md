---
tags:
  - domain/sql
  - theme/performance
  - type/concept
aliases:
  - DISTINCT ON
order: 31
---

# DISTINCT ON — top-1 в группе

**Предпосылки:** [оконные функции](../querying/window-functions.md) (ROW_NUMBER, PARTITION BY).

← [Материализованные представления](materialized-views.md)

Дашборд менеджера: для каждого из 50 отделов показать сотрудника с максимальной зарплатой. Стандартное решение — ROW_NUMBER + CTE: нумеруем все 100 000 сотрудников внутри каждого отдела, потом фильтруем `rn = 1`. Ради 50 результатов создаётся промежуточная нумерация на 100 000 строк. Для top-N (`rn <= N`) это единственный стандартный способ. Но для top-1 PostgreSQL сокращает запрос до одной строки.

## DISTINCT ON

DISTINCT ON (англ. «уникальный по») — для каждого уникального значения выражения PostgreSQL оставляет одну строку:

```sql
SELECT DISTINCT ON (department_id) department_id, name, salary
FROM employees
WHERE salary IS NOT NULL
ORDER BY department_id, salary DESC NULLS LAST;
```

```
 department_id | name     | salary
---------------+----------+--------
             1 | Анна     |  90000
             2 | Глеб     |  70000
          NULL | Евгений  |  55000
```

Для каждого уникального `department_id` PostgreSQL берёт первую строку по ORDER BY. Требование: выражение в DISTINCT ON должно быть в начале ORDER BY.

Планировщик использует Sort + Unique — один проход по отсортированным данным без промежуточного CTE. При индексе `(department_id, salary DESC)` сортировка не нужна — планировщик читает данные в нужном порядке напрямую из индекса и отбрасывает дубликаты по ходу.

## ROW_NUMBER vs DISTINCT ON

Стандартное решение для сравнения:

```sql
WITH ranked AS (
    SELECT name, department_id, salary,
           ROW_NUMBER() OVER (
               PARTITION BY department_id
               ORDER BY salary DESC NULLS LAST
           ) AS rn
    FROM employees
    WHERE salary IS NOT NULL
)
SELECT name, department_id, salary
FROM ranked
WHERE rn = 1;
```

Тот же результат, но ROW_NUMBER нумерует **все** строки во **всех** группах, потом фильтрует — на таблице 100 000 строк это ощутимо больше работы, чем Sort + Unique для 50 групп.

| Подход | Top-1 | Top-N | Стандарт SQL | Производительность (top-1) |
|---|---|---|---|---|
| ROW_NUMBER + CTE | да | да | да | нумерует все строки |
| DISTINCT ON | да | нет | нет (PG) | Sort + Unique или Index Scan |

DISTINCT ON — PostgreSQL-shortcut для частного случая top-1. Для top-N или портативного SQL — ROW_NUMBER + CTE. Для top-N с использованием индекса — [LATERAL](../querying/subqueries-and-cte.md#lateral--подзапрос-с-доступом-к-внешним-строкам).

## Sources

- PostgreSQL Documentation (v16): DISTINCT ON. <https://www.postgresql.org/docs/16/sql-select.html#SQL-DISTINCT>

---

← [Материализованные представления](materialized-views.md)
