---
tags:
  - domain/sql
  - theme/data-representation
  - type/concept
aliases:
  - CASE
  - COALESCE
  - NULLIF
  - CAST
  - Expressions
order: 2
---

# Выражения

**Предпосылки:** [типы данных и NULL](types-and-null.md) (типы, трёхзначная логика, IS NULL).

← [Типы данных и NULL](types-and-null.md) | [SELECT и фильтрация](../querying/select-and-filtering.md) →

Выражение в SQL — любая конструкция, которая вычисляется в значение: арифметика (`salary * 1.1`), вызов функции (`length(name)`), условная логика (`CASE WHEN ...`). Выражения можно использовать в SELECT, WHERE, ORDER BY — везде, где ожидается значение.

Представим: HR-отдел готовит квартальный отчёт по сотрудникам. Каждая колонка отчёта требует вычислений — классификация, обработка пропусков, форматирование, работа с датами. Отчёт строится на знакомой таблице `employees`:

```
 id | name     | department_id | salary | hire_date
----+----------+---------------+--------+------------
  1 | Анна     |             1 |  90000 | 2021-03-15
  2 | Борис    |             2 |  60000 | 2020-07-01
  3 | Вера     |             1 |  85000 | 2022-01-10
  4 | Глеб     |             2 |  70000 | 2019-11-20
  5 | Дина     |             1 |  NULL  | 2023-06-01
  6 | Евгений  |          NULL |  55000 | 2024-02-01
```

## Классификация зарплат — CASE

Первая колонка отчёта: категория зарплаты — «высокая», «средняя», «неизвестна». Нет готовой функции, которая превращает число в категорию — нужна условная логика.

CASE (англ. «случай») — аналог `if/elsif/else` внутри SQL-выражения. Две формы.

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
 Евгений  |  55000 | неизвестна
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

## Бонус с неизвестной зарплатой — COALESCE

Вторая колонка: расчётный бонус 10% от зарплаты. Для Дины `salary * 0.1` даёт NULL — бонус неизвестен. В отчёте нужно 0 вместо пустого значения.

COALESCE (от лат. «срастись, слиться») принимает список аргументов и возвращает первый, который не NULL:

```sql
SELECT name, COALESCE(salary, 0) * 0.1 AS bonus
FROM employees;
```

```
 name     | bonus
----------+-------
 Анна     |  9000
 Борис    |  6000
 Вера     |  8500
 Глеб     |  7000
 Дина     |     0
 Евгений  |  5500
```

COALESCE можно вызывать с любым количеством аргументов: `COALESCE(a, b, c, d)` вернёт первый не-NULL слева направо. Если все NULL — результат NULL. Типичное применение помимо расчётов — объединение данных из нескольких столбцов: `COALESCE(nickname, first_name, 'Anonymous')`.

## Выручка на сотрудника — NULLIF

Третья колонка: выручка отдела / количество сотрудников. Если отдел пуст (нет сотрудников), деление на ноль вызовет ошибку.

NULLIF (англ. «обнулить, если») — обратная операция к COALESCE. Принимает два аргумента: если они равны, возвращает NULL, иначе возвращает первый:

```sql
SELECT NULLIF(department_id, 0) FROM employees;
```

Применение для защиты от деления на ноль: `total / NULLIF(count, 0)` вернёт NULL вместо ошибки, когда `count` равен нулю.

## Метка сотрудника — конкатенация строк

Четвёртая колонка: метка вида `Анна (1)`, где число — id отдела. У Евгения отдела нет — нужна обработка NULL.

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

Конкатенация с NULL даёт NULL: `'hello' || NULL` --> NULL. Поэтому COALESCE часто нужен при построении строк. Запись `department_id::text` — приведение типов, о котором ниже.

## Приведение типов — CAST

В метке выше `department_id` — число, а `||` ожидает строки. Нужно явное преобразование.

SQL — строго типизированный язык. CAST (англ. «привести, преобразовать») выполняет явное приведение:

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

## Стаж в отчёте — арифметика с датами

Пятая колонка: стаж сотрудника. Нужно вычислить, сколько времени прошло с даты найма.

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

### EXTRACT — извлечение компонентов даты

Стаж в годах — это не строка `4 years 11 mons`, а число. EXTRACT (англ. «извлечь») достаёт компонент из даты или интервала:

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

## Наймы по кварталам — DATE_TRUNC

Шестая колонка: количество наймов по кварталам (для отчёта). Нужно «округлить» дату найма до начала квартала.

`DATE_TRUNC(precision, timestamp)` обрезает дату до указанной точности — аналог округления вниз для дат:

```sql
SELECT DATE_TRUNC('month', TIMESTAMP '2025-03-15 14:30:00');
-- 2025-03-01 00:00:00

SELECT DATE_TRUNC('year', TIMESTAMP '2025-03-15 14:30:00');
-- 2025-01-01 00:00:00
```

