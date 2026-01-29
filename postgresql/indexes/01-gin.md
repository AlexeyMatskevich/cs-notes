# GIN — обобщённый инвертированный индекс

**Предпосылки:** [инвертированный индекс](../../algorithms-and-data-structures/non-linear/08-inverted-index.md), [B-tree](00-btree.md).

Инвертированный индекс «переворачивает» отношение между записью и её содержимым: вместо «документ → элементы» хранит «элемент → список документов». Подробнее о структуре, словаре, posting list и операциях пересечения/объединения — в [инвертированный индекс](../../algorithms-and-data-structures/non-linear/08-inverted-index.md).

GIN (Generalized Inverted Index) — обобщённый инвертированный индекс. «Обобщённый» означает, что GIN работает не только с текстом, а с любыми типами данных, которые можно разбить на элементы: массивы, JSONB, полнотекстовые векторы. GIN — фреймворк, адаптируемый под разные типы через operator class. Появился в PostgreSQL 8.2 (2006).

## Что индексирует GIN

GIN индексирует **составные значения**, разбивая их на **элементы**:

| Тип данных | Составное значение | Элементы |
|------------|-------------------|----------|
| integer[] | {1, 2, 3} | 1, 2, 3 |
| text[] | {ruby, rails} | ruby, rails |
| jsonb | {"a": 1, "tags": ["x", "y"]} | a, 1, tags, x, y |
| tsvector | 'cat' 'dog' 'fish' | cat, dog, fish |

## Почему B-tree не подходит

B-tree сортирует *целые массивы* как единое значение, лексикографически по элементам. Для массива `{ruby, rails, postgresql}` B-tree может эффективно искать *точное совпадение* массива или *диапазон массивов*. Но для оператора `@>` ("содержит элемент") B-tree бесполезен — элемент может быть на любой позиции, в массиве любой длины, с любыми соседними элементами. B-tree не может "заглянуть внутрь" значения.

## Физическая структура GIN

GIN состоит из двух основных частей:

### 1. Entry Tree (дерево ключей)

B-tree, где ключи — это **отдельные элементы** (не составные значения).

             ┌─────────────────┐
             │   Entry Tree    │
             │    (B-tree)     │
             └────────┬────────┘
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
     [django]     [python]      [ruby]
        │             │             │
        ↓             ↓             ↓
     Posting      Posting       Posting
      List         List          List

**Почему B-tree для ключей, а не хеш-таблица?** B-tree сохраняет порядок ключей. Это критично для диапазонных запросов по элементам (если ключи — числа) и prefix-поиска (для tsvector можно искать лексемы, начинающиеся с "prog").

### 2. Posting List (список вхождений)

Для каждого ключа — отсортированный список TID (указателей на строки), где этот ключ встречается.

    ruby → [TID(100,1), TID(200,3), TID(350,2)]
             ↓            ↓            ↓
          строка 1     строка 2     строка 3
          в heap       в heap       в heap

**Почему отсортированный?** Для эффективного пересечения при AND-запросах. Merge двух отсортированных списков — O(n + m) методом двух указателей, а не O(n × m).

**Что хранится в posting list:** только TID'ы (адреса строк в heap). Сам ключ не дублируется — он уже есть в Entry Tree.

### 3. Posting Tree (для частых ключей)

Если posting list слишком длинный (ключ встречается в тысячах строк), он не помещается в одну страницу. PostgreSQL превращает его в отдельное **B-tree по TID** — Posting Tree.

    Редкий ключ "sinatra":
    sinatra → [TID1, TID2, TID3]  (простой список, inline в листе Entry Tree)

    Частый ключ "the":
    the → ┌──────────────────┐
          │   Posting Tree   │
          │  (B-tree по TID) │
          └──────────────────┘
          Содержит миллионы TID

**Порог переключения:** определяется тем, помещается ли список на одну страницу (~8KB).

**TID как ключ в Posting Tree:** TID — это пара (block_number, offset_number). Сравниваются лексикографически: сначала по block_number, при равенстве — по offset.

    (100, 1) < (100, 2) < (200, 1) < (200, 5)

