# B-tree

**Предпосылки:** [B+ дерево](../../algorithms-and-data-structures/non-linear/06-b-plus-tree.md), [страницы и кортежи](../storage/01-pages-and-tuples.md).

PostgreSQL называет свой индекс "B-tree", но технически это **B+tree с модификациями**, основанный на статье **Lehman & Yao (1981)** — "Efficient Locking for Concurrent Operations on B-Trees".

## Версии (выборочно)

| Версия PostgreSQL | Изменения в B-tree |
|-------------------|-------------------|
| 11 (2018) | Covering indexes (INCLUDE) |
| 12 (2019) | REINDEX CONCURRENTLY |
| 13 (2020) | Дедупликация записей, индексы со смешанным порядком |

## Физическая структура

PostgreSQL хранит всё в **страницах по 8 КБ** (по умолчанию). Индекс — это файл, состоящий из страниц.

    ┌─────────────────────────────────────────────────────────────┐
    │  Файл индекса                                               │
    ├─────────────────────────────────────────────────────────────┤
    │  Page 0: Meta page (служебная информация)                   │
    │  Page 1: Root (корень, может быть и листом для маленьких)   │
    │  Page 2: Internal или Leaf                                  │
    │  Page 3: Internal или Leaf                                  │
    │  ...                                                        │
    └─────────────────────────────────────────────────────────────┘

## Структура страницы B-tree

    ┌────────────────────────────────────────────────────────────────┐
    │  Page Header (24 байта)                                        │
    │  ├── pd_lsn: LSN последнего изменения (см. [WAL](../durability/00-wal.md)) │
    │  ├── pd_flags: флаги страницы                                  │
    │  ├── pd_lower: указатель на конец массива item pointers        │
    │  ├── pd_upper: указатель на начало свободного места            │
    │  └── pd_special: указатель на special space                    │
    ├────────────────────────────────────────────────────────────────┤
    │  Item Pointers (массив указателей на tuples внутри страницы)   │
    │  [ItemId 1][ItemId 2][ItemId 3]...                             │
    ├────────────────────────────────────────────────────────────────┤
    │  Free Space (свободное место, растёт навстречу)                │
    ├────────────────────────────────────────────────────────────────┤
    │  Index Tuples (сами данные, растут снизу вверх)                │
    │  [...tuple 3...][...tuple 2...][...tuple 1...]                 │
    ├────────────────────────────────────────────────────────────────┤
    │  Special Space (специфично для B-tree)                         │
    │  ├── btpo_prev: указатель на левого соседа                     │
    │  ├── btpo_next: указатель на правого соседа (right-link!)      │
    │  ├── btpo_level: уровень (0 = лист)                            │
    │  └── btpo_flags: leaf? root? deleted?                          │
    └────────────────────────────────────────────────────────────────┘

## Термины: heap tuple, index tuple, TID/ctid

В PostgreSQL слово *tuple* встречается в двух разных смыслах:

- **Heap tuple** — физическая версия строки в таблице (с заголовком `xmin/xmax/ctid/...`; см. [страницы и кортежи](../storage/01-pages-and-tuples.md) и [MVCC](../concurrency/00-mvcc.md)).
- **Index tuple** — запись внутри индекса (ключ + указатель).

Дальше в этой заметке:
- “строка” — логическая строка таблицы (row в SQL),
- “heap tuple” — физическая версия строки,
- “index tuple” — запись индекса.

### TID (ctid) — адрес heap tuple

**TID (Tuple Identifier)** — физический адрес heap tuple в heap (таблице).

**Структура:** `(block_number, offset_within_block)`

    TID = (847, 3)
            │    │
            │    └── третий tuple на этой странице (нумерация с 1)
            │
            └── страница номер 847 в файле heap

В SQL тот же указатель виден как системная колонка `ctid`.

## Index Tuple — что хранится в узле

Для **листовой страницы**:

    ┌─────────────────────────────────────────┐
    │  Index Tuple (лист)                     │
    ├─────────────────────────────────────────┤
    │  t_tid: (block_number, offset)          │  ← указатель на строку в heap
    │  t_info: размер и флаги                 │
    │  key_data: значение ключа               │  ← например, salary=50000
    └─────────────────────────────────────────┘

