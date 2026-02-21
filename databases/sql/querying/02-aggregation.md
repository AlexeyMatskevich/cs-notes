# Агрегация

**Предпосылки:** [сортировка и ограничение](01-sorting-and-limiting.md) (ORDER BY, DISTINCT, pipeline FROM → WHERE → SELECT → ORDER BY → LIMIT).

До сих пор каждая строка результата соответствовала одной строке таблицы. Но вопрос «сколько всего сотрудников?» или «какая средняя зарплата по отделам?» требует **схлопнуть** набор строк в одно значение. Для этого нужны агрегатные функции и GROUP BY.

## Агрегатные функции

Слово «агрегат» (aggregate, англ. «совокупность») означает: функция принимает набор строк и возвращает одно значение.

### COUNT — подсчёт

```sql
SELECT COUNT(*) FROM employees;
```

```
 count
-------
     6
```

`COUNT(*)` считает **все строки**, включая те, где есть NULL.

```sql
SELECT COUNT(salary) FROM employees;
```

```
 count
-------
     5
```

`COUNT(salary)` считает строки, в которых `salary` не NULL. У Дины зарплата неизвестна — она не посчитана.

`COUNT(DISTINCT column)` считает уникальные не-NULL значения:

```sql
SELECT COUNT(DISTINCT department_id) FROM employees;
```

```
 count
-------
     2
```

Евгений (`NULL`) не посчитан, отделы 1 и 2 — посчитаны по разу.

### SUM, AVG, MIN, MAX

```sql
SELECT SUM(salary), AVG(salary), MIN(salary), MAX(salary)
FROM employees;
```

```
  sum   |  avg   |  min  |  max
--------+--------+-------+-------
 360000 |  72000 | 55000 | 90000
```

Все агрегатные функции **игнорируют NULL** (кроме `COUNT(*)`). SUM сложил 90000+60000+85000+70000+55000 = 360000. AVG поделил на 5, не на 6, потому что Дина пропущена.

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

## GROUP BY — агрегация по группам

GROUP BY (англ. «группировать по») разбивает строки на группы по значению столбца и применяет агрегатную функцию к каждой группе отдельно:

```sql
SELECT department_id, COUNT(*), AVG(salary)
FROM employees
GROUP BY department_id;
```

Пошагово:

```
1. FROM employees -- все 6 строк
2. GROUP BY department_id -- три группы:
     department_id=1:    Анна(90000), Вера(85000), Дина(NULL)
     department_id=2:    Борис(60000), Глеб(70000)
     department_id=NULL: Евгений(55000)
3. SELECT -- для каждой группы вычисляем агрегаты
```

```
 department_id | count |  avg
---------------+-------+-------
             1 |     3 | 87500
             2 |     2 | 65000
          NULL |     1 | 55000
```

AVG для `department_id=1` = (90000 + 85000) / 2 = 87500. Дина (NULL) игнорируется — делим на 2, не на 3.

### NULL в GROUP BY

NULL-значения образуют **одну группу**, аналогично DISTINCT. Евгений с `department_id = NULL` попал в отдельную группу.

### Правило SELECT при GROUP BY

При GROUP BY в SELECT допустимы только: столбцы из GROUP BY и агрегатные функции. Ничего больше.

```sql
SELECT department_id, name, COUNT(*)  -- ОШИБКА
FROM employees
GROUP BY department_id;
```

PostgreSQL откажет: `name` не в GROUP BY и не в агрегатной функции. В группе `department_id=1` три имени (Анна, Вера, Дина) — какое показать? PostgreSQL не может выбрать за вас.

## Обновлённый pipeline

```
1. FROM       -- берём строки
2. WHERE      -- фильтруем строки (до группировки)
3. GROUP BY   -- разбиваем на группы, агрегатные функции на шаге 3
4. HAVING     -- фильтруем группы (после группировки)
5. SELECT     -- вычисляем выражения
6. DISTINCT   -- дедупликация
7. ORDER BY   -- сортируем
8. LIMIT/OFFSET -- обрезаем
```

Нельзя/можно:
- В WHERE **нельзя** использовать агрегатные функции — групп ещё не существует.
- Псевдоним из SELECT **нельзя** использовать в WHERE и HAVING — SELECT выполняется позже.
- В ORDER BY **можно** использовать псевдоним из SELECT.

## HAVING — фильтрация групп

HAVING (англ. «имеющий») фильтрует **группы** после GROUP BY. WHERE фильтрует строки до группировки, HAVING — группы после.

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

## FILTER — фильтрация внутри агрегата

FILTER (англ. «фильтр») ограничивает, какие строки попадают в конкретный агрегат. В PostgreSQL (и стандарте SQL:2003):

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

`COUNT(*) FILTER (WHERE salary > 70000)` считает только строки, где зарплата выше 70000. Это чище, чем эквивалент через CASE: `COUNT(CASE WHEN salary > 70000 THEN 1 END)`.

FILTER работает в двух режимах: с обычными агрегатами (GROUP BY, шаг 3 pipeline) и с оконными агрегатами (OVER, шаг 5). С чисто оконными функциями (ROW_NUMBER, RANK) FILTER **не работает**.

## string_agg и array_agg

`string_agg(expression, delimiter)` собирает значения в строку через разделитель:

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

`jsonb_agg(expression)` собирает значения в JSON-массив: `jsonb_agg(name)` --> `["Анна", "Вера", "Дина"]`. Удобен для API, где результат отдаётся как JSON.

`array_agg(expression)` собирает значения в массив PostgreSQL:

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

Все три коллектора (string_agg, array_agg, jsonb_agg) — расширения PostgreSQL.

## Классификация агрегатных функций

```
Агрегатные функции:
  COUNT, SUM, AVG, MIN, MAX, string_agg, array_agg, jsonb_agg, ...

  Режим 1: обычный агрегат (с GROUP BY, шаг 3 pipeline)
  Режим 2: оконный агрегат (с OVER, шаг 5 pipeline)

  FILTER работает в обоих режимах — и с GROUP BY, и с OVER.
```

Подробнее о режиме 2 и чисто оконных функциях — в [оконных функциях](07-window-functions.md).

## Sources

- PostgreSQL Documentation (v16): Aggregate Functions. <https://www.postgresql.org/docs/16/functions-aggregate.html>
- PostgreSQL Documentation (v16): GROUP BY, HAVING. <https://www.postgresql.org/docs/16/sql-select.html>