## Пример: индексирование массива

    CREATE TABLE posts (
        id serial PRIMARY KEY,
        title text,
        tags text[]
    );

    INSERT INTO posts (title, tags) VALUES
    ('Ruby Basics', ARRAY['ruby', 'tutorial']),
    ('PostgreSQL GIN', ARRAY['postgresql', 'indexing', 'tutorial']),
    ('Rails API', ARRAY['ruby', 'rails', 'api']);

    CREATE INDEX idx_tags ON posts USING gin(tags);

Что построит PostgreSQL:

    Entry Tree (B-tree по элементам массивов):
    ┌─────────────────────────────────────────────────┐
    │  api → indexing → postgresql → rails → ruby → tutorial │
    └─────────────────────────────────────────────────┘

    Posting Lists:
    api        → [TID строки 3]
    indexing   → [TID строки 2]
    postgresql → [TID строки 2]
    rails      → [TID строки 3]
    ruby       → [TID строки 1, TID строки 3]
    tutorial   → [TID строки 1, TID строки 2]

## Поиск в GIN

### Запрос: WHERE tags @> ARRAY['ruby']

"Найти посты, где tags содержит 'ruby'"

    1. Ищем 'ruby' в Entry Tree (B-tree поиск) — O(log K), где K = число уникальных ключей
    2. Получаем posting list: [TID строки 1, TID строки 3]
    3. Идём в heap за строками

### Запрос: WHERE tags @> ARRAY['ruby', 'tutorial']

"Найти посты, где tags содержит И 'ruby', И 'tutorial'"

    1. Ищем 'ruby' в Entry Tree → [TID1, TID3]
    2. Ищем 'tutorial' в Entry Tree → [TID1, TID2]
    3. Пересечение (AND): [TID1, TID3] ∩ [TID1, TID2] = [TID1]
    4. Идём в heap за строкой 1

Пересечение двух отсортированных списков — O(n + m) методом двух указателей.

### Запрос: WHERE tags && ARRAY['ruby', 'rails']

"Найти посты, где tags содержит 'ruby' ИЛИ 'rails' (хотя бы один)"

    1. Ищем 'ruby' в Entry Tree → [TID1, TID3]
    2. Ищем 'rails' в Entry Tree → [TID3]
    3. Объединение (OR): [TID1, TID3] ∪ [TID3] = [TID1, TID3]
    4. Идём в heap за строками 1 и 3

## Сжатие Posting Lists

Каждый TID занимает 6 байт (4 байта block_number + 2 байта offset). Posting list из миллиона TID'ов — 6 МБ.

PostgreSQL использует **varbyte encoding** — кодирование дельт между соседними TID'ами с переменной длиной байта:

    Несжатый posting list:
        TID(100,1), TID(100,2), TID(100,5), TID(101,1), TID(105,3)
        6 + 6 + 6 + 6 + 6 = 30 байт

    Сжатый (дельты):
        База: TID(100,1)
        Дельты: +1, +3, +252, +1026

        Дельта +1 кодируется 1 байтом
        Дельта +1026 кодируется 2 байтами
        Итого: ~10-15 байт вместо 30

Сжатие эффективнее, когда TID'ы идут последовательно (таблица не фрагментирована). После VACUUM FULL или CLUSTER сжатие лучше.

## Операторы для GIN

### Массивы (integer[], text[], и т.д.)

| Оператор | Значение | Пример |
|----------|----------|--------|
| `@>` | Содержит все элементы | `tags @> ARRAY['ruby']` |
| `<@` | Содержится в | `tags <@ ARRAY['ruby', 'rails', 'api']` |
| `&&` | Пересекается (есть общие) | `tags && ARRAY['ruby', 'python']` |
| `=` | Равны | `tags = ARRAY['ruby', 'rails']` |

### JSONB

| Оператор | Значение | Пример |
|----------|----------|--------|
| `@>` | Содержит JSON | `data @> '{"type": "post"}'` |
| `?` | Содержит ключ | `data ? 'email'` |
| `?&` | Содержит все ключи | `data ?& array['email', 'name']` |
| `?\|` | Содержит любой ключ | `data ?\| array['email', 'phone']` |

## JSONB: jsonb_ops vs jsonb_path_ops

PostgreSQL предлагает два operator class для JSONB:

### jsonb_ops (по умолчанию)

    CREATE INDEX idx_data ON products USING gin(data);
    -- эквивалентно:
    CREATE INDEX idx_data ON products USING gin(data jsonb_ops);

**Что индексирует:** каждый ключ и каждое значение отдельно.