Для **внутренней страницы**:

    ┌─────────────────────────────────────────┐
    │  Index Tuple (внутренний)               │
    ├─────────────────────────────────────────┤
    │  t_tid: (child_block, offset)           │  ← указатель на дочернюю страницу
    │  t_info: размер и флаги                 │
    │  key_data: разделитель (pivot)          │  ← граница для навигации
    └─────────────────────────────────────────┘

## High Key и Right-Link (Lehman & Yao)

Каждая страница (кроме самой правой на уровне) содержит **high key** — максимальное значение, которое может быть на этой странице.

    Страница A                          Страница B
    ┌─────────────────────┐            ┌─────────────────────┐
    │ high_key = 50       │───────────→│ high_key = 100      │
    │ keys: 10, 20, 30, 40│            │ keys: 50, 60, 70, 80│
    │ right_link ─────────────────────→│                     │
    └─────────────────────┘            └─────────────────────┘

**Зачем это нужно?**

При конкурентной вставке страница может разделиться (split) в момент, когда другой процесс её читает. High key и right-link позволяют читателю понять: "о, страница разделилась, мне нужно пойти направо".

Это позволяет избежать блокировки всего дерева при вставках — блокируем только те страницы, которые непосредственно модифицируем.

## Зачем двусвязный список листьев

PostgreSQL использует **двусвязный список** (btpo_prev + btpo_next), а не односвязный.

**Причина: ORDER BY ... DESC**

    SELECT * FROM employees
    ORDER BY salary DESC
    LIMIT 10;

Что происходит:
- Нужны 10 самых высоких зарплат
- Спускаемся по дереву до самого правого листа
- Идём **назад** по листьям через btpo_prev, собирая значения

В плане выполнения это отображается как:

    Index Scan Backward using idx_salary on employees

## Heap и Index — две отдельные структуры

**Критически важно:** в PostgreSQL данные таблицы (heap) и индекс — это **разные файлы**.

    ┌─────────────────────────────────────────────────────────────────┐
    │  HEAP (куча) — сама таблица                                     │
    │  Данные лежат В ПОРЯДКЕ ВСТАВКИ, не отсортированы ни по чему   │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  INDEX — отдельная структура (B+tree)                          │
    │  Ключи отсортированы, каждый ключ содержит указатель (TID)     │
    │  на физическое расположение строки в heap                       │
    └─────────────────────────────────────────────────────────────────┘

**Следствие:** после поиска по индексу нужно идти в heap за данными — это random I/O.

## Три типа сканирования индекса

### Index Scan

Классическое использование индекса:

    1. Спуск по B-tree до нужного листа
    2. Для каждого найденного ключа — поход в heap по TID
    3. Возврат данных

**Проблема:** random I/O при походах в heap.

**Когда используется:** малая селективность (< 1-2% строк).

### Bitmap Index Scan

Двухфазное сканирование для уменьшения random I/O:

**Фаза 1:** Читаем индекс, строим bitmap страниц heap

    Bitmap страниц:
    ┌─────────────────────────────────────────────────────────┐
    │ Page:  0   1   2   ...  123  ...  291  ...  532  ...  847 │
    │ Bit:   0   0   0   ...   1   ...   1   ...   1   ...   1  │
    └─────────────────────────────────────────────────────────┘

**Фаза 2:** Читаем страницы heap в порядке номеров (ближе к sequential I/O)

**Когда используется:** средняя селективность (2-15% строк).

**Бонус:** можно комбинировать несколько индексов через BitmapAnd / BitmapOr.

    SELECT * FROM employees
    WHERE salary > 50000 AND department_id = 5;

    -- План:
    Bitmap Heap Scan
      →  BitmapAnd
            →  Bitmap Index Scan on idx_salary
            →  Bitmap Index Scan on idx_department

### Index Only Scan

Если все нужные колонки есть в индексе — не ходим в heap вообще.

    CREATE INDEX idx_salary ON employees(salary);

    -- Этот запрос может использовать Index Only Scan:
    SELECT salary FROM employees WHERE salary > 50000;

    -- А этот — нет (name не в индексе):
    SELECT name, salary FROM employees WHERE salary > 50000;

**Ограничение:** работает только если страница heap помечена как "all-visible" в Visibility Map (см. [VACUUM](../maintenance/00-vacuum.md); связано с [MVCC](../concurrency/00-mvcc.md)).

### Covering Index (INCLUDE) — PostgreSQL 11+

Решение проблемы Index Only Scan:

    CREATE INDEX idx_salary_covering
    ON employees(salary)
    INCLUDE (name, department);

