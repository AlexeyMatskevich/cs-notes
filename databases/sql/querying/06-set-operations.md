# Операции над множествами

**Предпосылки:** [подзапросы и CTE](05-subqueries-and-cte.md) (подзапросы, CTE).

← [Подзапросы и CTE](05-subqueries-and-cte.md) | [Оконные функции](07-window-functions.md) →

Подзапросы вкладывают один запрос в другой. Но иногда нужно просто **объединить результаты** двух независимых запросов: показать в одном списке и сотрудников, и клиентов, или найти общие значения между двумя наборами.

UNION (англ. «объединение»), INTERSECT (англ. «пересечение»), EXCEPT (англ. «исключение») объединяют результаты нескольких SELECT в один набор строк.

## UNION — объединение

UNION объединяет результаты двух запросов, **удаляя дубликаты**:

```sql
SELECT name FROM employees
UNION
SELECT name FROM customers;
```

```
 name
----------
 Alice
 Bob
 Charlie
 Анна
 Борис
 Вера
 Глеб
 Дина
 Евгений
```

Требования к UNION: оба SELECT должны возвращать **одинаковое количество столбцов**, и типы столбцов должны быть совместимы. Имена столбцов берутся из первого SELECT.

### UNION ALL — без удаления дубликатов

UNION ALL сохраняет все строки, включая дубликаты:

```sql
SELECT department_id FROM employees
UNION ALL
SELECT id FROM departments;
```

```
 department_id
--------------
             1
             2
             1
             2
             1
          NULL
             1
             2
             3
```

UNION ALL быстрее UNION, потому что не тратит ресурсы на дедупликацию. Если дубликаты не мешают или невозможны — используйте ALL.

## INTERSECT — пересечение

INTERSECT (англ. «пересечение») возвращает строки, присутствующие в **обоих** результатах:

```sql
SELECT department_id FROM employees WHERE salary > 80000
INTERSECT
SELECT department_id FROM employees WHERE hire_date >= '2021-01-01';
```

```
 department_id
--------------
             1
```

Сотрудники с зарплатой > 80000: отделы {1}. Нанятые после 2021: отделы {1, 2, NULL}. Пересечение: {1}.

INTERSECT ALL сохраняет дубликаты (по количеству совпадений).

## EXCEPT — разность

EXCEPT (англ. «исключение, кроме») возвращает строки из первого результата, **отсутствующие** во втором:

```sql
SELECT id FROM departments
EXCEPT
SELECT department_id FROM employees WHERE department_id IS NOT NULL;
```

```
 id
----
  3
```

Все отделы: {1, 2, 3}. Отделы с сотрудниками: {1, 2}. Разность: {3} — отдел `hr`.

EXCEPT ALL — с учётом количества вхождений.

## Порядок выполнения

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

Как и в DISTINCT, операции над множествами считают два NULL **одинаковыми**. UNION удалит дубликат из двух строк (NULL), INTERSECT их сопоставит, EXCEPT вычтет.

## Приоритет операций

INTERSECT имеет более высокий приоритет, чем UNION и EXCEPT:

```sql
A UNION B INTERSECT C
```

Выполняется как `A UNION (B INTERSECT C)`. Для другого порядка — скобки.

## Sources

- PostgreSQL Documentation (v16): UNION, INTERSECT, EXCEPT. <https://www.postgresql.org/docs/16/sql-select.html#SQL-UNION>

---

← [Подзапросы и CTE](05-subqueries-and-cte.md) | [Оконные функции](07-window-functions.md) →