Применение к таблице сотрудников — увидеть, в каком квартале каждый был нанят:

```sql
SELECT name, hire_date,
       DATE_TRUNC('quarter', hire_date) AS quarter_start
FROM employees;
```

```
 name     | hire_date  | quarter_start
----------+------------+--------------
 Анна     | 2021-03-15 | 2021-01-01
 Борис    | 2020-07-01 | 2020-07-01
 Вера     | 2022-01-10 | 2022-01-01
 Глеб     | 2019-11-20 | 2019-10-01
 Дина     | 2023-06-01 | 2023-04-01
 Евгений  | 2024-02-01 | 2024-01-01
```

DATE_TRUNC часто используется вместе с [GROUP BY](../querying/aggregation.md) для подсчёта по периодам — это рассмотрено в [агрегации](../querying/aggregation.md).

Доступные точности: microseconds, milliseconds, second, minute, hour, day, week, month, quarter, year.

### CURRENT_DATE, CURRENT_TIMESTAMP, NOW()

`CURRENT_DATE` — текущая дата (тип `date`). `CURRENT_TIMESTAMP` / `NOW()` — текущая дата и время с часовым поясом:

```sql
SELECT CURRENT_DATE;        -- 2026-02-21
SELECT CURRENT_TIMESTAMP;   -- 2026-02-21 14:30:00+00
SELECT NOW();               -- то же, что CURRENT_TIMESTAMP
```

`CURRENT_DATE` и `CURRENT_TIMESTAMP` — стандарт SQL (без скобок). `NOW()` — расширение PostgreSQL.

Внутри одной транзакции `NOW()` возвращает **одно и то же значение** — момент начала транзакции. Если нужно время, которое меняется по ходу выполнения — `clock_timestamp()` (PostgreSQL).

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

Помимо прибавления интервала, с датами работает и обратная операция — вычитание. Тип результата зависит от типов операндов:

```sql
-- date - date = integer (количество дней)
SELECT '2025-03-15'::date - '2025-01-01'::date;  -- 73

-- timestamp - timestamp = interval
SELECT '2025-03-15 14:00'::timestamp - '2025-03-01 09:30'::timestamp;
-- 14 days 04:30:00

-- date + integer = date (дата через N дней)
SELECT '2025-01-01'::date + 30;  -- 2025-01-31

-- date - integer = date (дата N дней назад)
SELECT '2025-03-15'::date - 7;   -- 2025-03-08
```

Практический пример — сколько дней каждый сотрудник работает в компании:

```sql
SELECT name, CURRENT_DATE - hire_date AS days_employed
FROM employees
WHERE id <= 3;
```

```
 name  | days_employed
-------+--------------
 Анна  |         1804
 Борис |         2061
 Вера  |          1466
```

Интервалы можно умножать и делить — это удобно для расчёта пропорций:

```sql
SELECT INTERVAL '1 day' * 365.25 AS year_approx;  -- 365 days 06:00:00
SELECT INTERVAL '8 hours' / 2;                     -- 04:00:00
SELECT INTERVAL '1 hour' * 3 + INTERVAL '30 minutes';  -- 03:30:00
```

Ключевое различие: `date - date` возвращает `integer` (целое число дней), а `timestamp - timestamp` возвращает `interval` (который включает часы, минуты, секунды). Если нужно получить дробное число дней из интервала, извлекают эпоху: `EXTRACT(EPOCH FROM interval) / 86400`.

## Зарплата в диапазоне — GREATEST и LEAST

Последняя колонка: зарплата, ограниченная диапазоном 50000–100000 для внешнего отчёта. Нужно «обрезать» значения снизу и сверху.

GREATEST и LEAST принимают несколько значений и возвращают наибольшее или наименьшее. В отличие от агрегатных MAX/MIN (работают по строкам), GREATEST/LEAST работают **по столбцам** одной строки:

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

Поведение с NULL: в PostgreSQL GREATEST и LEAST **игнорируют NULL**, если есть хотя бы одно не-NULL значение:

```sql
SELECT GREATEST(10, NULL, 5);   -- 10
SELECT GREATEST(NULL, NULL);    -- NULL
SELECT LEAST(10, NULL, 5);      -- 5
```

Это PostgreSQL-специфика. В стандарте SQL и в некоторых СУБД (Oracle) любой NULL делает результат NULL.

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

## Sources

- PostgreSQL Documentation (v16): Conditional Expressions (CASE, COALESCE, NULLIF). <https://www.postgresql.org/docs/16/functions-conditional.html>
- PostgreSQL Documentation (v16): Type Conversion. <https://www.postgresql.org/docs/16/typeconv.html>
- PostgreSQL Documentation (v16): String Functions, Date/Time Functions. <https://www.postgresql.org/docs/16/functions-string.html>, <https://www.postgresql.org/docs/16/functions-datetime.html>

---

← [Типы данных и NULL](types-and-null.md) | [SELECT и фильтрация](../querying/select-and-filtering.md) →
