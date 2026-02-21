# Полнотекстовый поиск

**Предпосылки:** [SELECT и фильтрация](../querying/00-select-and-filtering.md) (LIKE), [GIN индекс](../../postgresql/indexes/01-gin.md).

Таблица `articles` хранит статьи. Задача — найти все статьи, содержащие слово «database». `WHERE body LIKE '%database%'` работает, но у подхода два недостатка: LIKE не использует индекс (полный перебор таблицы) и не понимает словоформы — строка «databases» не совпадёт с шаблоном «database». Полнотекстовый поиск PostgreSQL решает обе проблемы.

## tsvector и tsquery

Полнотекстовый поиск работает с двумя типами данных.

**tsvector** (text search vector, англ. «вектор текстового поиска») — документ, подготовленный для поиска. Текст разбивается на лексемы — нормализованные основы слов:

```sql
SELECT to_tsvector('english', 'PostgreSQL is a powerful database system');
```

```
              to_tsvector
------------------------------------------
 'databas':5 'power':4 'postgresql':1 'system':6
```

«powerful» превратилось в «power», «database» — в «databas». Это стемминг (stemming) — приведение слова к основе. Стоп-слова («is», «a») удалены — они не несут смысла для поиска. Числа после двоеточия — позиции слов в исходном тексте.

**tsquery** (text search query, англ. «запрос текстового поиска») — поисковый запрос:

```sql
SELECT to_tsquery('english', 'powerful & database');
```

```
      to_tsquery
---------------------
 'power' & 'databas'
```

Тот же стемминг. Операторы запроса: `&` — И, `|` — ИЛИ, `!` — НЕ, `<->` — слова рядом (фразовый поиск).

## Оператор @@

Оператор `@@` проверяет, совпадает ли документ с запросом:

```sql
CREATE TABLE articles (
    id    BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    body  TEXT NOT NULL
);

INSERT INTO articles VALUES
(1, 'PostgreSQL Basics', 'PostgreSQL is a powerful database system'),
(2, 'Ruby on Rails',     'Rails uses ActiveRecord for database access'),
(3, 'Rust Language',     'Rust is a systems programming language');

SELECT title FROM articles
WHERE to_tsvector('english', body) @@ to_tsquery('english', 'database');
```

```
      title
-------------------
 PostgreSQL Basics
 Ruby on Rails
```

Обе статьи содержат слово «database» (в разных формах). Третья статья не содержит — она не попала в результат.

Для комбинированного поиска по нескольким полям tsvector'ы конкатенируются оператором `||`:

```sql
SELECT title FROM articles
WHERE to_tsvector('english', title || ' ' || body)
   @@ to_tsquery('english', 'rails & database');
```

## Хранимый tsvector и индексирование

Вызов `to_tsvector()` при каждом запросе заново парсит текст каждой строки. На большой таблице это дорого. Два решения: хранимый столбец + индекс, или индекс на выражении.

### Хранимый столбец (generated column)

```sql
ALTER TABLE articles ADD COLUMN body_tsv TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', body)) STORED;

CREATE INDEX articles_body_tsv_idx ON articles USING gin (body_tsv);
```

Столбец `body_tsv` автоматически обновляется при изменении `body`. [GIN индекс](../../postgresql/indexes/01-gin.md) ускоряет поиск по оператору `@@`:

```sql
SELECT title FROM articles WHERE body_tsv @@ to_tsquery('english', 'database');
```

### Индекс на выражении

Если дополнительный столбец не нужен:

```sql
CREATE INDEX articles_body_fts_idx
ON articles USING gin (to_tsvector('english', body));
```

Запрос должен повторять выражение индекса точно:

```sql
SELECT title FROM articles
WHERE to_tsvector('english', body) @@ to_tsquery('english', 'database');
```

## Конфигурации поиска

Первый аргумент `to_tsvector` и `to_tsquery` — конфигурация (regconfig). Она определяет правила стемминга и список стоп-слов. PostgreSQL включает конфигурации для многих языков:

```sql
SELECT to_tsvector('russian', 'PostgreSQL — мощная система баз данных');
```

```
              to_tsvector
-------------------------------------------
 'баз':4 'дан':5 'мощн':2 'postgresql':1 'систем':3
```

Если конфигурация не указана, используется `default_text_search_config` (обычно `english`). Для многоязычного контента конфигурацию лучше указывать явно.

Стемминг не всегда предсказуем: «postgres» и «postgresql» стеммируются в разные основы — поиск по одному не найдёт другой. Для доменных терминов, брендов и аббревиатур, где важно точное совпадение, подходит конфигурация `simple` — она не стеммирует, только приводит к lowercase.

## Ранжирование результатов

Полнотекстовый поиск не только фильтрует, но и ранжирует результаты по релевантности.

