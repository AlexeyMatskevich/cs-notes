# Операции над множествами

**Предпосылки:** [подзапросы и CTE](subqueries-and-cte.md) (подзапросы, CTE).

← [Подзапросы и CTE](subqueries-and-cte.md) | [Оконные функции](window-functions.md) →

Подзапросы вкладывают один запрос в другой. Но иногда нужно просто **объединить результаты** двух независимых запросов. У компании есть таблица `employees` (сотрудники) и таблица `customers` (клиенты):

```
employees:                    customers:
 name     | email              name    | email
----------+-----------        ---------+-------------
 Анна     | anna@c.co          Alice   | alice@ext.co
 Борис    | boris@c.co         Bob     | bob@ext.co
 Анна     | anna@c.co          Анна    | anna@c.co
```

Анна — и сотрудник, и клиент (один и тот же email). Задачи: единый список рассылки, пересечение, разность.

## Единый список рассылки — UNION

UNION (англ. «объединение») — SQL-реализация операции объединения из [реляционной алгебры](../foundations/relational-model.md#реляционная-алгебра). Объединяет результаты двух запросов, **удаляя дубликаты**:

```sql
SELECT name, email FROM employees
UNION
SELECT name, email FROM customers;
```

```
 name  | email
-------+-------------
 Alice | alice@ext.co
 Bob   | bob@ext.co
 Анна  | anna@c.co
 Борис | boris@c.co
```

Анна появилась один раз — UNION убрал дубликат. Визуально:

```
  employees       customers
  .-------.       .-------.
  |       |       |       |
  | Борис | Анна  | Alice |     UNION = всё вместе, без дубликатов
  |       |       | Bob   |
  '-------'       '-------'
```

Требования к UNION: оба SELECT должны возвращать **одинаковое количество столбцов**, и типы столбцов должны быть совместимы. Имена столбцов берутся из первого SELECT.

### UNION ALL — с дубликатами

UNION ALL сохраняет все строки, включая дубликаты:

```sql
SELECT name, email FROM employees
UNION ALL
SELECT name, email FROM customers;
```

Анна появится дважды. UNION ALL быстрее UNION, потому что не тратит ресурсы на дедупликацию. Если дубликаты не мешают или невозможны — используйте ALL.

## Кто и сотрудник, и клиент? — INTERSECT

INTERSECT (англ. «пересечение») возвращает строки, присутствующие в **обоих** результатах:

```sql
SELECT name, email FROM employees
INTERSECT
SELECT name, email FROM customers;
```

```
 name | email
------+----------
 Анна | anna@c.co
```

Только Анна есть в обеих таблицах.

```
  employees       customers
  .-------.       .-------.
  |       |///////|       |
  | Борис |/ Анна/| Alice |     INTERSECT = только пересечение
  |       |///////| Bob   |
  '-------'       '-------'
```

INTERSECT ALL сохраняет дубликаты (по количеству совпадений).

## Клиенты, не сотрудники — EXCEPT

EXCEPT (англ. «исключение, кроме») возвращает строки из первого результата, **отсутствующие** во втором:

```sql
SELECT name, email FROM customers
EXCEPT
SELECT name, email FROM employees;
```

```
 name  | email
-------+-------------
 Alice | alice@ext.co
 Bob   | bob@ext.co
```

Анна исключена — она есть среди сотрудников.

```
  employees       customers
  .-------.       .-------.
  |       |       |///////|
  | Борис | Анна  |/Alice/|     EXCEPT = правая минус пересечение
  |       |       |/ Bob /|
  '-------'       |///////|
                  '-------'
```

EXCEPT ALL — с учётом количества вхождений.

### EXCEPT vs LEFT JOIN + IS NULL

Задачу «клиенты, не сотрудники» можно решить и через LEFT JOIN (из [соединений](joins.md)):

```sql
SELECT c.name, c.email
FROM customers c
LEFT JOIN employees e ON c.email = e.email
WHERE e.email IS NULL;
```

Два подхода к одной задаче. EXCEPT компактнее, когда структура столбцов совпадает. LEFT JOIN гибче — позволяет сравнивать по произвольным столбцам и возвращать столбцы из обеих таблиц.

## Порядок и ограничение результата

Каждый SELECT в операции над множествами выполняет свой полный pipeline (FROM → WHERE → ... → SELECT). Операция применяется **после** завершения обоих pipeline.

ORDER BY и LIMIT относятся к **финальному результату**, а не к отдельным SELECT:

```sql
SELECT name, 'employee' AS source FROM employees
UNION ALL
SELECT name, 'customer' AS source FROM customers
ORDER BY name
LIMIT 5;
```

ORDER BY и LIMIT стоят после последнего SELECT и применяются ко всему объединению.

Если нужно отсортировать или ограничить отдельный SELECT внутри операции, его нужно обернуть в подзапрос:

```sql
(SELECT name FROM employees ORDER BY name LIMIT 3)
UNION ALL
(SELECT name FROM customers ORDER BY name LIMIT 3);
```

## NULL в операциях над множествами

Как и в DISTINCT, операции над множествами считают два NULL **одинаковыми** — [то же поведение](../foundations/types-and-null.md#null-в-разных-контекстах), что и в GROUP BY. UNION удалит дубликат из двух строк (NULL), INTERSECT их сопоставит, EXCEPT вычтет.

## Приоритет операций

INTERSECT имеет более высокий приоритет, чем UNION и EXCEPT:

```sql
A UNION B INTERSECT C
```

Выполняется как `A UNION (B INTERSECT C)`. Для другого порядка — скобки.

## Sources

- PostgreSQL Documentation (v16): UNION, INTERSECT, EXCEPT. <https://www.postgresql.org/docs/16/sql-select.html#SQL-UNION>

---

← [Подзапросы и CTE](subqueries-and-cte.md) | [Оконные функции](window-functions.md) →