Теперь в листьях индекса хранится:

    [salary=50000, TID, name="Carol", department="Sales"]

Запрос может получить всё из индекса без heap.

**Цена:** индекс больше по размеру.

## Операции модификации в PostgreSQL

### INSERT

PostgreSQL использует split по Lehman & Yao:

1. Спуск до целевого листа
2. Вставка ключа
3. Если переполнение — split:
   - Создаём новую страницу
   - Устанавливаем high_key и right_link
   - Добавляем разделитель в родителя (отдельный шаг)

Между шагами дерево "временно неконсистентно", но right-link позволяет читателям корректно работать.

### DELETE — НЕ как в учебнике!

**Учебник:** при удалении делаем borrowing или merge.

**PostgreSQL:** нет, не делаем.

    До удаления:
    Лист: [10, 20, 30, 40, 50]

    Удаляем 30:

    После удаления:
    Лист: [10, 20, □, 40, 50]
                  ↑
            dead tuple (помечен как удалённый, но физически на месте)

**Почему PostgreSQL не делает merge:**

1. **MVCC:** удалённая запись может быть ещё видна другим транзакциям
2. **Сложность:** merge требует много блокировок
3. **Бесполезность:** освободившееся место часто быстро занимается новыми записями

### UPDATE = DELETE + INSERT

**Важнейшая особенность PostgreSQL!**

При UPDATE PostgreSQL не изменяет строку in-place. Он создаёт новую версию:

    Heap до UPDATE:
      Tuple 1: (id=1, status='pending')
               xmin=500, xmax=∞

    Heap после UPDATE:
      Tuple 1: (id=1, status='pending')     ← помечена как мёртвая
               xmin=500, xmax=600

      Tuple 2: (id=1, status='processing')  ← новая версия
               xmin=600, xmax=∞

**Следствие для индексов:** каждый UPDATE создаёт dead tuple в индексе.

**Почему так:** MVCC требует сохранения старых версий для других транзакций.

## HOT — Heap-Only Tuples (PostgreSQL 8.3+)

### Название

**HOT (Heap-Only Tuples)** — оптимизация, при которой новая версия строки создаётся без обновления индексов.

**Почему "Heap-Only":** новый tuple существует только в heap, индексы продолжают указывать на старый tuple.

### Условия для HOT

1. Изменяемые колонки **не входят ни в один индекс**
2. Новая версия tuple **помещается на ту же страницу** heap

### Как работает

    Heap до UPDATE:
    ┌─────────────────────────────────────────────────────────────┐
    │ Page 100:                                                   │
    │   Tuple 1: (id=1, price=100, description='old')            │
    │            TID=(100,1)                                      │
    └─────────────────────────────────────────────────────────────┘

    Index по price:
    [price=100, TID=(100,1)]

    Heap после HOT UPDATE (изменили только description):
    ┌─────────────────────────────────────────────────────────────┐
    │ Page 100:                                                   │
    │   Tuple 1: (id=1, price=100, description='old')            │
    │            DEAD, указатель → Tuple 2                        │
    │                                                             │
    │   Tuple 2: (id=1, price=100, description='new')            │
    │            TID=(100,2), LIVE                                │
    └─────────────────────────────────────────────────────────────┘

    Index по price:
    [price=100, TID=(100,1)]  ← НЕ ИЗМЕНИЛСЯ!

При поиске: индекс указывает на Tuple 1, который перенаправляет на Tuple 2.

### Мониторинг HOT

    SELECT
        relname,
        n_tup_upd as total_updates,
        n_tup_hot_upd as hot_updates,
        round(100.0 * n_tup_hot_upd / nullif(n_tup_upd, 0), 1) as hot_percent
    FROM pg_stat_user_tables
    WHERE relname = 'your_table';

Хороший показатель: **hot_percent > 90%**.

## Bloat — раздувание индекса

### Что это

После множества DELETE/UPDATE индекс содержит много dead tuples и полупустых страниц.

    После множества DELETE:
    ┌─────────┐
    │  Root   │
    └────┬────┘
         ├────────────┬────────────┐
         ↓            ↓            ↓
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Leaf 1  │↔│ Leaf 2  │↔│ Leaf 3  │  все ~10-20% заполнены
    │  BLOAT! │ │  BLOAT! │ │  BLOAT! │
    └─────────┘ └─────────┘ └─────────┘

### Почему это плохо

