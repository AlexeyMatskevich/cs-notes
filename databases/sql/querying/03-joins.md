# Соединения (JOIN)

**Предпосылки:** [агрегация](02-aggregation.md) (GROUP BY, HAVING, pipeline до шага 8).

← [Агрегация](02-aggregation.md) | [Расширенная группировка](04-grouping-sets.md) →

Все предыдущие запросы работали с одной таблицей. Но в реальных базах данные **разделены** по нескольким таблицам: сотрудники — отдельно, отделы — отдельно. Это [следствие нормализации](../foundations/00-relational-model.md#плоская-таблица-и-её-проблемы), устраняющей аномалии плоской таблицы. Связь между ними — через общее значение (ключ). JOIN (англ. «соединение, объединение») комбинирует строки из разных таблиц.

Две таблицы:

```
departments:
 id | name        | budget
----+-------------+--------
  1 | engineering | 500000
  2 | sales       | 300000
  3 | hr          | 150000

employees:
 id | name     | department_id | salary | hire_date
----+----------+---------------+--------+------------
  1 | Анна     |             1 |  90000 | 2021-03-15
  2 | Борис    |             2 |  60000 | 2020-07-01
  3 | Вера     |             1 |  85000 | 2022-01-10
  4 | Глеб     |             2 |  70000 | 2019-11-20
  5 | Дина     |             1 |  NULL  | 2023-06-01
  6 | Евгений  |          NULL |  55000 | 2024-02-01
```

Отдел `hr` не имеет сотрудников. Евгений не привязан к отделу (`department_id = NULL`).

## Псевдонимы таблиц

При работе с несколькими таблицами удобно давать им короткие имена. Псевдоним (alias) задаётся после имени таблицы в FROM:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
JOIN departments d ON e.department_id = d.id;
```

`e` — псевдоним для `employees`, `d` — для `departments`. Ключевое слово AS для табличных псевдонимов **необязательно**: `FROM employees AS e` и `FROM employees e` эквивалентны. Псевдонимы обязательны при self-join, где одна таблица используется дважды.

## CROSS JOIN — декартово произведение

Самый простой способ скомбинировать две таблицы — взять каждую строку первой и приклеить к каждой строке второй. 6 сотрудников x 3 отдела = 18 строк:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e CROSS JOIN departments d;
```

Большинство из 18 комбинаций бессмысленны — Анна соединена с каждым отделом, хотя работает только в engineering. CROSS JOIN важен как **концепция**: декартово произведение — одна из семи операций [реляционной алгебры](../foundations/00-relational-model.md#реляционная-алгебра), и все остальные JOIN — это CROSS JOIN плюс фильтрация.

## INNER JOIN — осмысленное соединение

INNER JOIN (или просто JOIN) оставляет только строки, для которых условие ON вернуло TRUE:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
JOIN departments d ON e.department_id = d.id;
```

```
 name  | dept_name
-------+-------------
 Анна  | engineering
 Борис | sales
 Вера  | engineering
 Глеб  | sales
 Дина  | engineering
```

Кого здесь нет? **Евгения** — его `department_id` = NULL, и `NULL = 1`, `NULL = 2`, `NULL = 3` дают NULL. Ни одна комбинация не TRUE. **Отдела hr** — ни один сотрудник не имеет `department_id = 3`. INNER JOIN возвращает только строки с парой в обеих таблицах.

## LEFT JOIN — сохранение строк из левой таблицы

LEFT JOIN (полное название — LEFT OUTER JOIN) гарантирует, что **все строки левой таблицы** попадут в результат. Если пара не нашлась — столбцы правой таблицы заполняются NULL:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id;
```

```
 name     | dept_name
----------+-------------
 Анна     | engineering
 Борис    | sales
 Вера     | engineering
 Глеб     | sales
 Дина     | engineering
 Евгений  | NULL
```

Евгений вернулся — его отдел неизвестен, пары нет, но LEFT JOIN сохранил его. Столбцы из `departments` заполнены NULL.

Отдел `hr` по-прежнему отсутствует — он из правой таблицы, а LEFT JOIN защищает только левую.

## RIGHT JOIN и FULL OUTER JOIN

RIGHT JOIN — зеркало LEFT JOIN: сохраняет все строки правой таблицы. На практике используется редко — любой RIGHT JOIN можно переписать как LEFT JOIN, поменяв таблицы местами.

FULL OUTER JOIN — сохраняет все строки из обеих таблиц:

```sql
SELECT e.name, d.name AS dept_name
FROM employees e
FULL OUTER JOIN departments d ON e.department_id = d.id;
```

```
 name     | dept_name
----------+-------------
 Анна     | engineering
 Борис    | sales
 Вера     | engineering
 Глеб     | sales
 Дина     | engineering
 Евгений  | NULL
 NULL     | hr
```

И Евгений, и `hr` в результате.

Прогрессия идёт от вопроса «что делать со строками без пары?»: INNER JOIN отбрасывает их, LEFT JOIN сохраняет из левой таблицы (заполняя правую NULL-ами), RIGHT JOIN — зеркально из правой, а FULL OUTER JOIN сохраняет все строки из обеих таблиц.

## Паттерн «найти сирот»

LEFT JOIN + WHERE ... IS NULL — способ найти строки без пары:

```sql
SELECT d.name
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id
WHERE e.id IS NULL;
```

```
 name
------
 hr
```

LEFT JOIN сохраняет все отделы. Для `hr` столбцы `employees` — NULL. Фильтр `WHERE e.id IS NULL` оставляет только такие строки.

## Self-join — таблица соединяется сама с собой

Иногда нужно сравнить строки **внутри одной таблицы**. Пример: пары сотрудников из одного отдела:

```sql
SELECT e1.name, e2.name, e1.department_id
FROM employees e1
JOIN employees e2 ON e1.department_id = e2.department_id
WHERE e1.id < e2.id;
```

```
 name  | name | department_id
-------+------+--------------
 Анна  | Вера |            1
 Анна  | Дина |            1
 Вера  | Дина |            1
 Борис | Глеб |            2
```

Чтобы понять роль `e1.id < e2.id`, уберём это условие и посмотрим, что выдаёт один только JOIN. Условие ON `e1.department_id = e2.department_id` соединяет каждого сотрудника отдела с каждым сотрудником того же отдела — включая самого себя. Для отдела engineering (Анна id=1, Вера id=3, Дина id=5) получается 3 × 3 = 9 строк:

```
 e1.id | e1.name | e2.id | e2.name | department_id
-------+---------+-------+---------+--------------
     1 | Анна    |     1 | Анна    |            1   -- самопара
     1 | Анна    |     3 | Вера    |            1
     1 | Анна    |     5 | Дина    |            1
     3 | Вера    |     1 | Анна    |            1   -- зеркало строки выше
     3 | Вера    |     3 | Вера    |            1   -- самопара
     3 | Вера    |     5 | Дина    |            1
     5 | Дина    |     1 | Анна    |            1   -- зеркало
     5 | Дина    |     3 | Вера    |            1   -- зеркало
     5 | Дина    |     5 | Дина    |            1   -- самопара
```

Здесь две проблемы. **Самопары** — строки, где сотрудник соединён сам с собой (Анна–Анна, Вера–Вера, Дина–Дина). **Зеркальные дубликаты** — пара Анна–Вера присутствует дважды: (e1=Анна, e2=Вера) и (e1=Вера, e2=Анна). Для задачи «пары коллег» это одна и та же пара.

`WHERE e1.id < e2.id` решает обе проблемы одним условием. Самопары отсекаются, потому что `id` никогда не меньше самого себя (1 < 1 — FALSE). Из каждой зеркальной пары выживает только та, где меньший id стоит слева: (Анна id=1, Вера id=3) проходит (1 < 3), а (Вера id=3, Анна id=1) — нет (3 < 1 — FALSE). Из 9 строк остаётся 3: Анна–Вера, Анна–Дина, Вера–Дина.

Альтернативы: `e1.id <> e2.id` убрала бы самопары, но оставила зеркала. `e1.id <= e2.id` — оставила бы самопары. Именно строгое неравенство `<` отсекает оба класса лишних строк.

**Евгений** не попал в результат ни в одной паре. Его `department_id = NULL`, а в условии ON стоит `e1.department_id = e2.department_id`. Когда хотя бы одна сторона — NULL, оператор `=` возвращает NULL (не TRUE и не FALSE). Поскольку INNER JOIN оставляет строки только при TRUE, Евгений не соединяется ни с кем — даже сам с собой, потому что `NULL = NULL` — тоже NULL.

## ON vs WHERE при LEFT JOIN

При INNER JOIN условие в ON и в WHERE взаимозаменяемы — оптимизатор строит одинаковый план. При LEFT JOIN — **нет**:

```sql
-- Вариант A: условие в ON
SELECT e.name, d.name AS dept_name
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id AND d.budget > 200000;

-- Вариант B: условие в WHERE
SELECT e.name, d.name AS dept_name
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
WHERE d.budget > 200000;
```

Вариант A: ON не нашёл пару для Дины (engineering, budget=500000, пара есть) — а для `hr` нет сотрудника. Но если бы `budget` не проходил условие, LEFT JOIN подставил бы NULL. Все сотрудники остаются в результате.

Вариант B: LEFT JOIN подставил данные отделов, потом WHERE отсеивает строки, где `d.budget` NULL или <= 200000. Евгений (dept NULL) и сотрудники отделов с малым бюджетом **исчезают** — LEFT JOIN фактически превращается в INNER JOIN.

Правило: при LEFT JOIN условия на правую таблицу ставятся **в ON**, а не в WHERE, если нужно сохранить строки левой таблицы.

Это следствие [порядка выполнения](02-aggregation.md#полный-порядок-выполнения-запроса): ON выполняется на шаге 1 вместе с FROM, а WHERE — на шаге 2, когда LEFT JOIN уже подставил NULL-строки.

## USING — когда столбцы совпадают по имени

Если столбец соединения одинаково назван в обеих таблицах, вместо ON можно использовать USING:

```sql
SELECT e.name, d.name
FROM employees e
JOIN departments d USING (department_id);
```

USING(department_id) эквивалентен `ON e.department_id = d.department_id`. Столбец `department_id` появляется в результате один раз (а не дважды, как при ON).

## NATURAL JOIN — неявное соединение

NATURAL JOIN автоматически находит все столбцы с одинаковыми именами в обеих таблицах и соединяет по ним. Если в `employees` и `departments` есть общий столбец `department_id`, `NATURAL JOIN` использует его как условие.

NATURAL JOIN зависит от **имён столбцов**, а не от намерения разработчика. Если кто-то добавит столбец `name` в `departments`, NATURAL JOIN молча начнёт соединять и по `department_id`, и по `name` — запрос вернёт неправильный результат без ошибки. Правило: NATURAL JOIN не используется в production-коде. Всегда явный ON или USING.

## NULL в контексте JOIN

NULL в столбце соединения означает «нет пары»: `NULL = значение` даёт NULL, условие ON не TRUE, строка не соединяется. При INNER JOIN такая строка исчезает. При LEFT JOIN — сохраняется с NULL в столбцах правой таблицы.

Как СУБД выбирает порядок соединений на практике — в [планировщике PostgreSQL](../../postgresql/query-processing/01-join-order.md).

## Sources

- PostgreSQL Documentation (v16): JOIN. <https://www.postgresql.org/docs/16/sql-select.html>
- PostgreSQL Documentation (v16): Join Types. <https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-JOIN>

---

← [Агрегация](02-aggregation.md) | [Расширенная группировка](04-grouping-sets.md) →
