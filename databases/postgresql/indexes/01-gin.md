# GIN — обобщённый инвертированный индекс

**Предпосылки:** [инвертированный индекс](../../../algorithms-and-data-structures/non-linear/08-inverted-index.md), [B-tree](00-btree.md).

← [B-tree](00-btree.md) | [GiST](02-gist.md) →

[Инвертированный индекс](../../../algorithms-and-data-structures/non-linear/08-inverted-index.md) «переворачивает» отношение: вместо «документ → элементы» хранит «элемент → список документов». GIN (Generalized Inverted Index) — обобщённая реализация этой идеи в PostgreSQL: он работает не только с текстом, а с любыми типами, которые можно разбить на элементы — массивами, JSONB, полнотекстовыми векторами. «Обобщённый» означает, что GIN — фреймворк, адаптируемый под разные типы данных через operator class. Появился в PostgreSQL 8.2 (2006).

## Почему B-tree не может заглянуть внутрь

В интернет-магазине у каждого товара есть массив тегов. Нужно найти все товары с тегом 'ruby': `WHERE tags @> ARRAY['ruby']`. [B-tree](00-btree.md) сортирует *целые массивы* лексикографически — `{a, b}` < `{a, c}` — и может искать только точное совпадение массива или диапазон массивов. Оператор `@>` («содержит элемент») B-tree не поддерживает: элемент может быть на любой позиции, в массиве любой длины.

GIN решает задачу: он разбивает каждый массив на отдельные элементы и индексирует каждый из них. Массив `{ruby, rails, api}` превращается в три записи в индексе, каждая указывает на строку-источник.

```sql
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
```

Три строки — шесть уникальных элементов. PostgreSQL построит индекс, в котором каждый элемент ведёт к списку строк, содержащих его.

## Физическая структура: Entry Tree и Posting Lists

GIN состоит из двух частей. **Entry Tree** — [B-tree](00-btree.md), где ключи — отдельные элементы (не составные значения). Почему B-tree, а не [хеш-таблица](../../../algorithms-and-data-structures/linear/05-hash-table.md)? B-tree сохраняет порядок ключей, что критично для диапазонных запросов по числовым элементам и prefix-поиска по лексемам (например, все слова на «prog»).

Для каждого ключа в Entry Tree хранится **posting list** — отсортированный список TID (ctid) строк, содержащих этот элемент. Вот что GIN построит для данных выше:

```
Entry Tree (B-tree по элементам):

    api -- indexing -- postgresql -- rails -- ruby -- tutorial

Posting Lists:
    api        -> [TID(1,3)]
    indexing   -> [TID(1,2)]
    postgresql -> [TID(1,2)]
    rails      -> [TID(1,3)]
    ruby       -> [TID(1,1), TID(1,3)]
    tutorial   -> [TID(1,1), TID(1,2)]
```

Posting list отсортирован по TID, потому что основная операция — [пересечение списков](../../../algorithms-and-data-structures/non-linear/08-inverted-index.md) при AND-запросах. Merge двух отсортированных списков — O(n + m) методом двух указателей, а не O(n × m). Сами ключи в posting list не дублируются — они уже есть в Entry Tree.

## Posting Tree: когда posting list не помещается на страницу

Для редких ключей (например, тег 'sinatra' на трёх товарах) posting list хранится inline в листе Entry Tree. Но когда ключ встречается в тысячах строк (тег 'sale' на 100 000 товаров), список не помещается на одну страницу (~8 КБ). PostgreSQL превращает его в **Posting Tree** — отдельное B-tree по TID:

```
Редкий ключ:   sinatra -> [TID1, TID2, TID3]        (inline в листе Entry Tree)
Частый ключ:   sale    -> Posting Tree (B-tree по TID, тысячи страниц)
```

TID — пара (block_number, offset_number). Сравниваются лексикографически: сначала по block_number, при равенстве — по offset. `(100, 1) < (100, 2) < (200, 1) < (200, 5)`.

## Поиск: как GIN обслуживает @> и &&

Вернёмся к данным из примера. Запрос `WHERE tags @> ARRAY['ruby']` — «найти посты, содержащие 'ruby'». PostgreSQL ищет 'ruby' в Entry Tree за O(log K), где K — число уникальных элементов. Находит posting list `[TID(1,1), TID(1,3)]`. Идёт в heap за строками — результат: «Ruby Basics» и «Rails API».

