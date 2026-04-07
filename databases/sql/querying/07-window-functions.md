# Оконные функции

<details>
<summary>Предпосылки</summary>

[агрегация](02-aggregation.md) (агрегатные функции, GROUP BY), [соединения](03-joins.md) (JOIN), [подзапросы и CTE](05-subqueries-and-cte.md) (коррелированные подзапросы, CTE).

</details>

← [Операции над множествами](06-set-operations.md) | [Таблицы и типы](../schema/00-tables-and-types.md) →

## Зарплата рядом со средней по отделу

Задача: «для каждого сотрудника показать его зарплату и среднюю зарплату по отделу». С GROUP BY средняя вычисляется, но строки схлопываются — имена теряются. Нужен инструмент, который добавит вычисленное значение к каждой строке, не уничтожая их.

## OVER — вычисление без потери строк

OVER (англ. «поверх, над») превращает агрегатную функцию в **оконную** — такую, которая смотрит на данные через **окно** (window): ограниченный набор строк, видимый для вычисления. Функция смотрит «поверх» этих строк, не схлопывая их:

```sql
SELECT name, department_id, salary,
       AVG(salary) OVER (PARTITION BY department_id) AS dept_avg
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | department_id | salary | dept_avg
----------+---------------+--------+---------
 Анна     |             1 |  90000 |   87500
 Вера     |             1 |  85000 |   87500
 Борис    |             2 |  60000 |   65000
 Глеб     |             2 |  70000 |   65000
 Евгений  |          NULL |  55000 |   55000
```

Пять строк на входе — пять строк на выходе. Но к каждой добавлен `dept_avg` — средняя по её отделу. Контраст с GROUP BY наглядный:

```
GROUP BY department_id:             OVER (PARTITION BY department_id):

 dept_id |  avg                     name    | dept_id | salary | dept_avg
---------+-------                   --------+---------+--------+---------
       1 | 87500     строки         Анна    |       1 |  90000 |   87500
       2 | 65000     схлопнуты      Вера    |       1 |  85000 |   87500
    NULL | 55000                    Борис   |       2 |  60000 |   65000
                                    Глеб    |       2 |  70000 |   65000
  3 строки                          Евгений |    NULL |  55000 |   55000

                                   5 строк — все на месте
```

PARTITION BY (англ. «разделить по») делит данные на секции (как GROUP BY делит на группы), но строки внутри секции **сохраняются**. Без PARTITION BY функция работает по **всем строкам** результата: `AVG(salary) OVER ()`.

В примере выше окно для Анны — две строки отдела 1 (Анна и Вера), для Бориса — две строки отдела 2 (Борис и Глеб). PARTITION BY определяет границы окна; пока оно совпадает с целой секцией.

## Нарастающий итог — ORDER BY в OVER

ORDER BY внутри OVER задаёт порядок обработки строк **внутри секции**:

```sql
SELECT name, salary,
       SUM(salary) OVER (ORDER BY salary) AS running_total
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | salary | running_total
----------+--------+--------------
 Евгений  |  55000 |        55000
 Борис    |  60000 |       115000
 Глеб     |  70000 |       185000
 Вера     |  85000 |       270000
 Анна     |  90000 |       360000
```

Для каждой строки суммируются все предыдущие строки по порядку salary — нарастающий итог (running total). ORDER BY сузил окно: теперь функция видит не всю секцию, а строки от начала до текущей позиции.

Без оконных функций нарастающий итог потребовал бы коррелированного подзапроса: `SELECT ..., (SELECT SUM(salary) FROM employees e2 WHERE e2.salary <= e1.salary) FROM employees e1`. `SUM(...) OVER (ORDER BY salary)` заменяет это одной строкой.

## Позиция по зарплате в отделе — ROW_NUMBER

«Кто первый по зарплате в отделе?» ROW_NUMBER() присваивает уникальный последовательный номер каждой строке внутри секции:

```sql
SELECT name, department_id, salary,
       ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC NULLS LAST) AS rn
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | department_id | salary | rn
----------+---------------+--------+----
 Анна     |             1 |  90000 |  1
 Вера     |             1 |  85000 |  2
 Глеб     |             2 |  70000 |  1
 Борис    |             2 |  60000 |  2
 Евгений  |          NULL |  55000 |  1
```

## Ничья — RANK vs DENSE_RANK

