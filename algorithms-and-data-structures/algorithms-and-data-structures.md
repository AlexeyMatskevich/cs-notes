---
tags:
  - domain/algorithms
  - theme/storage
  - theme/performance
  - type/overview
aliases:
  - algorithms
  - data structures
order: 0
---

# Алгоритмы и структуры данных

**Предпосылки:** [базовое программирование](../programming/programming.md) (переменные, типы, условия, циклы, функции, [указатели/ссылки](../programming/memory.md)) и оценка сложности в O(…).

Выбор структуры данных почти всегда сводится к двум вопросам:
1. Как находим элемент — по позиции (индекс), по ключу или по связям с другими элементами?
2. Чем платим за скорость — сдвигами и копированием при вставке, лишней памятью под ссылки, тем, как данные ложатся в кеш процессора (быстрая память рядом с ядром), а в многопоточном коде — ожиданием на блокировках (когда потоки конкурируют за общий ресурс)?

Линейные структуры отвечают на первый вопрос через позицию или ключ. Нелинейные добавляют третий способ — поиск по связям между элементами, когда в данных есть иерархии, сети или маршруты. Техники в конце — это уже не контейнеры, а приёмы, которые используют и те, и другие.

## Линейные структуры

Типичный путь выбора: [[algorithms-and-data-structures/linear/array|массив]] → [[algorithms-and-data-structures/linear/dynamic-array|динамический массив]] → [[algorithms-and-data-structures/linear/linked-list|связный список]] → ограниченные интерфейсы ([[algorithms-and-data-structures/linear/stack-queue-deque|стек/очередь/дек]]) → [[algorithms-and-data-structures/linear/hash-table|хеш‑таблица]] → кэши с вытеснением ([[algorithms-and-data-structures/linear/lru-cache|LRU]]/LFU/[[algorithms-and-data-structures/linear/clock-sweep|clock‑sweep]]).

0. [[algorithms-and-data-structures/linear/adt|Абстрактный тип данных (ADT)]] — тип как контракт операций, отделённый от реализации
1. [[algorithms-and-data-structures/linear/array|Массив]] — непрерывный блок памяти: доступ по индексу за O(1), цена — фиксированный размер
2. [[algorithms-and-data-structures/linear/dynamic-array|Динамический массив]] — рост через удвоение ёмкости, амортизированный O(1) на добавление в конец
3. [[algorithms-and-data-structures/linear/linked-list|Связный список]] — узлы со ссылками: вставка/удаление за O(1), цена — нет доступа по индексу
4. [[algorithms-and-data-structures/linear/stack-queue-deque|Стек, очередь, дек]] — ограниченные интерфейсы доступа: LIFO, FIFO, оба конца
5. [[algorithms-and-data-structures/linear/hash-table|Хеш-таблица]] — поиск по ключу за O(1) в среднем через хеш-функцию; цена — коллизии и деградация
6. [[algorithms-and-data-structures/linear/lru-cache|LRU-кэш]] — вытеснение давно неиспользованного за O(1) на хеш-таблице и двусвязном списке
7. [[algorithms-and-data-structures/linear/clock-sweep|Clock-Sweep]] — приближение LRU без конкуренции потоков при каждом обращении

## Нелинейные структуры

Все линейные структуры хранят элементы в последовательности — по позиции или по ключу. Но когда в данных есть иерархии, сети или маршруты, нужны связи «многие ко многим» или «один ко многим». [[algorithms-and-data-structures/non-linear/graph|Граф]] — самый общий случай; [[algorithms-and-data-structures/non-linear/tree|дерево]] — его частный случай (связный, без циклов), а [[algorithms-and-data-structures/non-linear/heap|куча]] — уже частный случай дерева (плюс свойство кучи: родитель не больше или не меньше детей).

