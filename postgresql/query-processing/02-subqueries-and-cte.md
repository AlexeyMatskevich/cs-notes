# Подзапросы и CTE

**Предпосылки:** [планировщик запросов](00-planner.md) (cost model, алгоритмы соединения), [порядок соединения](01-join-order.md) (dynamic programming, flattening JOIN в плоский список).

Планировщик оптимизирует соединения, перебирая порядки через dynamic programming. Но SQL позволяет вкладывать запросы друг в друга — подзапросы в WHERE, FROM, SELECT — и каждый такой вложенный запрос создаёт границу. Ключевой вопрос для планировщика: растворить границу, включив таблицы подзапроса в общий join tree, или оставить подзапрос отдельной единицей планирования.

## Виды подзапросов

Подзапрос в FROM (derived table) выглядит как виртуальная таблица:

```sql
SELECT * FROM (
  SELECT user_id, COUNT(*) AS cnt FROM orders GROUP BY user_id
) stats
WHERE cnt > 10;
```

Скалярный подзапрос в WHERE возвращает одно значение и используется как константа в условии:

```sql
SELECT * FROM users
WHERE age > (SELECT AVG(age) FROM users);
```

Подзапрос с IN или EXISTS в WHERE проверяет наличие или отсутствие строк:

```sql
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);
```

Коррелированный подзапрос в SELECT вычисляет значение для каждой строки внешнего запроса:

```sql
SELECT
  u.name,
  (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count
FROM users u;
```

Каждый вид подзапроса создаёт разные ограничения для оптимизатора, и планировщик применяет к ним разные стратегии.

## Разворачивание подзапросов (Subquery Flattening)

Когда возможно, планировщик превращает подзапрос в обычное соединение. Это называется subquery flattening (или pullup). Таблицы подзапроса попадают в общий список FROM, и dynamic programming может найти для них оптимальный порядок соединения.

Подзапрос с IN:

```sql
-- До оптимизации:
SELECT * FROM users u
WHERE u.id IN (SELECT user_id FROM orders WHERE total > 1000);

-- После flattening (концептуально):
SELECT DISTINCT u.* FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.total > 1000;
```

После разворачивания планировщик выбирает алгоритм соединения (hash join, nested loop, merge join) и порядок — точно так же, как для обычного JOIN.

Flattening невозможен, когда подзапрос содержит агрегаты, DISTINCT, LIMIT, OFFSET, set-операции (UNION, INTERSECT, EXCEPT) или volatile-функции. В этих случаях подзапрос остаётся отдельной единицей планирования: планировщик сначала оптимизирует его внутренне, потом использует результат как входную таблицу для внешнего запроса. Динамическое программирование не может переупорядочить таблицы через эту границу, что может привести к неоптимальному плану, если подзапрос возвращает много строк.

## Скалярные подзапросы

Скалярный подзапрос, который не зависит от внешнего запроса (non-correlated), выполняется один раз:

```sql
SELECT * FROM users u
WHERE u.salary > (SELECT AVG(salary) FROM users);
```

Планировщик вычисляет подзапрос, получает число (например, 75 000) и подставляет его в условие — `WHERE u.salary > 75000`. Дальше внешний запрос оптимизируется как обычный запрос с константой в WHERE.

Коррелированный скалярный подзапрос зависит от внешнего запроса:

```sql
SELECT * FROM users u
WHERE u.salary > (
  SELECT AVG(salary) FROM users
  WHERE department_id = u.department_id
);
```

Наивное выполнение: для каждой строки внешнего запроса запускается подзапрос. При 100 000 пользователей — 100 000 выполнений. Планировщик пытается преобразовать такой подзапрос в соединение, чтобы обойтись одним проходом.

## Semi-join

EXISTS преобразуется в semi-join:

```sql
-- Исходный запрос:
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);

-- После оптимизации (концептуально):
SELECT u.* FROM users u SEMI JOIN orders o ON o.user_id = u.id;
```

Semi-join возвращает строку из левой таблицы, если в правой есть хотя бы одно совпадение. В отличие от обычного JOIN, semi-join не дублирует строку при нескольких совпадениях — если у пользователя 50 заказов, он появится в результате ровно один раз. В выводе EXPLAIN semi-join отображается как `Hash Semi Join` или `Nested Loop Semi Join`.

Аналогично, NOT EXISTS преобразуется в anti-join — возвращает строки из левой таблицы, для которых совпадений в правой нет.

## Pullup подзапроса из SELECT

Коррелированный подзапрос в SELECT:

```sql
SELECT
  u.name,
  (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count
FROM users u;
```

Планировщик рассматривает два варианта выполнения.

Наивный: для каждой строки users выполнить подзапрос. Если users содержит N строк — N выполнений подзапроса. При наличии индекса на `orders.user_id` каждое выполнение быстрое, но N может быть большим.

Оптимизированный (pullup): преобразовать в LEFT JOIN с агрегацией:

```sql
SELECT u.name, COALESCE(o.cnt, 0)
FROM users u
LEFT JOIN (
  SELECT user_id, COUNT(*) AS cnt FROM orders GROUP BY user_id
) o ON o.user_id = u.id;
```