**Поддерживает:** `@>`, `?`, `?&`, `?\|`, `@?`, `@@`

### jsonb_path_ops

    CREATE INDEX idx_data ON products USING gin(data jsonb_path_ops);

**Что индексирует:** хеши полных путей от корня до значения.

**Поддерживает:** только `@>`, `@?`, `@@`

### Сравнение

| Аспект | jsonb_ops | jsonb_path_ops |
|--------|-----------|----------------|
| Размер индекса | Больше | Меньше (~30%) |
| Оператор `?` (наличие ключа) | Да | Нет |
| Оператор `@>` (containment) | Да | Да, быстрее |
| Когда использовать | Нужны `?`, `?&`, `?\|` | Только `@>` запросы |

## Полнотекстовый поиск: tsvector и tsquery

### Проблема

    SELECT * FROM articles WHERE body LIKE '%database%';

Проблемы:
- Full table scan (LIKE с `%` в начале не использует B-tree)
- Не находит "databases", "Database", "DATABASE"
- Не понимает словоформы: "running" vs "run"

### Решение: tsvector и tsquery

**tsvector (text search vector)** — представление текста в виде отсортированного списка **лексем** (нормализованных слов).

**Лексема (lexeme)** — нормализованная форма слова: без окончаний, в нижнем регистре.

    SELECT to_tsvector('english', 'The quick brown foxes are running fast');

    -- Результат:
    'brown':3 'fast':7 'fox':4 'quick':2 'run':6

Что произошло:
- "The", "are" — удалены (стоп-слова)
- "foxes" → "fox" (стемминг: отсечение окончания)
- "running" → "run" (стемминг)
- Числа — позиции слов в оригинале

**tsquery (text search query)** — запрос для поиска по tsvector.

    SELECT to_tsquery('english', 'running & fox');

    -- Результат:
    'run' & 'fox'

### Оператор @@

    SELECT * FROM articles
    WHERE to_tsvector('english', body) @@ to_tsquery('english', 'database');

Оператор `@@` — "tsvector соответствует tsquery".

### GIN индекс для полнотекстового поиска

**Способ 1: индекс на выражение**

    CREATE INDEX idx_body_fts ON articles
    USING gin(to_tsvector('english', body));

    -- Запрос должен точно соответствовать выражению:
    SELECT * FROM articles
    WHERE to_tsvector('english', body) @@ to_tsquery('english', 'database');

**Способ 2: отдельная колонка tsvector (рекомендуется)**

    ALTER TABLE articles ADD COLUMN body_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', body)) STORED;

    CREATE INDEX idx_body_tsv ON articles USING gin(body_tsv);

    -- Запрос проще:
    SELECT * FROM articles
    WHERE body_tsv @@ to_tsquery('english', 'database');

## Pending List (Fast Update)

### Проблема записи в GIN

INSERT одной строки с массивом из 200 элементов требует 200 модификаций индекса — по одной для каждого элемента. Каждая модификация потенциально требует записи страницы. Много random I/O.

### Решение: отложенная вставка

**Pending List (список ожидания)** — несортированный буфер для новых записей. Вместо дорогой операции (random I/O в множество мест B-tree) делаем дешёвую (sequential append в один список).

    INSERT статьи с лексемами [postgresql, gin, index]

    С pending list:
    → Записываем пары (ключ, TID) в конец pending list
    → Готово!

    ┌─────────────────────────────────────────────────────────────┐
    │  Pending List (несортированный, append-only)               │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │ (postgresql, TID1) (gin, TID1) (index, TID1) ...    │   │
    │  │ (database, TID2) (query, TID2) ...                  │   │
    │  └─────────────────────────────────────────────────────┘   │
    │                                                             │
    │  Entry Tree + Posting Lists (основная структура)           │
    │  (обновляется позже, batch-ом)                             │
    └─────────────────────────────────────────────────────────────┘

**Важно:** ключ в pending list может повторяться. Это просто лог вставок. При слиянии записи с одинаковым ключом объединяются в один posting list.

### Влияние на поиск

При поиске PostgreSQL проверяет **обе структуры**:

    1. Ищем в Entry Tree → получаем posting list
    2. Сканируем весь Pending List (несортированный!)
    3. Объединяем результаты

