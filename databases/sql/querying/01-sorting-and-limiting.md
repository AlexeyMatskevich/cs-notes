# Сортировка и ограничение

**Предпосылки:** [SELECT и фильтрация](00-select-and-filtering.md) (SELECT, FROM, WHERE, логический порядок выполнения).

Результат запроса — неупорядоченная коллекция строк. Порядок вывода без ORDER BY произволен и может меняться. Для управления порядком и объёмом результата SQL предоставляет ORDER BY, LIMIT/OFFSET и DISTINCT.

## ORDER BY — явный порядок

ORDER BY (англ. «упорядочить по») сортирует результат:

```sql
SELECT name, salary
FROM employees
WHERE department_id = 1
ORDER BY salary;
```

```
 name | salary
------+--------
 Вера |  85000
 Анна |  90000
 Дина |  NULL
```

По умолчанию сортировка **по возрастанию** — ASC (от ascending, «восходящий»). Для убывания — DESC (descending, «нисходящий»):

```sql
SELECT name, salary
FROM employees
WHERE department_id = 1
ORDER BY salary DESC;
```

```
 name | salary
------+--------
 Дина |  NULL
 Анна |  90000
 Вера |  85000
```

### NULL при сортировке

NULL при сортировке в PostgreSQL ведёт себя **как если бы был наибольшим значением**: при ASC — в конце, при DESC — в начале. Это конвенция PostgreSQL, не математическое свойство NULL. Поведение можно переопределить:

```sql
ORDER BY salary DESC NULLS LAST
```

Это поставит NULL в конец даже при убывающей сортировке.

### Сортировка по нескольким столбцам

```sql
SELECT name, department_id, salary
FROM employees
ORDER BY department_id, salary DESC;
```

Сначала по отделу (по возрастанию), внутри каждого отдела — по зарплате (по убыванию).

### Псевдонимы в ORDER BY

ORDER BY выполняется **после** SELECT, поэтому может использовать псевдонимы:

```sql
SELECT name, salary * 12 AS annual
FROM employees
ORDER BY annual DESC NULLS LAST;
```

Это работает, потому что к моменту сортировки столбец `annual` уже вычислен.

## Обновлённый pipeline

```
1. FROM       -- берём строки
2. WHERE      -- фильтруем
3. SELECT     -- выбираем столбцы, вычисляем выражения
4. ORDER BY   -- сортируем результат
```

## Видимость псевдонимов

Псевдонимы из SELECT видны не во всех секциях запроса. Причина — логический порядок выполнения: SELECT вычисляется позже, чем WHERE и GROUP BY.

| Псевдоним | WHERE | GROUP BY | HAVING | SELECT | ORDER BY |
|---|---|---|---|---|---|
| Столбца (SELECT ... AS x) | нет | нет* | нет | да | да |
| Таблицы (FROM t AS x) | да | да | да | да | да |
| CTE (WITH x AS ...) | да | да | да | да | да |

\* PostgreSQL в отличие от стандарта SQL **разрешает** использовать псевдоним столбца в GROUP BY. Это расширение PostgreSQL — в MySQL тоже работает, но в стандартном SQL не гарантировано.

Если нужно использовать вычисленное выражение в WHERE — придётся повторить его: `WHERE salary * 12 > 500000`, а не `WHERE annual > 500000`.

## LIMIT и OFFSET — ограничение результата

LIMIT (англ. «предел, ограничение») обрезает результат до указанного числа строк:

```sql
SELECT name, salary
FROM employees
ORDER BY salary DESC NULLS LAST
LIMIT 3;
```

```
 name | salary
------+--------
 Анна |  90000
 Вера |  85000
 Глеб |  70000
```

**LIMIT без ORDER BY почти всегда бессмыслен**: без сортировки нет гарантии, какие именно строки попадут в результат.

OFFSET (англ. «смещение») пропускает указанное число строк:

```sql
SELECT name, salary
FROM employees
ORDER BY salary DESC NULLS LAST
LIMIT 2 OFFSET 2;
```

```
 name     | salary
----------+--------
 Глеб     |  70000
 Борис    |  60000
```

OFFSET 2 пропустил Анну и Веру, LIMIT 2 взял следующие две.

LIMIT/OFFSET часто используется для **пагинации**: страница 1 — `LIMIT 10 OFFSET 0`, страница 2 — `LIMIT 10 OFFSET 10`. Но у этого подхода проблема: чтобы показать страницу 1000, PostgreSQL отсортирует все строки и пропустит 9990. Чем больше OFFSET, тем дороже запрос. Для больших таблиц существует keyset pagination — см. [пагинация](../../postgresql/query-processing/07-pagination.md).

## Обновлённый pipeline

```
1. FROM       -- берём строки
2. WHERE      -- фильтруем
3. SELECT     -- выбираем столбцы
4. ORDER BY   -- сортируем
5. LIMIT/OFFSET -- обрезаем
```

## DISTINCT — удаление дубликатов

DISTINCT (англ. «различный, уникальный») убирает дубликаты из результата:

```sql
SELECT DISTINCT department_id
FROM employees;
```

```
 department_id
--------------
             1
             2
          NULL
```

Три уникальных значения: 1, 2 и NULL. Даже если в таблице несколько строк с `department_id = 1`, DISTINCT оставит одну.

DISTINCT стоит ресурсов — PostgreSQL сравнивает строки через сортировку или хеш-таблицу. Не ставьте DISTINCT «на всякий случай».

### NULL в DISTINCT

DISTINCT считает два NULL **одинаковыми** (дубликатами). Это отличается от поведения `=`, где `NULL = NULL` даёт NULL. DISTINCT использует специальный механизм «IS NOT DISTINCT FROM».

```sql
SELECT DISTINCT salary
FROM employees
ORDER BY salary NULLS LAST;
```

```
 salary
--------
  55000
  60000
  70000
  85000
  90000
   NULL
```

NULL ровно один раз, даже если в таблице несколько строк с неизвестной зарплатой.

### DISTINCT в pipeline

DISTINCT выполняется после SELECT, но до ORDER BY:

```
1. FROM       -- берём строки
2. WHERE      -- фильтруем
3. SELECT     -- выбираем столбцы
4. DISTINCT   -- дедупликация
5. ORDER BY   -- сортируем
6. LIMIT/OFFSET -- обрезаем
```

## DISTINCT ON — первая строка в каждой группе (PostgreSQL)

В PostgreSQL DISTINCT ON выбирает одну строку для каждого уникального значения указанного выражения:

```sql
SELECT DISTINCT ON (department_id) department_id, name, salary
FROM employees
ORDER BY department_id, salary DESC NULLS LAST;
```

```
 department_id | name     | salary
---------------+----------+--------
             1 | Анна     |  90000
             2 | Глеб     |  70000
          NULL | Евгений  |  55000
```

Для каждого `department_id` выбрана первая строка по ORDER BY (самая высокая зарплата). DISTINCT ON — специфика PostgreSQL, в стандартном SQL аналогичный результат достигается через оконные функции.

Требование: выражение в DISTINCT ON должно быть в начале ORDER BY — иначе какая строка «первая» неопределена.

## Sources

- PostgreSQL Documentation (v16): ORDER BY, LIMIT, DISTINCT. <https://www.postgresql.org/docs/16/sql-select.html>
- PostgreSQL Documentation (v16): DISTINCT ON. <https://www.postgresql.org/docs/16/sql-select.html#SQL-DISTINCT>