- Больше страниц читать при сканировании
- Больше места на диске
- Вытеснение полезных данных из кэша

### VACUUM

**[VACUUM](../maintenance/00-vacuum.md)** — фоновый процесс, чистящий dead tuples.

    До VACUUM:
    Лист: [10, 20, DEAD, DEAD, 50, DEAD, 70]

    После VACUUM:
    Лист: [10, 20, 50, 70, □, □, □]
                          ↑ свободное место

**Важно:** VACUUM **не уменьшает размер файла индекса**. Он освобождает место внутри страниц для повторного использования.

### Лечение bloat

**REINDEX:**

    REINDEX INDEX idx_salary;  -- блокирует таблицу

**REINDEX CONCURRENTLY (PostgreSQL 12+):**

    REINDEX INDEX CONCURRENTLY idx_salary;  -- не блокирует

## Operator Classes

### Название и суть

**Operator Class (операторный класс)** — набор операторов и функций, которые говорят индексу, как работать с конкретным типом данных.

### Что нужно B-tree

B-tree требует **пять операторов сравнения**:

    Стратегия 1: <   (меньше)
    Стратегия 2: <=  (меньше или равно)
    Стратегия 3: =   (равно)
    Стратегия 4: >=  (больше или равно)
    Стратегия 5: >   (больше)

И **support function** — функцию сравнения:

    compare(a, b) → integer
      Возвращает:
        -1 если a < b
         0 если a = b
        +1 если a > b

### Примеры operator classes

    SELECT opcname, opcintype::regtype
    FROM pg_opclass
    WHERE opcmethod = (SELECT oid FROM pg_am WHERE amname = 'btree')
    ORDER BY opcintype::regtype::text
    LIMIT 10;

    -- Результат:
    -- int4_ops      │ integer
    -- int8_ops      │ bigint
    -- text_ops      │ text
    -- date_ops      │ date
    -- uuid_ops      │ uuid

## Collation

### Название и суть

**Collation (правила сортировки)** — набор правил, определяющих порядок сортировки строк.

От латинского "collatio" — сравнение, сопоставление.

### Влияние на индекс

Индекс строится с конкретной collation:

    -- Посмотреть collation базы
    SHOW lc_collate;

    -- Разные индексы с разной collation
    CREATE INDEX idx_name_en ON users(name COLLATE "en_US");
    CREATE INDEX idx_name_c ON users(name COLLATE "C");

### Collation "C" vs локализованная

**Collation "C"** — побайтовое сравнение:
- Предсказуемый порядок (по ASCII/UTF-8 кодам)
- 'Z' < 'a' (заглавные перед строчными)
- Быстрее
- Работает для LIKE 'prefix%'

**Локализованная (например, "en_US.UTF-8")**:
- Регистронезависимая сортировка
- 'a' < 'B' < 'c'
- LIKE 'prefix%' **не использует индекс**

### text_pattern_ops для LIKE

    -- Обычный индекс — LIKE не работает с en_US
    CREATE INDEX idx_email ON users(email);

    -- Специальный operator class для паттернов
    CREATE INDEX idx_email_pattern ON users(email text_pattern_ops);

    -- Теперь работает:
    SELECT * FROM users WHERE email LIKE 'john%';

## Составные индексы

### Структура

Составной индекс — один B-tree с многокомпонентным ключом.

    CREATE INDEX idx_user_created ON events(user_id, created_at);

Сортировка: сначала по user_id, при равенстве — по created_at.

    Отсортированный порядок:
    (1, 2024-01-05)
    (1, 2024-01-15)
    (1, 2024-01-25)
    (2, 2024-01-03)
    (2, 2024-01-10)

### Leftmost Prefix Rule

Составной индекс `(A, B, C)` эффективен для:

    WHERE A = ?                     ✓ использует индекс
    WHERE A = ? AND B = ?           ✓ использует индекс
    WHERE A = ? AND B = ? AND C = ? ✓ использует индекс
    WHERE A = ? AND C = ?           △ только по A, C фильтруется
    WHERE B = ?                     ✗ индекс бесполезен
    WHERE C = ?                     ✗ индекс бесполезен

**Аналогия:** телефонный справочник отсортирован по (фамилия, имя). Можно найти всех Ивановых, всех Ивановых Иванов, но нельзя эффективно найти всех Иванов.

### ORDER BY и составные индексы