**Проблема для редких ключей:** pending list сканируется целиком. Если в pending list 100,000 записей, а по основному индексу нашли бы 5 строк — 99.99% времени тратим на сканирование pending list, где может не быть ни одного релевантного результата.

**Компромисс:** INSERT быстрее, SELECT медленнее (особенно для редких ключей).

### Когда pending list сливается

1. При переполнении: `gin_pending_list_limit` (по умолчанию 4MB). Та транзакция, которой "не повезло", платит за всех.
2. При `VACUUM` таблицы
3. Вручную: `SELECT gin_clean_pending_list('idx_name')`

### Отключение Fast Update

    CREATE INDEX idx_body_tsv ON articles USING gin(body_tsv)
    WITH (fastupdate = off);

Теперь INSERT сразу модифицирует основную структуру.

**Когда отключать fastupdate:**
- Нагрузка read-heavy (много поисков, мало вставок)
- Критична предсказуемость latency (pending list создаёт спайки при слиянии)

**Когда оставлять включённым:**
- Нагрузка write-heavy или bulk insert
- Средняя производительность важнее worst-case latency

## Составные GIN индексы

GIN поддерживает составные индексы:

    CREATE INDEX idx_tags_attrs ON products USING gin(tags, attributes);

**Важное отличие от B-tree:** нет "leftmost prefix rule". Каждая колонка индексируется независимо.

    -- Все три запроса используют idx_tags_attrs:
    WHERE tags @> ARRAY['electronics']              -- ✓
    WHERE attributes @> '{"color": "black"}'        -- ✓
    WHERE tags @> ARRAY['phone'] AND attributes ? 'storage'  -- ✓

GIN хранит элементы из всех колонок в одном Entry Tree, помечая, из какой колонки каждый элемент.

## Operator Class для GIN

GIN требует от типа данных определить несколько функций:

**extractValue(datum)** — разбивает составное значение на элементы при индексации. Получает массив {10, 20, 30}, возвращает три ключа: 10, 20, 30.

**extractQuery(query, strategy)** — разбивает условие запроса на искомые элементы. Получает условие "@> ARRAY[10, 30]", возвращает ключи 10 и 30, плюс информацию что нужно AND.

**consistent(check[], query, strategy)** — проверяет, удовлетворяет ли набор найденных ключей условию запроса.

Разные operator classes для одного типа могут индексировать его по-разному (как jsonb_ops vs jsonb_path_ops).

## Сложность операций GIN

| Операция | Сложность | Примечание |
|----------|-----------|------------|
| Поиск одного ключа | O(log K + P) | K = уникальных ключей, P = размер posting list |
| Поиск с AND | O(log K × m + merge) | m = ключей в запросе, merge = O(P1 + P2 + ...) |
| Поиск с OR | O(log K × m + union) | union = O(P1 + P2 + ...) |
| INSERT (fastupdate=on) | O(1) amortized | Append в pending list |
| INSERT (fastupdate=off) | O(e × log K) | e = элементов в значении |

## Когда использовать GIN

| Задача | Подходит GIN? |
|--------|---------------|
| Поиск по элементам массива | Да |
| Поиск по ключам/значениям JSONB | Да |
| Полнотекстовый поиск | Да |
| Поиск по диапазону (>, <, BETWEEN) | Нет, используй B-tree |
| Сортировка (ORDER BY) | Нет, используй B-tree |
| Уникальность | Нет, используй B-tree |
| Поиск ближайших соседей | Нет, используй GiST |

## Терминология GIN

| Термин | Значение |
|--------|----------|
| Inverted Index | Индекс "элемент → список документов" |
| Entry Tree | B-tree по элементам (ключам) |
| Posting List | Отсортированный список TID для одного ключа |
| Posting Tree | B-tree по TID для частого ключа |
| Pending List | Несортированный буфер для отложенной вставки |
| Fast Update | Режим с pending list (по умолчанию включён) |
| tsvector | Нормализованное представление текста для поиска |
| tsquery | Запрос для полнотекстового поиска |
| Лексема (lexeme) | Нормализованная форма слова |
| jsonb_ops | Operator class для JSONB, все операторы |
| jsonb_path_ops | Operator class для JSONB, только @>, компактнее |

GIN работает с дискретными элементами внутри составных значений. Данные без линейного порядка — геометрия, диапазоны, IP-сети — индексирует [GiST](02-gist.md).
