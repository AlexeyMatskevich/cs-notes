# Агрегация

**Предпосылки:** [сортировка и ограничение](01-sorting-and-limiting.md) (ORDER BY, DISTINCT, pipeline FROM → WHERE → SELECT → ORDER BY → LIMIT).

← [Сортировка и ограничение](01-sorting-and-limiting.md) | [Соединения](03-joins.md) →

До сих пор каждая строка результата соответствовала одной строке таблицы. Менеджер начинает задавать вопросы другого рода — не про конкретных сотрудников, а про **отделы и компанию в целом**: «Сколько всего сотрудников?», «Какой фонд зарплаты?», «Средняя зарплата по отделам?». Ответ на такие вопросы требует **схлопнуть** набор строк в одно значение.

## Сколько сотрудников?

На таблице из 10000 строк считать вручную невозможно. Агрегатная функция (aggregate, англ. «совокупность») принимает набор строк и возвращает одно значение.

```sql
SELECT COUNT(*) FROM employees;
```

```
 count
-------
     6
```

`COUNT(*)` считает **все строки**, включая те, где есть NULL. `COUNT(salary)` — другой вопрос: считает строки, в которых `salary` не NULL:

```sql
SELECT COUNT(salary) FROM employees;
```

```
 count
-------
     5
```

У Дины зарплата неизвестна — она не посчитана. `COUNT(DISTINCT column)` считает уникальные не-NULL значения:

```sql
SELECT COUNT(DISTINCT department_id) FROM employees;
```

```
 count
-------
     2
```

Евгений (`NULL`) не посчитан, отделы 1 и 2 — посчитаны по разу.

## Фонд зарплаты и средняя

```sql
SELECT SUM(salary), AVG(salary), MIN(salary), MAX(salary)
FROM employees;
```

```
  sum   |  avg   |  min  |  max
--------+--------+-------+-------
 360000 |  72000 | 55000 | 90000
```

