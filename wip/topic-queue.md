# Очередь тем

Формат: `[ ]` — тема, которую нужно покрыть отдельной заметкой или разделом.

## Shared Theory / Cross-Domain

- [ ] Теория конкурентных вычислений (рабочее название) — общая модель для случаев, где результат зависит от порядка конкурирующих операций: потоки и `race condition`, CPU/memory model и `data race`, SQL-транзакции и аномалии изоляции, распределённые системы и causal order. Нужна как опорная заметка, чтобы не объяснять одну и ту же идею по отдельности в разных разделах, а ссылаться на единый язык: события, interleaving, конфликт за общее состояние, `happens-before`, атомарность, сериализация/serializability, linearizability. Проблема, которую она решает: одна и та же причина ошибок сейчас распадается на разные локальные термины (`race condition`, `data race`, `lost update`, isolation anomalies), и нужен один общий уровень объяснения над ними. TOCTOU кажется сюда же.

## Rails + PostgreSQL

- [ ] Prepared statements в Rails (ActiveRecord): где и как используются, как связаны с пулом соединений, как влияют на планирование (generic/custom plan) и что меняют/не меняют в защите от SQL injection.

## System Design / Distributed Systems

- [ ] Failover в реальных системах: как выбирают лидера, что такое fencing, как избегают split brain (общие принципы и типовые механики).
- [ ] Как шардируют в реальных продуктах: практики и компромиссы (например, Notion и другие компании) — ближе к system design.

## PostgreSQL / Query Processing

- [ ] Селективность и CTE: при инлайнинге (PG 12+) планировщик видит статистику исходных таблиц, при материализации — нет (барьер). Перепроверить на реальных EXPLAIN: действительно ли инлайнённый CTE даёт ту же оценку rows, что и plain-запрос. Отдельно — ортогональная проблема выражений в WHERE (magic constants), которая не зависит от CTE. Возможно стоит чётко расписать разницу между этими двумя механизмами в `postgresql/query-processing/02-subqueries-and-cte.md`.

## Shared Theory / Standards

- [ ] POSIX (Portable Operating System Interface) — единое определение стандарта для всего репо. Сейчас расшифровка дублируется в 5 файлах (`ipc.md`, `signals.md`, `memory-mapping.md`, `file-io.md`, `threads.md`). Нужна одна каноническая точка (скорее всего `linux/foundations/what-is-os.md`, раздел рядом с `## Ядро`) с якорем, на который ссылаются все остальные. После создания: убрать дублирующие расшифровки, оставить `[[...#posix|POSIX]]` ссылки.

## Computer Systems / OS

- [ ] Что на самом деле значит «данные записаны»: цепочка `store buffer -> L1/L2/L3 -> когерентная видимость другим ядрам -> DRAM -> page cache/ядро -> SSD/HDD` и какие гарантии появляются на каждом шаге. Контекст вопроса: после разбора `store buffer` в `computer/cpu.md` и `computer/data-path/memory-hierarchy.md` возникла путаница между тремя разными смыслами «записано» — значение уже видно текущему потоку, его уже могут увидеть другие ядра, и оно уже durable для `COMMIT` в БД.
- [x] Файловые дескрипторы → [linux/foundations/04-file-descriptors.md](../linux/foundations/file-descriptors.md)
- [x] Мультиплексирование ввода-вывода → [linux/programming/04-io-multiplexing.md](../linux/programming/io-multiplexing.md)
- [x] `write()` vs `fsync()` → [linux/foundations/06-filesystems.md](../linux/foundations/filesystems.md) (page cache, fsync) + [linux/programming/02-file-io.md](../linux/programming/file-io.md) (O_SYNC, O_DSYNC)
- [x] ABI и размещение данных → [computer/programmer-model/01-abi-and-data-layout.md](../computer/programmer-model/abi-and-data-layout.md)
- [x] Межпроцессное взаимодействие → [linux/programming/06-ipc.md](../linux/programming/ipc.md)
- [x] Права доступа и capabilities → [linux/foundations/08-permissions-and-capabilities.md](../linux/foundations/permissions-and-capabilities.md)
- [x] Управление памятью ядра → [linux/kernel/04-memory-management.md](../linux/kernel/memory-management.md)
- [x] Redis AOF: переписать `databases/redis/persistence/01-aof.md`, вынести объяснение `fsync`/`write()` в отдельную базовую заметку и оставить ссылку на неё. (Базовые заметки теперь существуют — осталось обновить AOF.)

## Programming

- [x] Двоичное представление данных → [foundations/binary-and-bytes.md](../foundations/binary-and-bytes.md)

## Algorithms and Data Structures

- [ ] Красно-чёрное дерево (самобалансирующийся BST) — используется в ядре Linux: CFS scheduler, epoll, VMA, ext4. Связано с `algorithms-and-data-structures/non-linear/03-bst.md`.
- [ ] Ring buffer / кольцевой буфер — NIC DMA ring buffer, io_uring SQ/CQ, ext4 journal, NVMe command queues. Связано с `algorithms-and-data-structures/linear/04-stack-queue-deque.md`.
- [ ] Trie (префиксное дерево) — FIB routing table (longest prefix match) в сетевом стеке ядра.