Если два сотрудника получают одинаковую зарплату, ROW_NUMBER всё равно присвоит разные номера (порядок произволен). Для задач, где ничьи важны, есть RANK (англ. «ранг, место в рейтинге») и DENSE_RANK (англ. «плотный ранг» — без пропусков):

```sql
SELECT name, department_id, salary,
       ROW_NUMBER() OVER w AS rn,
       RANK()       OVER w AS rnk,
       DENSE_RANK() OVER w AS drnk
FROM employees
WHERE salary IS NOT NULL
WINDOW w AS (PARTITION BY department_id ORDER BY salary DESC NULLS LAST);
```

```
 name     | department_id | salary | rn | rnk | drnk
----------+---------------+--------+----+-----+------
 Анна     |             1 |  90000 |  1 |   1 |    1
 Вера     |             1 |  85000 |  2 |   2 |    2
 Глеб     |             2 |  70000 |  1 |   1 |    1
 Борис    |             2 |  60000 |  2 |   2 |    2
 Евгений  |          NULL |  55000 |  1 |   1 |    1
```

RANK() — ранг с пропусками: если две строки на 1-м месте, следующая получит 3. DENSE_RANK() — ранг без пропусков: если две строки на 1-м месте, следующая получит 2. Разница проявляется только при одинаковых значениях ORDER BY.

## Терцили для compensation review — NTILE

Терцили (от лат. *tertius* — «третий») — деление на три равные части: верхняя, средняя, нижняя треть. NTILE(n) (англ. «n-tile», «n-ая часть») делит строки на n примерно равных групп — при n = 3 это и есть терцили:

```sql
SELECT name, salary,
       NTILE(3) OVER (ORDER BY salary DESC NULLS LAST) AS tercile
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | salary | tercile
----------+--------+--------
 Анна     |  90000 |       1
 Вера     |  85000 |       1
 Глеб     |  70000 |       2
 Борис    |  60000 |       2
 Евгений  |  55000 |       3
```

## Изменение зарплаты vs предыдущий найм — LAG, LEAD

Доступ к значениям других строк внутри секции. LAG (англ. «отставание») — значение предыдущей строки, LEAD (англ. «опережение») — следующей:

```sql
SELECT name, salary,
       LAG(salary) OVER (ORDER BY salary) AS prev_salary,
       LEAD(salary) OVER (ORDER BY salary) AS next_salary
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | salary | prev_salary | next_salary
----------+--------+------------+------------
 Евгений  |  55000 |       NULL |      60000
 Борис    |  60000 |      55000 |      70000
 Глеб     |  70000 |      60000 |      85000
 Вера     |  85000 |      70000 |      90000
 Анна     |  90000 |      85000 |       NULL
```

LAG(salary, 2) — значение через две строки назад. LAG(salary, 1, 0) — с дефолтным значением 0 вместо NULL.

Без LAG пришлось бы нумеровать строки подзапросом и соединять таблицу саму с собой по номеру строки ± 1 — громоздкий self-join вместо одного вызова функции.

## Топ-зарплата отдела рядом с каждым — FIRST_VALUE

Задача: показать рядом с каждым сотрудником имя того, кто зарабатывает в отделе больше всех. Без оконных функций это решается через подзапрос с MAX и два JOIN:

```sql
SELECT e.name, e.department_id, e.salary, top.name AS top_earner
FROM employees e
JOIN (
    SELECT department_id, MAX(salary) AS max_sal
    FROM employees
    WHERE salary IS NOT NULL
    GROUP BY department_id
) ms ON e.department_id = ms.department_id
JOIN employees top
    ON top.department_id = ms.department_id AND top.salary = ms.max_sal
WHERE e.salary IS NOT NULL AND e.department_id IS NOT NULL;
```

Два JOIN и подзапрос. FIRST_VALUE делает то же одним проходом:

```sql
SELECT name, department_id, salary,
       FIRST_VALUE(name) OVER (
           PARTITION BY department_id
           ORDER BY salary DESC NULLS LAST
       ) AS top_earner
FROM employees
WHERE salary IS NOT NULL AND department_id IS NOT NULL;
```

```
 name  | department_id | salary | top_earner
-------+---------------+--------+-----------
 Анна  |             1 |  90000 | Анна
 Вера  |             1 |  85000 | Анна
 Глеб  |             2 |  70000 | Глеб
 Борис |             2 |  60000 | Глеб
```