Индекс `(A, B, C)` помогает с ORDER BY если:

    ORDER BY A                    ✓
    ORDER BY A, B                 ✓
    ORDER BY A, B, C              ✓
    ORDER BY A DESC, B DESC       ✓ (читаем индекс назад)

    ORDER BY B                    ✗
    ORDER BY A, C                 ✗ (пропущен B)
    ORDER BY A ASC, B DESC        ✗ (смешанные направления)*

    *PostgreSQL 13+ поддерживает:
    CREATE INDEX idx ON t(A ASC, B DESC);

## Уникальные индексы

### UNIQUE INDEX vs UNIQUE CONSTRAINT

| Аспект | UNIQUE CONSTRAINT | UNIQUE INDEX |
|--------|-------------------|--------------|
| Где хранится | pg_constraint + pg_index | только pg_index |
| FOREIGN KEY | Да | Нет |
| DEFERRABLE | Да | Нет |
| Partial (WHERE) | Нет | Да |
| INCLUDE колонки | Нет* | Да |

### DEFERRABLE

**Deferrable** — возможность отложить проверку до конца транзакции.

    ALTER TABLE departments
    ADD CONSTRAINT fk_head
    FOREIGN KEY (head_employee_id) REFERENCES employees(id)
    DEFERRABLE INITIALLY DEFERRED;

    BEGIN;
    INSERT INTO departments (id, head_employee_id) VALUES (1, 1);
    INSERT INTO employees (id, department_id) VALUES (1, 1);
    COMMIT;  -- Проверка здесь

### Partial Unique Index

**Partial Index** — индекс только для части строк.

    -- Уникальность email только для активных пользователей
    CREATE UNIQUE INDEX idx_email_active
    ON users(email)
    WHERE deleted_at IS NULL;

Позволяет:
- Реализовать soft delete с повторным использованием email
- Экономить место (индексируем только нужные строки)

## Сводка: когда B-tree подходит

| Задача | Решение |
|--------|---------|
| Поиск по точному значению | B-tree |
| Поиск по диапазону | B-tree |
| Сортировка | B-tree (порядок колонок важен) |
| LIKE 'prefix%' | B-tree с COLLATE "C" или text_pattern_ops |
| Уникальность | UNIQUE INDEX или UNIQUE CONSTRAINT |
| Уникальность с условием | Partial UNIQUE INDEX |
| Частые UPDATE по одним колонкам | HOT (не индексировать изменяемые колонки) |
| Bloat | VACUUM, REINDEX CONCURRENTLY |

## Терминология PostgreSQL B-tree

| Термин | Значение |
|--------|----------|
| Heap | Файл с данными таблицы (не путать с heap как структурой данных) |
| Tuple | Строка таблицы или запись индекса |
| TID | Tuple Identifier — адрес (page, offset) |
| Page | Страница 8KB |
| High key | Максимальный ключ на странице (Lehman & Yao) |
| Right-link | Указатель на соседнюю страницу справа |
| Dead tuple | Удалённая запись, ожидающая VACUUM |
| Bloat | Раздувание из-за dead tuples |
| HOT | Heap-Only Tuple — UPDATE без изменения индексов |
| Visibility Map | Битовая карта "все tuple видимы" для Index Only Scan |
| Operator class | Набор операторов для работы индекса с типом данных |
| Collation | Правила сортировки строк |

B-tree покрывает точные совпадения, диапазоны и сортировку. Когда нужно заглянуть внутрь составных значений — массивов, JSONB, полнотекстовых векторов — работает [GIN](01-gin.md).

## Sources

- PostgreSQL Documentation (пример: v16): Indexes, B-tree, Index-Only Scans, operator classes, collations. <https://www.postgresql.org/docs/16/indexes.html>, <https://www.postgresql.org/docs/16/indexes-types.html>, <https://www.postgresql.org/docs/16/indexes-index-only-scans.html>, <https://www.postgresql.org/docs/16/indexes-opclass.html>, <https://www.postgresql.org/docs/16/collation.html>
- Lehman, P., Yao, S. *Efficient Locking for Concurrent Operations on B-Trees* (1981). <https://doi.org/10.1145/319566.319567>
- PostgreSQL Release Notes: v11/v12/v13 (INCLUDE, REINDEX CONCURRENTLY, deduplication, mixed-order indexes). <https://www.postgresql.org/docs/11/release-11.html>, <https://www.postgresql.org/docs/12/release-12.html>, <https://www.postgresql.org/docs/13/release-13.html>