Таблица orders читается один раз, агрегируется, и результат соединяется с users. Один проход вместо N.

Наивный вариант лучше, когда внешний запрос возвращает мало строк:

```sql
SELECT
  u.name,
  (SELECT COUNT(*) FROM orders WHERE user_id = u.id)
FROM users u
WHERE u.id = 42;  -- одна строка
```

Подзапрос выполнится один раз. Агрегировать всю таблицу orders ради одной строки было бы расточительно. Планировщик сравнивает cost обоих вариантов — ключевой фактор в этом решении: оценка числа строк внешнего запроса (estimated rows).

## Сводка по оптимизации подзапросов

| Тип подзапроса | Стратегия планировщика |
|----------------|----------------------|
| В FROM (derived table) | Разворачивание в JOIN, если нет агрегатов/DISTINCT/LIMIT |
| Скалярный в WHERE (non-correlated) | Однократное выполнение, подстановка результата |
| IN/EXISTS (non-correlated) | Преобразование в semi-join |
| IN/EXISTS (correlated) | Преобразование в semi-join, если возможно |
| Скалярный в SELECT (correlated) | Pullup в LEFT JOIN или N выполнений — по cost |

## CTE (Common Table Expressions)

CTE — именованный подзапрос, определённый через WITH:

```sql
WITH recent_orders AS (
  SELECT * FROM orders WHERE created_at > now() - interval '7 days'
)
SELECT u.name, ro.total
FROM users u
JOIN recent_orders ro ON u.id = ro.user_id;
```

До PostgreSQL 12 CTE всегда материализовался: результат подзапроса вычислялся целиком, сохранялся во временном хранилище, и внешний запрос работал с этим сохранённым результатом. CTE действовал как optimization fence — планировщик не мог протолкнуть условия из внешнего запроса внутрь CTE и не мог развернуть CTE в общий join tree.

Начиная с PostgreSQL 12 планировщик может развернуть (inline) CTE, если это выгодно. Условия разворачивания: CTE не рекурсивный, не содержит побочных эффектов (INSERT/UPDATE/DELETE с RETURNING) и используется в запросе ровно один раз. При разворачивании CTE растворяется — его таблицы попадают в общий FROM, условия проталкиваются, и dynamic programming оптимизирует всё вместе.

### MATERIALIZED и NOT MATERIALIZED

Ключевые слова `MATERIALIZED` и `NOT MATERIALIZED` позволяют явно контролировать поведение:

```sql
-- Принудительная материализация
WITH filtered AS MATERIALIZED (
  SELECT * FROM users WHERE country = 'Japan'
)
SELECT * FROM filtered JOIN orders ON ...;

-- Принудительное разворачивание
WITH filtered AS NOT MATERIALIZED (
  SELECT * FROM users WHERE country = 'Japan'
)
SELECT * FROM filtered WHERE age > 30;
```

Даже в PostgreSQL 12+ CTE материализуется автоматически, если используется больше одного раза, содержит побочные эффекты или является рекурсивным (`WITH RECURSIVE`).

### Когда MATERIALIZED полезен

Фиксация порядка выполнения: `MATERIALIZED` гарантирует, что CTE выполнится отдельно, до основного запроса. Это полезно, когда нужно зафиксировать промежуточный результат и контролировать порядок соединения.

Многократное использование без пересчёта:

```sql
WITH stats AS MATERIALIZED (
  SELECT user_id, COUNT(*) AS cnt FROM orders GROUP BY user_id
)
SELECT * FROM stats s1 JOIN stats s2 ON s1.cnt = s2.cnt;
```

Без `MATERIALIZED` агрегация могла бы выполниться дважды. С ним — один раз, результат переиспользуется.

### Когда MATERIALIZED вреден

```sql
WITH filtered AS MATERIALIZED (
  SELECT * FROM users WHERE country = 'Japan'
)
SELECT * FROM filtered WHERE age > 30 LIMIT 10;
```

С `MATERIALIZED`: выбрать всех японских пользователей (допустим, 50 000), сохранить, применить фильтр по возрасту, вернуть 10. Без `MATERIALIZED` (inline): условия объединяются в `WHERE country = 'Japan' AND age > 30 LIMIT 10`, и при наличии составного индекса на `(country, age)` PostgreSQL читает ровно 10 строк. Разница — полное сканирование 50 000 строк против точечного чтения 10.

### Рекурсивные CTE

```sql
WITH RECURSIVE subordinates AS (
  SELECT id, name, manager_id FROM employees WHERE id = 1
  UNION ALL
  SELECT e.id, e.name, e.manager_id
  FROM employees e
  JOIN subordinates s ON e.manager_id = s.id
)
SELECT * FROM subordinates;
```

Рекурсивный CTE всегда материализуется — inline невозможен, потому что тело ссылается на себя. Попытка развернуть привела бы к бесконечной подстановке. PostgreSQL выполняет рекурсивный CTE итеративно: начальный запрос (anchor) вычисляется один раз, затем рекурсивная часть повторяется, пока не вернёт пустой результат. На каждой итерации рекурсивная часть видит только строки, добавленные на предыдущей итерации.