### Ловушка LAST_VALUE

Попробуем получить сотрудника с **наименьшей** зарплатой в отделе через LAST_VALUE:

```sql
SELECT name, department_id, salary,
       LAST_VALUE(name) OVER (
           PARTITION BY department_id ORDER BY salary DESC
       ) AS bottom_earner
FROM employees
WHERE salary IS NOT NULL;
```

```
 name  | department_id | salary | bottom_earner
-------+---------------+--------+--------------
 Анна  |             1 |  90000 | Анна
 Вера  |             1 |  85000 | Вера
 Глеб  |             2 |  70000 | Глеб
 Борис |             2 |  60000 | Борис
```

Каждая строка показывает саму себя! Причина: фрейм по умолчанию (при наличии ORDER BY) — `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Фрейм расширяется по мере чтения — LAST_VALUE видит только строки от начала до текущей позиции.

Для «настоящей» последней строки нужен явный фрейм на всю секцию:

```sql
LAST_VALUE(name) OVER (
    PARTITION BY department_id
    ORDER BY salary DESC
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
)
```

На практике `FIRST_VALUE` с обратной сортировкой предпочтительнее — не нужно помнить про фрейм.

## Фреймы

До сих пор окно определялось неявно — через PARTITION BY и ORDER BY. Фрейм (frame, англ. «рамка») задаёт его границы явно: какие именно строки из секции функция видит для каждой текущей строки. Два типа:

**ROWS** — физические строки. **RANGE** — логический диапазон значений. При одинаковых значениях (ties) результаты различаются.

Границы фрейма:

```
UNBOUNDED PRECEDING  -- от начала секции
N PRECEDING          -- N строк/значений назад
CURRENT ROW          -- текущая строка/значение
N FOLLOWING          -- N строк/значений вперёд
UNBOUNDED FOLLOWING  -- до конца секции
```

### ROWS vs RANGE: разница при дубликатах

Когда все значения ORDER BY уникальны, ROWS и RANGE дают одинаковый результат. Разница видна при дубликатах. Два сотрудника с одинаковой датой найма:

```
 name     | hire_date  | salary
----------+------------+--------
 Глеб     | 2019-11-20 |  70000
 Борис    | 2020-07-01 |  60000
 Анна     | 2021-03-15 |  90000
 Вера     | 2021-03-15 |  85000   <-- та же дата
 Евгений  | 2024-02-01 |  55000