Запрос `WHERE tags @> ARRAY['ruby', 'tutorial']` — «содержит И 'ruby', И 'tutorial'». Два поиска в Entry Tree:

```
ruby     -> [TID(1,1), TID(1,3)]
tutorial -> [TID(1,1), TID(1,2)]
```

Пересечение двумя указателями: оба списка начинаются с TID(1,1) — совпадение, добавляем в результат. Дальше TID(1,3) > TID(1,2), двигаем правый указатель. TID(1,2) пройден, правый список кончился. Результат: `[TID(1,1)]` — «Ruby Basics».

Запрос `WHERE tags && ARRAY['ruby', 'rails']` — «содержит хотя бы один». Два поиска:

```
ruby  -> [TID(1,1), TID(1,3)]
rails -> [TID(1,3)]
```

Объединение: TID(1,1) меньше TID(1,3) — берём из левого. TID(1,3) совпадает — берём один раз. Результат: `[TID(1,1), TID(1,3)]` — «Ruby Basics» и «Rails API».

Сложность поиска одного ключа — O(log K + P), где P — размер posting list. Для AND-запросов с m ключами: O(log K × m + merge), merge = O(P₁ + P₂ + …). Для OR — аналогично, но с объединением вместо пересечения.

## Сжатие posting lists

Каждый TID занимает 6 байт (4 байта block_number + 2 байта offset). Posting list из миллиона TID — 6 МБ. PostgreSQL использует **varbyte encoding** — кодирование дельт между соседними TID с переменной длиной байта. Поскольку TID отсортированы, дельты обычно малы:

```
Несжатый posting list:
    TID(100,1), TID(100,2), TID(100,5), TID(101,1), TID(105,3)
    6 + 6 + 6 + 6 + 6 = 30 байт

Сжатый (дельты от базы TID(100,1)):
    +1, +3, +252, +1026
    1 байт + 1 байт + 2 байта + 2 байта ≈ 10 байт
```

Малые дельты кодируются одним байтом вместо шести. Сжатие эффективнее на нефрагментированных таблицах (после [VACUUM FULL](../maintenance/00-vacuum.md) или CLUSTER), где TID идут последовательно и дельты минимальны.

## Запись: pending list как компромисс

INSERT одного товара с 200 тегами требует 200 модификаций индекса — по одной для каждого элемента. Каждая модификация — потенциальная запись страницы Entry Tree в случайное место. Это много random I/O.

**Pending list** (список ожидания, включён по умолчанию через `fastupdate = on`) решает проблему: вместо 200 записей в разные места B-tree PostgreSQL делает один sequential append в несортированный буфер.

```
INSERT: (postgresql, TID1) (gin, TID1) (index, TID1) ...
                         |
                         v
  +----------------------------------------------+
  | Pending List (несортированный, append-only)   |
  | (postgresql,TID1) (gin,TID1) (index,TID1)... |
  +----------------------------------------------+
                         |
                   слияние (batch)
                         |
                         v
  +----------------------------------------------+
  | Entry Tree + Posting Lists (основная часть)   |
  +----------------------------------------------+
```

Записи из pending list сливаются в основную структуру при переполнении буфера (`gin_pending_list_limit`, по умолчанию 4 МБ), при [VACUUM](../maintenance/00-vacuum.md), или вручную через `SELECT gin_clean_pending_list('idx_name')`. Та транзакция, которая переполнила буфер, платит за слияние всех накопленных записей.

Цена для чтения: при поиске PostgreSQL проверяет обе структуры — основной Entry Tree и весь pending list (несортированный). Для редких ключей это ощутимо: если в pending list 100 000 записей, а по основному индексу нашли бы 5 строк, почти всё время уходит на линейное сканирование буфера, где может не быть ни одного релевантного результата. Отключение fastupdate (`WITH (fastupdate = off)`) убирает этот overhead, но каждый INSERT платит полную цену записи в B-tree. Типичный выбор: fastupdate = on при write-heavy нагрузке, off — при read-heavy с критичной предсказуемостью latency.

## JSONB: два operator class'а

У товара кроме тегов есть JSONB-атрибуты: `data jsonb`. Запрос `WHERE data @> '{"color": "black"}'` — найти товары чёрного цвета. GIN индексирует JSONB через один из двух operator class'ов.