0. [[algorithms-and-data-structures/non-linear/graph|Граф]] — связи «многие ко многим»: матрица против списков смежности и цена памяти
1. [[algorithms-and-data-structures/non-linear/tree|Дерево]] — иерархия без циклов: корень, узлы, листья
2. [[algorithms-and-data-structures/non-linear/binary-tree|Бинарное дерево]] — не больше двух детей; обходы (in/pre/post-order, по уровням)
3. [[algorithms-and-data-structures/non-linear/binary-search-tree|Двоичное дерево поиска (BST)]] — упорядоченный поиск/вставка/удаление за O(h); цена — вырождение
4. [[algorithms-and-data-structures/non-linear/heap|Куча (Heap)]] — приоритетная очередь: извлечение min/max за O(log n) на массиве
5. [[algorithms-and-data-structures/non-linear/b-tree|B-дерево (B-tree)]] — много ключей в узле под размер страницы диска: меньше чтений с диска
6. [[algorithms-and-data-structures/non-linear/b-plus-tree|B+ дерево (B+ tree)]] — все данные в листьях, листья связаны: быстрый диапазонный скан
7. [[algorithms-and-data-structures/non-linear/b-star-tree|B* дерево (B* tree)]] — плотнее заполненные узлы за счёт перераспределения перед разбиением
8. [[algorithms-and-data-structures/non-linear/inverted-index|Инвертированный индекс (Inverted Index)]] — поиск внутри составных значений: термин → список документов
9. [[algorithms-and-data-structures/non-linear/skip-list|Skip List]] — упорядоченное множество за O(log n) на вероятностных уровнях, без балансировки

## Техники

Эти две заметки — не контейнеры, а приёмы поверх уже изученных структур, поэтому читаются последними: динамическое программирование опирается на [[algorithms-and-data-structures/linear/array|массив]] и [[algorithms-and-data-structures/linear/hash-table|хеш-таблицу]], а cache-aware алгоритмы — на [[algorithms-and-data-structures/non-linear/b-tree|B-дерево]] и иерархию памяти.

0. [[algorithms-and-data-structures/techniques/dynamic-programming|Динамическое программирование (DP)]] — таблица ответов на перекрывающиеся подзадачи вместо повторного пересчёта
1. [[algorithms-and-data-structures/techniques/cache-aware-algorithms|Cache-aware алгоритмы]] — учёт кеш-линий и локальности: tiling, AoS vs SoA, B-tree как cache-aware структура

## Выбор структуры

- Нужно часто проверять «есть ли ребро между i и j» → матрица смежности (таблица V×V, в ячейке — есть ли ребро).
- [[algorithms-and-data-structures/non-linear/graph|Граф]] разреженный и важны обходы соседей → списки смежности (у каждой вершины — список её соседей).
- Нужна иерархия без циклов → [[algorithms-and-data-structures/non-linear/tree|дерево]].
- Нужны быстрые `search/insert/delete` по упорядоченному ключу → [[algorithms-and-data-structures/non-linear/binary-search-tree|BST]] (если важны гарантии, лучше самобалансирующееся).
- Нужна приоритетная очередь (добавить элемент и извлечь min/max) → [[algorithms-and-data-structures/non-linear/heap|куча]].
- Поиск по ключу на диске → [[algorithms-and-data-structures/non-linear/b-tree|B-дерево]] / [[algorithms-and-data-structures/non-linear/b-plus-tree|B+ дерево]].
- Поиск внутри составных значений (массивы, тексты) → [[algorithms-and-data-structures/non-linear/inverted-index|инвертированный индекс]].
- Упорядоченное множество с O(log n) без балансировки → [[algorithms-and-data-structures/non-linear/skip-list|skip list]].

## Сводные таблицы

### [[algorithms-and-data-structures/linear/array|Массив]] vs [[algorithms-and-data-structures/linear/linked-list|Связный список]]

| Операция | [[algorithms-and-data-structures/linear/array\|Массив]] | Односвязный [[algorithms-and-data-structures/linear/linked-list\|список]] | Двусвязный [[algorithms-and-data-structures/linear/linked-list\|список]] |
|----------|--------|-------------------|-------------------|
| Доступ по индексу | O(1) | O(n) | O(n) |
| Поиск по значению | O(n) | O(n) | O(n) |
| Вставка в начало | O(n) | O(1) | O(1) |
| Вставка в конец | O(1)* | O(1)** | O(1)** |
| Вставка в середину | O(n) | O(1)*** | O(1)*** |
| Удаление из начала | O(n) | O(1) | O(1) |
| Удаление из конца | O(1) | O(n) | O(1)** |
| Удаление из середины | O(n) | O(1)*** | O(1)*** |

`*` — амортизировано
`**` — при наличии tail указателя
`***` — если уже есть указатель на место; иначе +O(n) на поиск

### ADT: [[algorithms-and-data-structures/linear/stack-queue-deque|Стек, Очередь, Дек]]

