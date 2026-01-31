# Алгоритмы и структуры данных

**Предпосылки:** базовые понятия программирования (переменные, типы данных, условия, циклы, функции), указатели/ссылки и оценка сложности в O(…).

В этих структурах почти всё сводится к двум вопросам:
1. По чему ищем элемент: по позиции (индекс) или по ключу?
2. Чем платим за скорость: сдвигами и копированием, лишними указателями, промахами кэша CPU, блокировками?

## Техники

0. [Динамическое программирование (DP)](techniques/00-dynamic-programming.md)

## Линейные структуры

Типичный путь выбора: массив → динамический массив → связный список → ограниченные интерфейсы (stack/queue/deque) → хеш‑таблица → кэши с вытеснением (LRU/LFU/clock‑sweep).

0. [Абстрактный тип данных (ADT)](linear/00-adt.md)
1. [Массив](linear/01-array.md)
2. [Динамический массив](linear/02-dynamic-array.md)
3. [Связный список](linear/03-linked-list.md)
4. [Стек, очередь, дек](linear/04-stack-queue-deque.md)
5. [Хеш-таблица](linear/05-hash-table.md)
6. [LRU-кэш](linear/06-lru-cache.md)
7. [Clock-Sweep](linear/07-clock-sweep.md)

## Нелинейные структуры

Все линейные структуры хранят элементы в последовательности — по позиции или по ключу. Но когда в данных есть иерархии, сети или маршруты, нужны связи "многие ко многим" или "один ко многим". Граф — обобщение, дерево и куча — его частные случаи с более сильными гарантиями.

0. [Граф](non-linear/00-graph.md)
1. [Дерево](non-linear/01-tree.md)
2. [Бинарное дерево](non-linear/02-binary-tree.md)
3. [Двоичное дерево поиска (BST)](non-linear/03-binary-search-tree.md)
4. [Куча (Heap)](non-linear/04-heap.md)
5. [B-дерево (B-tree)](non-linear/05-b-tree.md)
6. [B+ дерево (B+ tree)](non-linear/06-b-plus-tree.md)
7. [B* дерево (B* tree)](non-linear/07-b-star-tree.md)
8. [Инвертированный индекс (Inverted Index)](non-linear/08-inverted-index.md)
9. [Skip List](non-linear/09-skip-list.md)

## Выбор структуры

- Нужно часто проверять "есть ли ребро между i и j" → матрица смежности.
- Граф разреженный и важны обходы соседей → списки смежности.
- Нужна иерархия без циклов → дерево.
- Нужны быстрые `search/insert/delete` по упорядоченному ключу → BST (если важны гарантии, лучше самобалансирующееся).
- Нужна приоритетная очередь (добавить элемент и извлечь min/max) → куча.
- Поиск по ключу на диске → B-дерево / B+ дерево.
- Поиск внутри составных значений (массивы, тексты) → инвертированный индекс.
- Упорядоченное множество с O(log n) без балансировки → skip list.

## Сводные таблицы

### Массив vs Связный список

| Операция | Массив | Односвязный список | Двусвязный список |
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

### ADT: Стек, Очередь, Дек

| ADT | Порядок | Операции | Лучшая реализация |
|-----|---------|----------|-------------------|
| Стек | LIFO | push/pop с одного конца | Динамический массив |
| Очередь | FIFO | enqueue в конец, dequeue из начала | Ring buffer |
| Дек | Оба | Все операции с обоих концов | Ring buffer или двусвязный список |

### Хеш-таблица

| Операция | В среднем | В худшем |
|----------|-----------|----------|
| get | O(1) | O(n) |
| put | O(1)* | O(n) |
| delete | O(1) | O(n) |

`*` — амортизировано

### LRU-кэш

| Операция | Время | Структуры |
|----------|-------|-----------|
| get | O(1) | Хеш-таблица + двусвязный список |
| put | O(1) | Хеш-таблица + двусвязный список |

### LFU vs LRU

| Аспект | LRU | LFU |
|--------|-----|-----|
| Критерий вытеснения | Время последнего обращения | Количество обращений |
| Cache pollution | Нет | Да (старые популярные элементы застревают) |
| Адаптация к изменениям | Быстрая | Медленная |
| Лучше для | Меняющиеся паттерны доступа | Стабильные паттерны доступа |

### Clock-Sweep vs LRU vs LFU

| Аспект | LRU | LFU | Clock-Sweep |
|--------|-----|-----|-------------|
| Критерий | Время | Частота | Частота + затухание |
| Точность | Точный порядок | Точный счётчик | Приблизительный |
| Cache pollution | Нет | Да | Нет (затухание) |
| Contention | При каждом обращении | При каждом обращении | Только при вытеснении |
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
