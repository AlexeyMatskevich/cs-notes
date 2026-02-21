# Выражения

**Предпосылки:** [типы данных и NULL](01-types-and-null.md) (типы, трёхзначная логика, IS NULL).

Выражение в SQL — любая конструкция, которая вычисляется в значение: арифметика (`salary * 1.1`), вызов функции (`length(name)`), условная логика (`CASE WHEN ...`). Выражения можно использовать в SELECT, WHERE, ORDER BY, HAVING — везде, где ожидается значение.

Три конструкции из этого файла — CASE, COALESCE и NULLIF — нужны повсюду в SQL, поэтому они вводятся здесь, до изучения запросов.

## CASE — условная логика

CASE (англ. «случай») — аналог `if/elsif/else` внутри SQL-выражения. У конструкции две формы.

**Searched CASE** — произвольные условия:

```sql
SELECT name, salary,
       CASE
           WHEN salary >= 85000 THEN 'высокая'
           WHEN salary >= 60000 THEN 'средняя'
           ELSE 'неизвестна'
       END AS level
FROM employees;
```

```
 name     | salary | level
----------+--------+-----------
 Анна     |  90000 | высокая
 Борис    |  60000 | средняя
 Вера     |  85000 | высокая
 Глеб     |  70000 | средняя
 Дина     |  NULL  | неизвестна
 Евгений  |  55000 | средняя
```

Условия проверяются сверху вниз. Первое совпавшее определяет результат. Если ни одно не совпало — срабатывает ELSE. Если ELSE отсутствует и ни одно условие не совпало — результат NULL.

У Дины `salary` — NULL. Сравнение `NULL >= 85000` возвращает NULL, `NULL >= 60000` — тоже NULL. Ни одно условие не дало TRUE, поэтому сработал ELSE.

**Simple CASE** — сравнение с конкретным значением:

```sql
SELECT name,
       CASE department_id
           WHEN 1 THEN 'engineering'
           WHEN 2 THEN 'sales'
           ELSE 'другой'
       END AS dept_name
FROM employees;
```

Simple CASE использует `=` для сравнения, поэтому `NULL` в `department_id` не совпадёт ни с одним WHEN — сработает ELSE. Это следствие трёхзначной логики: `NULL = 1` --> NULL, не TRUE.

## COALESCE — первое не-NULL значение

COALESCE (от лат. «срастись, слиться») принимает список аргументов и возвращает первый, который не NULL:

```sql
SELECT name, COALESCE(salary, 0) AS effective_salary
FROM employees;
```

```
 name     | effective_salary
----------+-----------------
 Анна     |           90000
 Борис    |           60000
 Вера     |           85000
 Глеб     |           70000
 Дина     |               0
 Евгений  |           55000
```

У Дины `salary` — NULL, поэтому COALESCE вернул второй аргумент — 0. У остальных `salary` не NULL, и COALESCE вернул его.

COALESCE можно вызывать с любым количеством аргументов: `COALESCE(a, b, c, d)` вернёт первый не-NULL слева направо. Если все NULL — результат NULL.

Типичные применения: замена NULL на значение по умолчанию в вычислениях, объединение данных из нескольких столбцов (`COALESCE(nickname, first_name, 'Anonymous')`).

## NULLIF — превращение значения в NULL

NULLIF (англ. «обнулить, если») — обратная операция к COALESCE. Принимает два аргумента: если они равны, возвращает NULL, иначе возвращает первый:

```sql
SELECT NULLIF(department_id, 0) FROM employees;
```

Если `department_id` равен 0 — результат NULL. Иначе — значение `department_id` как есть.

Применение: защита от деления на ноль. Выражение `total / NULLIF(count, 0)` вернёт NULL вместо ошибки, когда `count` равен нулю.

## CAST и приведение типов

SQL — строго типизированный язык, но иногда нужно явно преобразовать значение из одного типа в другой. Для этого есть CAST (англ. «привести, преобразовать»):

```sql
SELECT CAST('2024-01-15' AS date);
SELECT CAST(42 AS text);
```

В PostgreSQL есть короткая форма — оператор `::`:

```sql
SELECT '2024-01-15'::date;
SELECT 42::text;
```