| ADT | Порядок | Операции | Лучшая реализация |
|-----|---------|----------|-------------------|
| [[algorithms-and-data-structures/linear/stack-queue-deque\|Стек]] | LIFO | push/pop с одного конца | [[algorithms-and-data-structures/linear/dynamic-array\|Динамический массив]] |
| [[algorithms-and-data-structures/linear/stack-queue-deque\|Очередь]] | FIFO | enqueue в конец, dequeue из начала | Кольцевой буфер (ring buffer) |
| [[algorithms-and-data-structures/linear/stack-queue-deque\|Дек]] | Оба | Все операции с обоих концов | Кольцевой буфер или двусвязный [[algorithms-and-data-structures/linear/linked-list\|список]] |

### [[algorithms-and-data-structures/linear/hash-table|Хеш-таблица]]

| Операция | В среднем | В худшем |
|----------|-----------|----------|
| get | O(1) | O(n) |
| put | O(1)* | O(n) |
| delete | O(1) | O(n) |

`*` — амортизировано

### [[algorithms-and-data-structures/linear/lru-cache|LRU-кэш]]

| Операция | Время | Структуры |
|----------|-------|-----------|
| get | O(1) | [[algorithms-and-data-structures/linear/hash-table\|Хеш-таблица]] + двусвязный [[algorithms-and-data-structures/linear/linked-list\|список]] |
| put | O(1) | [[algorithms-and-data-structures/linear/hash-table\|Хеш-таблица]] + двусвязный [[algorithms-and-data-structures/linear/linked-list\|список]] |

### LFU vs [[algorithms-and-data-structures/linear/lru-cache|LRU]]

| Аспект | [[algorithms-and-data-structures/linear/lru-cache\|LRU]] | LFU |
|--------|-----|-----|
| Критерий вытеснения | Время последнего обращения | Количество обращений |
| Засорение кеша (cache pollution) | Нет | Да (старые популярные элементы застревают) |
| Адаптация к изменениям | Быстрая | Медленная |
| Лучше для | Меняющиеся паттерны доступа | Стабильные паттерны доступа |

### [[algorithms-and-data-structures/linear/clock-sweep|Clock-Sweep]] vs [[algorithms-and-data-structures/linear/lru-cache|LRU]] vs LFU

| Аспект | [[algorithms-and-data-structures/linear/lru-cache\|LRU]] | LFU | [[algorithms-and-data-structures/linear/clock-sweep\|Clock-Sweep]] |
|--------|-----|-----|-------------|
| Критерий | Время | Частота | Частота + затухание |
| Точность | Точный порядок | Точный счётчик | Приблизительный |
| Засорение кеша | Нет | Да | Нет (затухание) |
| Конкуренция потоков (contention) | При каждом обращении | При каждом обращении | Только при вытеснении |
| Масштабируемость | Хуже | Хуже | Лучше |

## Sources

- Bayer, R., McCreight, E. *Organization and Maintenance of Large Ordered Indices*, 1972.
- Knuth, D. *The Art of Computer Programming*, Vol. 3: Sorting and Searching.
- OpenJDK (например, JDK 21): `java.util.ArrayList` (`grow`). <https://github.com/openjdk/jdk/blob/jdk21u/src/java.base/share/classes/java/util/ArrayList.java>
- CPython (например, Python 3.12): over-allocation списка. <https://github.com/python/cpython/blob/v3.12.0/Objects/listobject.c>
- Go (например, Go 1.22): рост `slice`. <https://github.com/golang/go/blob/go1.22.0/src/runtime/slice.go>
- PostgreSQL (например, 16): clock-sweep / `BM_MAX_USAGE_COUNT`. <https://github.com/postgres/postgres/blob/REL_16_0/src/include/storage/buf_internals.h> и <https://github.com/postgres/postgres/blob/REL_16_0/src/backend/storage/buffer/freelist.c>
- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms* (CLRS), 4th ed.
- Pugh, W. *Skip Lists: A Probabilistic Alternative to Balanced Trees*, 1990.
- Wikipedia: [Graph (discrete mathematics)](https://en.wikipedia.org/wiki/Graph_(discrete_mathematics)), [Tree (graph theory)](https://en.wikipedia.org/wiki/Tree_(graph_theory)), [Binary heap](https://en.wikipedia.org/wiki/Binary_heap)
