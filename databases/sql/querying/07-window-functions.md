# Оконные функции

**Предпосылки:** [агрегация](02-aggregation.md) (агрегатные функции, GROUP BY), [соединения](03-joins.md) (JOIN).

← [Операции над множествами](06-set-operations.md) | [Таблицы и типы](../schema/00-tables-and-types.md) →

Все предыдущие инструменты либо оставляют строки как есть (SELECT, WHERE, JOIN), либо схлопывают их в группы (GROUP BY). Оконные функции решают задачу, которая раньше была невозможна: вычислить агрегат **без потери строк**.

Задача: «для каждого сотрудника показать его зарплату и среднюю зарплату по отделу». С GROUP BY средняя вычисляется, но строки схлопываются — имена теряются. Нужен инструмент, который добавит вычисленное значение к каждой строке.

## OVER — оконная функция

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

Пять строк на входе — пять строк на выходе. Но к каждой строке добавлен `dept_avg` — средняя по её отделу.

## PARTITION BY — разделение на секции

PARTITION BY (англ. «разделить по») делит данные на секции (как GROUP BY делит на группы), но строки внутри секции **сохраняются**:

```sql
AVG(salary) OVER (PARTITION BY department_id)
```

Без PARTITION BY функция работает по **всем строкам** результата:

```sql
AVG(salary) OVER ()
```

## ORDER BY в OVER — порядок внутри секции

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

`SUM(salary) OVER (ORDER BY salary)` — нарастающий итог (running total): для каждой строки суммируются все предыдущие строки по порядку salary.

## Функции ранжирования

Ранжирование — присвоение номера каждой строке внутри секции. Три функции отличаются обработкой одинаковых значений (ties):

```sql
SELECT name, department_id, salary,
       ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC NULLS LAST) AS rn,
       RANK()       OVER (PARTITION BY department_id ORDER BY salary DESC NULLS LAST) AS rnk,
       DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC NULLS LAST) AS drnk
FROM employees
WHERE salary IS NOT NULL;
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

ROW_NUMBER() — уникальный последовательный номер. При ties порядок произволен.

RANK() — ранг с пропусками. Если две строки на 1-м месте, следующая получит 3.

DENSE_RANK() — ранг без пропусков. Если две строки на 1-м месте, следующая получит 2.

### NTILE — разбиение на равные группы

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

## Навигационные функции

Доступ к значениям других строк внутри секции:

**LAG/LEAD** — значение предыдущей/следующей строки:

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

**FIRST_VALUE / LAST_VALUE / NTH_VALUE** — значение первой/последней/N-й строки в фрейме:

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

## Фреймы

Фрейм (frame, англ. «рамка») определяет, какие строки «видит» оконная функция. По умолчанию при наличии ORDER BY в OVER фрейм — `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` (от начала секции до текущей строки).

Два типа фреймов:

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

### Ловушка LAST_VALUE

Фрейм по умолчанию (при наличии ORDER BY) — `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Фрейм расширяется по мере чтения: для первой строки это 1–1, для второй 1–2, для третьей 1–3. Первая строка **всегда** внутри, последняя строка секции — только когда до неё дошли.

FIRST_VALUE безопасен: первая строка всегда в фрейме. LAST_VALUE с дефолтным фреймом возвращает **текущую строку**, а не последнюю в секции:

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

Каждая строка показывает саму себя. Для «настоящей» последней строки нужен явный фрейм на всю секцию:

```sql
LAST_VALUE(name) OVER (
    PARTITION BY department_id
    ORDER BY salary DESC
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
)
```

На практике `FIRST_VALUE` с обратной сортировкой предпочтительнее — не нужно помнить про фрейм. NTH_VALUE подвержен той же ловушке, что и LAST_VALUE.

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

## NULL в оконных функциях

NULL при ORDER BY внутри OVER влияет на порядок и фреймы. При RANGE NULL-значения группируются вместе (как в обычной сортировке). LAG/LEAD через NULL возвращают NULL без специальной обработки.

## Sources

- PostgreSQL Documentation (v16): Window Functions. <https://www.postgresql.org/docs/16/tutorial-window.html>
- PostgreSQL Documentation (v16): Window Function Calls. <https://www.postgresql.org/docs/16/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS>

---

← [Операции над множествами](06-set-operations.md) | [Таблицы и типы](../schema/00-tables-and-types.md) →