Оператор `::` — специфика PostgreSQL, в стандартном SQL только CAST.

### Неявное приведение типов

PostgreSQL иногда приводит типы автоматически. Например, `salary > '70000'` сравнивает `integer` со строкой — PostgreSQL преобразует строку в число. Но полагаться на неявное приведение опасно: текстовое сравнение строк работает посимвольно (`'9' > '70000'` — TRUE, потому что `'9' > '7'`). Если оба операнда оказались строками, результат неожиданный.

Правило: числа пишутся без кавычек (`70000`), строки — в одинарных кавычках (`'текст'`). Даты — тоже в кавычках (`'2024-01-15'`), PostgreSQL автоматически приводит строку формата `YYYY-MM-DD` к типу `date`.

## Арифметика

Стандартные арифметические операторы: `+`, `-`, `*`, `/`, `%` (остаток от деления). Целочисленное деление — без дробной части: `7 / 2` = `3`. Для дробного результата хотя бы один операнд должен быть дробным: `7.0 / 2` = `3.5` или `7 / 2::numeric`.

Арифметика с NULL: любая операция с NULL даёт NULL. `salary * 1.1` при `salary = NULL` вернёт NULL. Для защиты используется COALESCE: `COALESCE(salary, 0) * 1.1`.

## Конкатенация строк

Оператор `||` склеивает строки:

```sql
SELECT name || ' (' || COALESCE(department_id::text, '?') || ')' AS label
FROM employees;
```

```
 label
-----------------
 Анна (1)
 Борис (2)
 Вера (1)
 Глеб (2)
 Дина (1)
 Евгений (?)
```

Конкатенация с NULL даёт NULL: `'hello' || NULL` --> NULL. Поэтому COALESCE часто нужен при построении строк.

## Функции для строк

`length(text)` — длина строки в символах. `upper(text)` / `lower(text)` — верхний/нижний регистр. `trim(text)` — удаление пробелов по краям. `substring(text FROM start FOR length)` — подстрока. `replace(text, from, to)` — замена подстроки.

```sql
SELECT upper(name), length(name) FROM employees WHERE id = 1;
```

```
 upper | length
-------+--------
 АННА  |      4
```

## Функции для дат

### CURRENT_DATE, CURRENT_TIMESTAMP, NOW()

`CURRENT_DATE` — текущая дата (тип `date`). `CURRENT_TIMESTAMP` / `NOW()` — текущая дата и время с часовым поясом:

```sql
SELECT CURRENT_DATE;        -- 2026-02-21
SELECT CURRENT_TIMESTAMP;   -- 2026-02-21 14:30:00+00
SELECT NOW();               -- то же, что CURRENT_TIMESTAMP
```

`CURRENT_DATE` и `CURRENT_TIMESTAMP` — стандарт SQL (без скобок). `NOW()` — расширение PostgreSQL.

Внутри одной транзакции `NOW()` возвращает **одно и то же значение** — момент начала транзакции. Если нужно время, которое меняется по ходу выполнения — `clock_timestamp()` (PostgreSQL).

### EXTRACT — извлечение компонентов даты

```sql
SELECT name, hire_date,
       EXTRACT(YEAR FROM hire_date) AS year,
       EXTRACT(MONTH FROM hire_date) AS month,
       EXTRACT(DOW FROM hire_date) AS day_of_week
FROM employees
WHERE id <= 3;
```

```
 name  | hire_date  | year | month | day_of_week
-------+------------+------+-------+------------
 Анна  | 2021-03-15 | 2021 |     3 |           1
 Борис | 2020-07-01 | 2020 |     7 |           3
 Вера  | 2022-01-10 | 2022 |     1 |           1
```

Доступные поля: YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, DOW (day of week, 0 = воскресенье), DOY (day of year), QUARTER, WEEK, EPOCH (секунды с 1970-01-01).

`EXTRACT` возвращает `numeric`, не `integer`. PostgreSQL поддерживает альтернативный синтаксис-функцию `date_part('year', hire_date)` — эквивалент EXTRACT.

### DATE_TRUNC — усечение до начала периода

`DATE_TRUNC(precision, timestamp)` обрезает дату до указанной точности — аналог округления вниз для дат:

```sql
SELECT DATE_TRUNC('month', TIMESTAMP '2025-03-15 14:30:00');
-- 2025-03-01 00:00:00

SELECT DATE_TRUNC('year', TIMESTAMP '2025-03-15 14:30:00');
-- 2025-01-01 00:00:00
```

Типичное применение — группировка по периодам:

```sql
SELECT DATE_TRUNC('month', hire_date) AS month, COUNT(*)
FROM employees
GROUP BY DATE_TRUNC('month', hire_date)
ORDER BY month;
```

```
 month      | count
------------+-------
 2019-11-01 |     1
 2020-07-01 |     1
 2021-03-01 |     1
 2022-01-01 |     1
 2023-06-01 |     1
 2024-02-01 |     1
```

Доступные точности: microseconds, milliseconds, second, minute, hour, day, week, month, quarter, year.

### AGE — разница между датами

`AGE(a, b)` возвращает интервал между двумя датами в человекочитаемом формате:

```sql
SELECT name, AGE(CURRENT_DATE, hire_date) AS tenure
FROM employees
WHERE id <= 3;
```

```
 name  | tenure
-------+------------------------
 Анна  | 4 years 11 mons 6 days
 Борис | 5 years 7 mons 20 days
 Вера  | 4 years 1 mon 11 days
```

С одним аргументом `AGE(date)` считает от CURRENT_DATE: `AGE(hire_date)` — то же, что `AGE(CURRENT_DATE, hire_date)`.

### INTERVAL — арифметика с датами

INTERVAL — тип данных, представляющий длительность. Складывается и вычитается с датами:

```sql
SELECT CURRENT_DATE + INTERVAL '3 months';   -- дата через 3 месяца
SELECT CURRENT_DATE - INTERVAL '30 days';    -- дата 30 дней назад

SELECT name, hire_date,
       hire_date + INTERVAL '90 days' AS probation_end
FROM employees
WHERE id <= 2;
```

```
 name  | hire_date  | probation_end
-------+------------+--------------
 Анна  | 2021-03-15 | 2021-06-13
 Борис | 2020-07-01 | 2020-09-29
```

Разница между двумя `date` возвращает **integer** (количество дней): `'2025-03-15'::date - '2025-01-01'::date` = 73. Разница между двумя `timestamp` возвращает **interval**.

## GREATEST и LEAST — min/max из списка значений

GREATEST и LEAST принимают несколько значений и возвращают наибольшее или наименьшее. В отличие от агрегатных MAX/MIN (работают по строкам), GREATEST/LEAST работают **по столбцам** одной строки:

```sql
SELECT name,
       GREATEST(salary, bonus, commission) AS best_income,
       LEAST(salary, bonus, commission) AS worst_income
FROM employees;
```

Поведение с NULL: в PostgreSQL GREATEST и LEAST **игнорируют NULL**, если есть хотя бы одно не-NULL значение:

```sql
SELECT GREATEST(10, NULL, 5);   -- 10
SELECT GREATEST(NULL, NULL);    -- NULL
SELECT LEAST(10, NULL, 5);      -- 5
```

Это PostgreSQL-специфика. В стандарте SQL и в некоторых СУБД (Oracle) любой NULL делает результат NULL.

Практический пример — ограничение значения (clamp):

```sql
SELECT name, LEAST(GREATEST(salary, 50000), 100000) AS clamped_salary
FROM employees
WHERE salary IS NOT NULL;
```

```
 name     | clamped_salary
----------+---------------
 Анна     |         90000
 Борис    |         60000
 Вера     |         85000
 Глеб     |         70000
 Евгений  |         55000
```

## Sources

- PostgreSQL Documentation (v16): Conditional Expressions (CASE, COALESCE, NULLIF). <https://www.postgresql.org/docs/16/functions-conditional.html>
- PostgreSQL Documentation (v16): Type Conversion. <https://www.postgresql.org/docs/16/typeconv.html>
- PostgreSQL Documentation (v16): String Functions, Date/Time Functions. <https://www.postgresql.org/docs/16/functions-string.html>, <https://www.postgresql.org/docs/16/functions-datetime.html>