**jsonb_ops** (по умолчанию) индексирует каждый ключ и каждое значение отдельно. Поддерживает `@>` (containment), `?` (наличие ключа), `?&` (все ключи), `?|` (любой ключ). Индекс крупнее, но гибче — покрывает все типы JSONB-запросов.

**jsonb_path_ops** индексирует хеши полных путей от корня до значения. Поддерживает только `@>`, `@?`, `@@` — зато индекс компактнее (~30% меньше) и containment-запросы быстрее: хеш пути исключает ложные срабатывания по совпадению ключа из другой ветки JSON. Если в документе есть `{"shipping": {"color": "red"}}` и `{"color": "black"}`, jsonb_ops найдёт оба при поиске ключа `color`, а jsonb_path_ops различит пути.

```sql
-- Гибкий: все операторы
CREATE INDEX idx_data ON products USING gin(data);

-- Компактный: только @>
CREATE INDEX idx_data_path ON products USING gin(data jsonb_path_ops);
```

Выбор определяется типом запросов: нужен `?` (проверка наличия ключа) — jsonb_ops, только containment — jsonb_path_ops.

## Полнотекстовый поиск: от LIKE к tsvector

Магазин растёт, появляется поиск по описаниям товаров. `WHERE description LIKE '%database%'` — полный перебор таблицы (LIKE с `%` в начале не использует [B-tree](00-btree.md)), не находит «databases», «Database», не понимает словоформы: «running» и «run» — для LIKE это разные строки.

**tsvector** — представление текста как отсортированного списка лексем (нормализованных слов):

```sql
SELECT to_tsvector('english', 'The quick brown foxes are running fast');

-- Результат:
-- 'brown':3 'fast':7 'fox':4 'quick':2 'run':6
```

«The», «are» удалены (стоп-слова). «foxes» → «fox», «running» → «run» (стемминг — отсечение окончаний). Числа — позиции слов в оригинале.

**tsquery** — запрос для поиска по tsvector: `to_tsquery('english', 'running & fox')` даёт `'run' & 'fox'`. Оператор `@@` проверяет соответствие: `tsvector @@ tsquery`.

GIN индексирует лексемы из tsvector так же, как элементы массива — каждая лексема становится ключом в Entry Tree, posting list указывает на строки, содержащие эту лексему. Запрос `'run' & 'fox'` — пересечение posting lists для двух ключей, та же механика AND-запроса. Рекомендуемый подход — отдельная stored generated колонка, чтобы не вычислять tsvector при каждом запросе:

```sql
ALTER TABLE products ADD COLUMN description_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('english', description)) STORED;

CREATE INDEX idx_description_tsv ON products USING gin(description_tsv);

SELECT * FROM products
WHERE description_tsv @@ to_tsquery('english', 'lightweight & database');
```

## Составные GIN и operator classes

GIN поддерживает составные индексы: `CREATE INDEX ON products USING gin(tags, data)`. В отличие от B-tree, здесь нет правила левого префикса — каждая колонка индексируется независимо. Запрос по любой из колонок использует индекс. GIN хранит элементы из всех колонок в одном Entry Tree, помечая, из какой колонки каждый элемент.

Под капотом GIN — фреймворк, адаптируемый к типам данных через **operator class**. Operator class определяет три функции: `extractValue` разбивает значение на элементы при индексации (массив `{10, 20, 30}` → три ключа), `extractQuery` разбивает условие запроса на искомые элементы (условие `@> ARRAY[10, 30]` → ключи 10 и 30 плюс информация, что нужен AND), `consistent` проверяет, удовлетворяет ли набор найденных ключей условию. Разные operator class'ы для одного типа индексируют его по-разному — jsonb_ops и jsonb_path_ops тому пример.

GIN работает с дискретными элементами внутри составных значений. Данные без линейного порядка — геометрия, диапазоны, IP-сети — индексирует [GiST](02-gist.md).

## Sources

- PostgreSQL Documentation (пример: v16): GIN. <https://www.postgresql.org/docs/16/gin.html>
- PostgreSQL Documentation (пример: v16): Full Text Search, JSON types и JSONB operators. <https://www.postgresql.org/docs/16/textsearch.html>, <https://www.postgresql.org/docs/16/datatype-json.html>

---

← [B-tree](00-btree.md) | [GiST](02-gist.md) →