Все агрегатные функции **игнорируют NULL** (кроме `COUNT(*)`): [NULL означает «значение неизвестно»](../foundations/01-types-and-null.md#null--отсутствие-значения), и включать неизвестное в сумму бессмысленно. SUM сложил 90000+60000+85000+70000+55000 = 360000. AVG (от average, «среднее») поделил на 5, не на 6 — Дина пропущена. Это важно: если бы AVG делил на 6, средняя была бы 60000 вместо 72000.

### Агрегаты от пустого набора

```sql
SELECT SUM(salary) FROM employees WHERE id = 999;
```

```
 sum
------
 NULL
```

SUM от пустого набора — NULL, не ноль. COUNT — исключение: `COUNT(*)` и `COUNT(столбец)` от пустого набора возвращают 0.

## Всё это по отделам — GROUP BY

«Средняя зарплата по отделам» — одно число на всю компанию не подходит. Запустить три отдельных запроса (`WHERE department_id = 1`, `WHERE department_id = 2`, `WHERE department_id IS NULL`)? На 50 отделах не масштабируется.

GROUP BY (англ. «группировать по») разбивает строки на группы по значению столбца и применяет агрегат к каждой группе отдельно:

```sql
SELECT department_id, COUNT(*), AVG(salary)
FROM employees
GROUP BY department_id;
```

Что происходит внутри:

```
 id | name    | dept_id | salary          GROUP BY dept_id
----+---------+---------+--------
  1 | Анна    |    1    | 90000    -.     .- dept_id=1: Анна(90k), Вера(85k), Дина(NULL)
  2 | Борис   |    2    | 60000     |---->|- dept_id=2: Борис(60k), Глеб(70k)
  3 | Вера    |    1    | 85000    -'     '- dept_id=NULL: Евгений(55k)
  4 | Глеб    |    2    | 70000
  5 | Дина    |    1    |  NULL           Агрегат по каждой группе:
  6 | Евгений | NULL    | 55000           dept_id=1: COUNT=3, AVG=87500
                                          dept_id=2: COUNT=2, AVG=65000
                                          dept_id=NULL: COUNT=1, AVG=55000
```

Результат:

```
 department_id | count |  avg
---------------+-------+-------
             1 |     3 | 87500
             2 |     2 | 65000
          NULL |     1 | 55000
```

AVG для `department_id=1` = (90000 + 85000) / 2 = 87500. Дина (NULL) игнорируется — делим на 2, не на 3. NULL-значения `department_id` образуют **одну группу**, [аналогично DISTINCT](../foundations/01-types-and-null.md#null-в-разных-контекстах).

### Что можно писать в SELECT при GROUP BY

Попробуем добавить имя сотрудника:

```sql
SELECT department_id, name, COUNT(*)  -- ОШИБКА
FROM employees
GROUP BY department_id;
```

PostgreSQL откажет: `name` не в GROUP BY и не в агрегатной функции. В группе `department_id=1` три имени (Анна, Вера, Дина) — какое показать? PostgreSQL не может выбрать за вас. Правило: при GROUP BY в SELECT допустимы **только** столбцы из GROUP BY и агрегатные функции.

Причина — порядок выполнения. GROUP BY (шаг 3) стоит между WHERE и SELECT:

```
1. FROM         -- берём строки
2. WHERE        -- фильтруем строки
3. GROUP BY     -- схлопываем в группы, вычисляем агрегаты
4. SELECT       -- вычисляем выражения
5. DISTINCT     -- дедупликация
6. ORDER BY     -- сортируем
7. LIMIT/OFFSET -- обрезаем
```

На момент SELECT строки уже сгруппированы — поэтому SELECT видит только ключи группировки и результаты агрегатов.

## Отделы с высокой средней — HAVING

«Покажи только отделы, где средняя зарплата больше 70000». Попробуем `WHERE AVG(salary) > 70000` — ошибка: `aggregate functions are not allowed in WHERE`. Почему? WHERE выполняется на шаге 2 и фильтрует строки по одной, а AVG(salary) требует группу строк для вычисления — на этом шаге групп ещё не существует.

HAVING (англ. «имеющий») фильтрует **группы** после GROUP BY:

```sql
SELECT department_id, AVG(salary)
FROM employees
WHERE hire_date >= '2020-01-01'
GROUP BY department_id
HAVING AVG(salary) > 70000;
```

```
1. FROM -- все 6 строк
2. WHERE hire_date >= '2020-01-01' -- отсекаем Глеба (2019)
3. GROUP BY department_id:
     1:    Анна(90000), Вера(85000), Дина(NULL)
     2:    Борис(60000)
     NULL: Евгений(55000)
4. HAVING AVG(salary) > 70000:
     1: (90000+85000)/2 = 87500 > 70000 --> TRUE
     2: 60000 > 70000 --> FALSE
     NULL: 55000 > 70000 --> FALSE
5. SELECT
```

```
 department_id |  avg
---------------+-------
             1 | 87500
```

HAVING может использовать агрегатные функции, отличные от тех, что в SELECT: можно выбирать `AVG(salary)`, а фильтровать по `COUNT(*) > 2`.

### Полный порядок выполнения запроса

HAVING вставляется между GROUP BY и SELECT — фильтрация групп происходит сразу после их формирования:

```
1. FROM         -- берём строки
2. WHERE        -- фильтруем строки (до группировки)
3. GROUP BY     -- разбиваем на группы, вычисляем агрегаты
4. HAVING       -- фильтруем группы (после группировки)
5. SELECT       -- вычисляем выражения
6. DISTINCT     -- дедупликация
7. ORDER BY     -- сортируем
8. LIMIT/OFFSET -- обрезаем
```

Это полный порядок выполнения SELECT-запроса — в следующих файлах мы будем ссылаться на конкретные шаги.

Видимость псевдонимов расширяется: псевдоним столбца из SELECT нельзя использовать ни в GROUP BY (стандарт SQL), ни в HAVING — оба выполняются до SELECT. PostgreSQL в отличие от стандарта **разрешает** псевдоним в GROUP BY — это расширение, в стандартном SQL не гарантировано.

<details>
<summary>Задача: отделы, в которых больше одного сотрудника с зарплатой выше 60000</summary>

**Частая ошибка:**
```sql
SELECT department_id FROM employees
WHERE salary > 60000 AND COUNT(*) > 1
GROUP BY department_id;
```
WHERE работает до GROUP BY — агрегат `COUNT(*)` здесь невозможен.

**Правильный вариант:**
```sql
SELECT department_id FROM employees
WHERE salary > 60000
GROUP BY department_id
HAVING COUNT(*) > 1;
```
WHERE фильтрует строки до группировки (оставляет зарплаты > 60000). HAVING фильтрует уже сформированные группы (оставляет группы с > 1 сотрудника).

</details>

## Сколько высокооплачиваемых в каждом отделе — FILTER

«Для каждого отдела покажи общее количество и количество с зарплатой > 70000». Первый способ — через CASE внутри COUNT:

```sql
SELECT department_id,
       COUNT(*) AS total,
       COUNT(CASE WHEN salary > 70000 THEN 1 END) AS high_salary
FROM employees
GROUP BY department_id;
```

CASE возвращает 1 для подходящих строк и NULL для остальных. COUNT игнорирует NULL — посчитаны только подходящие. Работает, но громоздко.

FILTER (англ. «фильтр», стандарт SQL:2003) делает то же лаконичнее:

```sql
SELECT department_id,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE salary > 70000) AS high_salary
FROM employees
GROUP BY department_id;
```

```
 department_id | total | high_salary
---------------+-------+------------
             1 |     3 |           2
             2 |     2 |           0
          NULL |     1 |           0
```

`COUNT(*) FILTER (WHERE salary > 70000)` считает только строки, где зарплата выше 70000. Разница с CASE: FILTER читается как естественный фильтр, а не как workaround через условную логику.

FILTER — не отдельный шаг pipeline, а модификатор агрегатной функции: для каждой строки он проверяет условие и пропускает в агрегат только подходящие. Поэтому FILTER запускается на том же шаге, что и сам агрегат: с обычными агрегатами — на шаге 3 (GROUP BY), с [оконными агрегатами](07-window-functions.md) — на шаге 5 (SELECT). С чисто оконными функциями (ROW_NUMBER, RANK) FILTER **не работает**.

## Имена через запятую — string_agg

«Покажи в отчёте одну строку на отдел с именами сотрудников через запятую». `string_agg` (string + aggregate, «собрать строки в одну») объединяет значения в строку через разделитель:

```sql
SELECT department_id, string_agg(name, ', ' ORDER BY name)
FROM employees
WHERE department_id IS NOT NULL
GROUP BY department_id;
```

```
 department_id | string_agg
---------------+-------------------
             1 | Анна, Вера, Дина
             2 | Борис, Глеб
```

## JSON для API — jsonb_agg

Если результат нужен не для отчёта, а для API — `jsonb_agg` (JSONB + aggregate) собирает значения в JSON-массив: `jsonb_agg(name)` --> `["Анна", "Вера", "Дина"]`.

`array_agg` (array + aggregate) собирает значения в массив PostgreSQL:

```sql
SELECT department_id, array_agg(name ORDER BY name)
FROM employees
WHERE department_id IS NOT NULL
GROUP BY department_id;
```

```
 department_id |    array_agg
---------------+-------------------
             1 | {Анна,Вера,Дина}
             2 | {Борис,Глеб}
```

`array_agg` входит в стандарт SQL:2008, `string_agg` аналогичен стандартной функции `LISTAGG` (SQL:2016). `jsonb_agg` — расширение PostgreSQL.

## Классификация агрегатных функций

```
Агрегатные функции:
  COUNT, SUM, AVG, MIN, MAX, string_agg, array_agg, jsonb_agg, ...

  Режим 1: обычный агрегат (с GROUP BY, шаг 3 pipeline)
  Режим 2: оконный агрегат (с OVER, шаг 5 pipeline)

  FILTER работает в обоих режимах — и с GROUP BY, и с OVER.
```

Подробнее о режиме 2 и чисто оконных функциях — в [оконных функциях](07-window-functions.md). В PostgreSQL при больших объёмах данных агрегация может не поместиться в память — подробнее в [memory и spill](../../postgresql/query-processing/04-memory-and-spill.md).

## Sources

- PostgreSQL Documentation (v16): Aggregate Functions. <https://www.postgresql.org/docs/16/functions-aggregate.html>
- PostgreSQL Documentation (v16): GROUP BY, HAVING. <https://www.postgresql.org/docs/16/sql-select.html>

---

← [Сортировка и ограничение](01-sorting-and-limiting.md) | [Соединения](03-joins.md) →