```

```sql
SELECT name, hire_date, salary,
       SUM(salary) OVER (ORDER BY hire_date
           RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS range_sum,
       SUM(salary) OVER (ORDER BY hire_date
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS rows_sum
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | hire_date  | salary | range_sum | rows_sum
----------+------------+--------+-----------+---------
 Глеб     | 2019-11-20 |  70000 |     70000 |   70000
 Борис    | 2020-07-01 |  60000 |    130000 |  130000
 Анна     | 2021-03-15 |  90000 |    305000 |  220000
 Вера     | 2021-03-15 |  85000 |    305000 |  305000
 Евгений  | 2024-02-01 |  55000 |    360000 |  360000
```

RANGE считает Анну и Веру «одной позицией» (одна дата) — обе видят сумму, включающую обеих (305000). ROWS считает физические строки по одной: Анна видит только свои 220000, Вера — 305000 с учётом Анны.

## Именованные окна

Если несколько функций используют одинаковый OVER, можно вынести определение:

```sql
SELECT name, salary,
       ROW_NUMBER() OVER w AS rn,
       SUM(salary) OVER w AS running_total
FROM employees
WHERE salary IS NOT NULL
WINDOW w AS (ORDER BY salary);
```

## FILTER с оконными агрегатами

FILTER (описан в [агрегации](02-aggregation.md)) работает и с оконными агрегатами:

```sql
SELECT name, department_id, salary,
       COUNT(*) FILTER (WHERE salary >= 70000)
           OVER (PARTITION BY department_id) AS high_earners_in_dept
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | department_id | salary | high_earners_in_dept
----------+---------------+--------+---------------------
 Анна     |             1 |  90000 |                   2
 Вера     |             1 |  85000 |                   2
 Борис    |             2 |  60000 |                   1
 Глеб     |             2 |  70000 |                   1
 Евгений  |          NULL |  55000 |                   0
```

FILTER с чисто оконными функциями (ROW_NUMBER, RANK, LAG, LEAD) **не работает** — только с агрегатными функциями в оконном режиме.

## Первая строка в группе — ROW_NUMBER + CTE

Каноническая задача: «самый высокооплачиваемый в каждом отделе **с именем**». GROUP BY вычислит MAX(salary), но имя потеряется — в группе несколько имён, и PostgreSQL не знает, какое вернуть.

Стандартное решение — ROW_NUMBER + CTE:

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

```
 name     | department_id | salary
----------+---------------+--------
 Анна     |             1 |  90000
 Глеб     |             2 |  70000
 Евгений  |          NULL |  55000
```

CTE `ranked` нумерует строки внутри каждого отдела по зарплате. Внешний запрос оставляет только первые. Для top-N достаточно изменить условие на `rn <= N`. Этот подход работает в любой СУБД, поддерживающей оконные функции.

В PostgreSQL top-1 в группе решается короче — [DISTINCT ON](../postgresql/08-distinct-on.md). Альтернативный подход к top-N через коррелированный подзапрос в FROM — [LATERAL](05-subqueries-and-cte.md#lateral--подзапрос-с-доступом-к-внешним-строкам).

## Классификация оконных функций

```
Агрегатные (с OVER): COUNT, SUM, AVG, MIN, MAX, string_agg, ...
  Работают и как обычные агрегаты (с GROUP BY), и как оконные (с OVER).
  FILTER работает в обоих режимах.

Чисто оконные: ROW_NUMBER, RANK, DENSE_RANK, NTILE,
               LAG, LEAD, FIRST_VALUE, LAST_VALUE, NTH_VALUE
  Только с OVER. Без OVER -- синтаксическая ошибка.
  FILTER с чисто оконными НЕ работает.
```

## Pipeline: оконные функции на шаге 5

Оконные функции выполняются **после GROUP BY и HAVING**, но в рамках шага SELECT:

```
1. FROM + JOIN     -- источник строк
2. WHERE           -- фильтрация строк
3. GROUP BY        -- группировка, обычные агрегаты
4. HAVING          -- фильтрация групп
5. SELECT          -- вычисление выражений, ОКОННЫЕ ФУНКЦИИ здесь
6. DISTINCT        -- дедупликация
7. ORDER BY        -- сортировка
8. LIMIT/OFFSET    -- обрезка
```

Следствия:
- Оконные функции **нельзя** использовать в WHERE и HAVING — они ещё не вычислены.
- Для фильтрации по результату оконной функции — подзапрос или CTE.
- Оконные функции видят данные **после GROUP BY**: если был GROUP BY, строки уже сгруппированы.

<details>
<summary>Задача: наименьшая зарплата отдела рядом с каждым сотрудником</summary>

**Частая ошибка:**
```sql
SELECT name, department_id, salary,
       LAST_VALUE(salary) OVER (
           PARTITION BY department_id ORDER BY salary DESC
       ) AS min_salary
FROM employees WHERE salary IS NOT NULL;
```
LAST_VALUE с дефолтным фреймом возвращает текущую строку, а не последнюю в секции.

**Правильный вариант:**
```sql
SELECT name, department_id, salary,
       FIRST_VALUE(salary) OVER (
           PARTITION BY department_id ORDER BY salary ASC
       ) AS min_salary
FROM employees WHERE salary IS NOT NULL;
```
FIRST_VALUE с сортировкой по возрастанию — первая строка всегда в фрейме.

</details>

## NULL в оконных функциях

NULL при ORDER BY внутри OVER влияет на порядок и фреймы. При RANGE NULL-значения группируются вместе (как в обычной сортировке). LAG/LEAD через NULL возвращают NULL без специальной обработки.

В PostgreSQL оконные функции с большими секциями потребляют значительную память — подробнее в [memory и spill](../../postgresql/query-processing/04-memory-and-spill.md).

## Sources

- PostgreSQL Documentation (v16): Window Functions. <https://www.postgresql.org/docs/16/tutorial-window.html>
- PostgreSQL Documentation (v16): Window Function Calls. <https://www.postgresql.org/docs/16/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS>

---

← [Операции над множествами](06-set-operations.md) | [Таблицы и типы](../schema/00-tables-and-types.md) →
