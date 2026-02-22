# Оконные функции

<details>
<summary>Предпосылки</summary>

[агрегация](02-aggregation.md) (агрегатные функции, GROUP BY), [соединения](03-joins.md) (JOIN), [подзапросы и CTE](05-subqueries-and-cte.md) (коррелированные подзапросы, CTE).

</details>

← [Операции над множествами](06-set-operations.md) | [Пагинация](08-pagination.md) →

## Зарплата рядом со средней по отделу

Задача: «для каждого сотрудника показать его зарплату и среднюю зарплату по отделу». С GROUP BY средняя вычисляется, но строки схлопываются — имена теряются. Нужен инструмент, который добавит вычисленное значение к каждой строке, не уничтожая их.

## OVER — вычисление без потери строк

OVER (англ. «поверх, над») превращает агрегатную функцию в оконную. Функция смотрит «поверх» набора строк, не схлопывая их:

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

Для каждой строки суммируются все предыдущие строки по порядку salary — нарастающий итог (running total).

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

NTILE(n) (англ. «n-ая часть, плитка») делит строки на n примерно равных групп:

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

## Топ-зарплата отдела рядом с каждым — FIRST_VALUE

FIRST_VALUE возвращает значение первой строки в фрейме:

```sql
SELECT name, department_id, salary,
       FIRST_VALUE(name) OVER (
           PARTITION BY department_id
           ORDER BY salary DESC NULLS LAST
       ) AS top_earner
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | department_id | salary | top_earner
----------+---------------+--------+-----------
 Анна     |             1 |  90000 | Анна
 Вера     |             1 |  85000 | Анна
 Глеб     |             2 |  70000 | Глеб
 Борис    |             2 |  60000 | Глеб
 Евгений  |          NULL |  55000 | Евгений
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

Фрейм (frame, англ. «рамка») определяет, какие строки «видит» оконная функция. Два типа:

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

## Первая строка в группе — ROW_NUMBER + CTE → DISTINCT ON

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

CTE `ranked` нумерует строки внутри каждого отдела по зарплате. Внешний запрос оставляет только первые. Этот подход работает в любой СУБД, поддерживающей оконные функции.

### DISTINCT ON — PostgreSQL-shortcut

В PostgreSQL ту же задачу решает DISTINCT ON:

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

Для каждого уникального `department_id` DISTINCT ON выбирает первую строку по ORDER BY. Требование: выражение в DISTINCT ON должно быть в начале ORDER BY.

Когда что:
- **ROW_NUMBER + CTE** — стандарт SQL, гибкий: легко получить top-2 или top-N (`WHERE rn <= N`), работает в любой СУБД.
- **DISTINCT ON** — PostgreSQL-специфика, компактнее для top-1. Для top-N не подходит.

## Top-N в группе — LATERAL

«Покажи топ-2 по зарплате **в каждом** отделе». DISTINCT ON не подходит — он берёт только top-1. ROW_NUMBER + CTE работает (`WHERE rn <= 2`). Но есть ещё один подход — LATERAL.

LATERAL (англ. «боковой») позволяет подзапросу в FROM ссылаться на столбцы предшествующих таблиц — как вложенный цикл, где для каждой строки внешней таблицы выполняется подзапрос:

```sql
SELECT d.name AS dept, top.employee_name, top.salary
FROM departments d
LEFT JOIN LATERAL (
    SELECT e.name AS employee_name, e.salary
    FROM employees e
    WHERE e.department_id = d.id
    ORDER BY e.salary DESC NULLS LAST
    LIMIT 2
) top ON true;
```

```
 dept        | employee_name | salary
-------------+---------------+--------
 engineering | Анна          |  90000
 engineering | Вера          |  85000
 sales       | Глеб          |  70000
 sales       | Борис         |  60000
 hr          | NULL          |   NULL
```

Для каждого отдела подзапрос выбирает двух лучших по зарплате. LATERAL ссылается на `d.id` из внешней таблицы — без LATERAL это было бы ошибкой. LEFT JOIN LATERAL сохраняет `hr`, у которого нет сотрудников. Это коррелированный подзапрос в FROM — по сути тот же механизм, что в [подзапросах](05-subqueries-and-cte.md), но здесь подзапрос порождает набор строк, а не одно значение.

LATERAL незаменим там, где нужно **порождать строки** из значения каждой строки: развернуть массив, вызвать `generate_series`, передать параметр в табличную функцию.

### Три подхода к «первая/лучшая строка в группе»

| Подход | Top-1 | Top-N | Стандарт SQL | Компактность |
|---|---|---|---|---|
| ROW_NUMBER + CTE | да | да | да | средняя |
| DISTINCT ON | да | нет | нет (PG) | высокая |
| LATERAL | да | да | да* | средняя |

\* LATERAL — стандарт SQL:1999, но не все СУБД его поддерживают.

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

## Sources

- PostgreSQL Documentation (v16): Window Functions. <https://www.postgresql.org/docs/16/tutorial-window.html>
- PostgreSQL Documentation (v16): Window Function Calls. <https://www.postgresql.org/docs/16/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS>
- PostgreSQL Documentation (v16): DISTINCT ON. <https://www.postgresql.org/docs/16/sql-select.html#SQL-DISTINCT>
- PostgreSQL Documentation (v16): LATERAL. <https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-LATERAL>

---

← [Операции над множествами](06-set-operations.md) | [Пагинация](08-pagination.md) →