`ts_rank(tsvector, tsquery)` возвращает числовой ранг — чем больше совпадений и чем они ближе друг к другу, тем выше ранг:

```sql
SELECT title, ts_rank(body_tsv, to_tsquery('english', 'database')) AS rank
FROM articles
WHERE body_tsv @@ to_tsquery('english', 'database')
ORDER BY rank DESC;
```

```
      title       |    rank
------------------+------------
 PostgreSQL Basics | 0.0607927
 Ruby on Rails     | 0.0607927
```

`ts_rank_cd` — вариант, учитывающий плотность совпадений (cover density).

## Вспомогательные функции

`plainto_tsquery` — автоматически объединяет слова через `&` (удобно для пользовательского ввода):

```sql
SELECT title FROM articles
WHERE body_tsv @@ plainto_tsquery('english', 'powerful database');
-- эквивалентно: to_tsquery('english', 'powerful & database')
```

`phraseto_tsquery` — фразовый поиск, слова должны идти рядом:

```sql
SELECT title FROM articles
WHERE body_tsv @@ phraseto_tsquery('english', 'database system');
```

`websearch_to_tsquery` — синтаксис в стиле Google: кавычки для фраз, `-` для исключения, `or` для ИЛИ:

```sql
SELECT title FROM articles
WHERE body_tsv @@ websearch_to_tsquery('english', 'database -rails');
```

## ts_headline — подсветка совпадений

`ts_headline` возвращает фрагмент текста с подсвеченными совпадениями:

```sql
SELECT ts_headline('english', body, to_tsquery('english', 'database'),
       'StartSel=<b>, StopSel=</b>, MaxFragments=2')
FROM articles
WHERE body_tsv @@ to_tsquery('english', 'database');
```

```
              ts_headline
---------------------------------------
 PostgreSQL is a powerful <b>database</b> system
 Rails uses ActiveRecord for <b>database</b> access
```

`ts_headline` парсит оригинальный текст заново — не использует индекс и не работает с tsvector. На 1000 результатов — 1000 парсингов полного текста. Паттерн: сначала отфильтровать и ограничить через `@@` + LIMIT в подзапросе, затем вызвать ts_headline только на финальных строках:

```sql
SELECT ts_headline('english', a.body, q, 'StartSel=<b>, StopSel=</b>')
FROM (
    SELECT id, body
    FROM articles
    WHERE body_tsv @@ websearch_to_tsquery('english', 'database')
    ORDER BY ts_rank(body_tsv, websearch_to_tsquery('english', 'database')) DESC
    LIMIT 20
) a, websearch_to_tsquery('english', 'database') q;
```

Подсветка выполняется для 20 строк вместо тысяч.

## GIN-индекс: обслуживание

GIN индекс медленнее B-tree на UPDATE и INSERT — каждое изменение tsvector обновляет инвертированный индекс. Для bulk load выгоднее удалить индекс, загрузить данные, пересоздать: три операции быстрее, чем миллион инкрементальных обновлений.

Параметр `fastupdate` (по умолчанию включён) смягчает проблему: новые записи попадают в pending list и объединяются с основным индексом batch'ами. Цена — первый запрос после накопления pending list чуть медленнее (merge происходит при чтении). Подробнее о структуре GIN — в [GIN индексе](../../postgresql/indexes/01-gin.md).

## Многоязычный поиск

Статьи на русском и английском в одной таблице. Два подхода.

Если язык известен для каждой строки (столбец `lang`), tsvector генерируется с нужной конфигурацией:

```sql
ALTER TABLE articles ADD COLUMN body_tsv TSVECTOR GENERATED ALWAYS AS (
    CASE lang
        WHEN 'ru' THEN to_tsvector('russian', body)
        WHEN 'en' THEN to_tsvector('english', body)
    END
) STORED;
```

Поиск выполняется с конфигурацией, соответствующей языку запроса. Русский запрос ищет по русским статьям, английский — по английским.

Если язык неизвестен или статья смешанная — конкатенация tsvector из двух конфигураций:

```sql
ALTER TABLE articles ADD COLUMN body_tsv TSVECTOR GENERATED ALWAYS AS (
    to_tsvector('russian', body) || to_tsvector('english', body)
) STORED;
```

Каждое слово стеммируется дважды — индекс примерно вдвое больше. Зато поиск по любому языку находит результаты без указания конфигурации.

## Sources

- PostgreSQL Documentation (v16): Full Text Search. <https://www.postgresql.org/docs/16/textsearch.html>
- PostgreSQL Documentation (v16): Text Search Types. <https://www.postgresql.org/docs/16/datatype-textsearch.html>
- PostgreSQL Documentation (v16): Text Search Functions. <https://www.postgresql.org/docs/16/functions-textsearch.html>
