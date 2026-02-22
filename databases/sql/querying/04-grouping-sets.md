# Расширенная группировка

**Предпосылки:** [агрегация](02-aggregation.md) (GROUP BY, HAVING, агрегатные функции).

← [Соединения](03-joins.md) | [Подзапросы и CTE](05-subqueries-and-cte.md) →

GROUP BY даёт одноуровневые итоги: выручка по отделам или выручка по месяцам. Но аналитические отчёты часто требуют **подытогов по нескольким уровням**: выручка по отделам, по месяцам, по комбинации «отдел + месяц» и общий итог — в одном результате.

Без GROUPING SETS приходится писать несколько запросов и объединять через UNION ALL. GROUPING SETS, ROLLUP (англ. «свёртка вверх») и CUBE (англ. «куб») решают эту задачу одним запросом. Все три конструкции — расширения GROUP BY: они работают на том же [шаге 3 порядка выполнения](02-aggregation.md#полный-порядок-выполнения-запроса), но генерируют несколько уровней группировки за один проход.

## GROUPING SETS — явный набор группировок

```sql
SELECT department_id, extract(year FROM hire_date) AS year, COUNT(*), SUM(salary)
FROM employees
WHERE department_id IS NOT NULL AND salary IS NOT NULL
GROUP BY GROUPING SETS (
    (department_id, year),   -- по отделу и году
    (department_id),         -- по отделу (итог по всем годам)
    (year),                  -- по году (итог по всем отделам)
    ()                       -- общий итог
);
```

Каждый набор в скобках — отдельная группировка. SQL вычисляет агрегаты для каждой из них и объединяет результаты.

```
 department_id | year | count |  sum
---------------+------+-------+--------
             1 | 2021 |     1 |  90000
             1 | 2022 |     1 |  85000
             2 | 2019 |     1 |  70000
             2 | 2020 |     1 |  60000
             1 | NULL |     2 | 175000   <-- итог по отделу 1
             2 | NULL |     2 | 130000   <-- итог по отделу 2
          NULL | 2019 |     1 |  70000   <-- итог за 2019
          NULL | 2020 |     1 |  60000   <-- итог за 2020
          NULL | 2021 |     1 |  90000   <-- итог за 2021
          NULL | 2022 |     1 |  85000   <-- итог за 2022
          NULL | NULL |     4 | 305000   <-- общий итог
```

NULL в столбцах `department_id` и `year` означает «по всем значениям этого измерения». Но [NULL уже означает «значение неизвестно»](../foundations/01-types-and-null.md#null--отсутствие-значения) — как отличить итог от настоящего NULL в данных?

## GROUPING() — отличить итог от настоящего NULL

Функция GROUPING() (англ. «группирование») возвращает 1, если столбец участвует в подытоге (т.е. NULL означает «по всем»), и 0, если значение реальное:

```sql
SELECT department_id,
       GROUPING(department_id) AS is_dept_total,
       COUNT(*), SUM(salary)
FROM employees
WHERE department_id IS NOT NULL AND salary IS NOT NULL
GROUP BY GROUPING SETS ((department_id), ());
```

```
 department_id | is_dept_total | count |  sum
---------------+--------------+-------+--------
             1 |            0 |     2 | 175000
             2 |            0 |     2 | 130000
          NULL |            1 |     4 | 305000
```

Строка с `is_dept_total = 1` — общий итог. NULL в `department_id` — не отсутствующий отдел, а «по всем отделам».

## ROLLUP — иерархическая свёртка

ROLLUP (англ. «свёртка вверх») — сокращение для иерархических подытогов. Данные «сворачиваются» от детали к итогу:

```sql
GROUP BY ROLLUP (department_id, year)
```

эквивалентен:

```sql
GROUP BY GROUPING SETS (
    (department_id, year),   -- самый детальный уровень
    (department_id),         -- итог по отделу (свернули year)
    ()                       -- общий итог (свернули всё)
)
```

Визуально ROLLUP убирает столбцы справа налево:

```
(dept, year)   -- оба
(dept)         -- убрали year
()             -- убрали всё
```

Для N столбцов в ROLLUP — N+1 уровень группировки. ROLLUP подходит, когда столбцы образуют **иерархию**: страна > город > район, год > квартал > месяц.

## CUBE — все комбинации

CUBE (англ. «куб») генерирует **все возможные комбинации** столбцов группировки, как грани куба:

```sql
GROUP BY CUBE (department_id, year)
```

эквивалентен:

```sql
GROUP BY GROUPING SETS (
    (department_id, year),   -- оба
    (department_id),         -- только dept
    (year),                  -- только year
    ()                       -- ничего (общий итог)
)
```

Результат CUBE для тех же данных (department_id, year):

```
 department_id | year | count |  sum
---------------+------+-------+--------
             1 | 2021 |     1 |  90000   -- (dept, year)
             1 | 2022 |     1 |  85000
             2 | 2019 |     1 |  70000
             2 | 2020 |     1 |  60000
             1 | NULL |     2 | 175000   -- (dept)
             2 | NULL |     2 | 130000
          NULL | 2019 |     1 |  70000   -- (year)
          NULL | 2020 |     1 |  60000
          NULL | 2021 |     1 |  90000
          NULL | 2022 |     1 |  85000
          NULL | NULL |     4 | 305000   -- ()
```

Результат совпадает с GROUPING SETS из первого примера: CUBE для двух столбцов генерирует все 4 комбинации. Для 3 столбцов: 8 комбинаций (2³). CUBE быстро растёт — используйте осторожно.

Разница между ROLLUP и CUBE:

```
ROLLUP(a, b, c):  (a,b,c), (a,b), (a), ()        -- 4 набора, иерархия
CUBE(a, b, c):    (a,b,c), (a,b), (a,c), (b,c),   -- 8 наборов, все
                  (a), (b), (c), ()                  комбинации
```

GROUPING() доступна в SELECT (шаг 5) и HAVING (шаг 4) для различения подытогов и реальных NULL.

## Sources

- PostgreSQL Documentation (v16): GROUPING SETS, CUBE, ROLLUP. <https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-GROUPING-SETS>

---

← [Соединения](03-joins.md) | [Подзапросы и CTE](05-subqueries-and-cte.md) →
