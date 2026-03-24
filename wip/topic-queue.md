# Очередь тем

Формат: `[ ]` — тема, которую нужно покрыть отдельной заметкой или разделом.

## Rails + PostgreSQL

- [ ] Prepared statements в Rails (ActiveRecord): где и как используются, как связаны с пулом соединений, как влияют на планирование (generic/custom plan) и что меняют/не меняют в защите от SQL injection.

## System Design / Distributed Systems

- [ ] Failover в реальных системах: как выбирают лидера, что такое fencing, как избегают split brain (общие принципы и типовые механики).
- [ ] Как шардируют в реальных продуктах: практики и компромиссы (например, Notion и другие компании) — ближе к system design.

## PostgreSQL / Query Processing

- [ ] Селективность и CTE: при инлайнинге (PG 12+) планировщик видит статистику исходных таблиц, при материализации — нет (барьер). Перепроверить на реальных EXPLAIN: действительно ли инлайнённый CTE даёт ту же оценку rows, что и plain-запрос. Отдельно — ортогональная проблема выражений в WHERE (magic constants), которая не зависит от CTE. Возможно стоит чётко расписать разницу между этими двумя механизмами в `postgresql/query-processing/02-subqueries-and-cte.md`.

## Computer Systems / OS

- [x] Файловые дескрипторы → [linux/foundations/04-file-descriptors.md](../linux/foundations/04-file-descriptors.md)
- [x] Мультиплексирование ввода-вывода → [linux/programming/04-io-multiplexing.md](../linux/programming/04-io-multiplexing.md)
- [x] `write()` vs `fsync()` → [linux/foundations/06-filesystems.md](../linux/foundations/06-filesystems.md) (page cache, fsync) + [linux/programming/02-file-io.md](../linux/programming/02-file-io.md) (O_SYNC, O_DSYNC)
- [x] ABI и размещение данных → [computer/06-abi-and-data-layout.md](../computer/06-abi-and-data-layout.md)
- [x] Межпроцессное взаимодействие → [linux/programming/06-ipc.md](../linux/programming/06-ipc.md)
- [x] Права доступа и capabilities → [linux/foundations/08-permissions-and-capabilities.md](../linux/foundations/08-permissions-and-capabilities.md)
- [x] Управление памятью ядра → [linux/kernel/04-memory-management.md](../linux/kernel/04-memory-management.md)
- [ ] Redis AOF: переписать `databases/redis/persistence/01-aof.md`, вынести объяснение `fsync`/`write()` в отдельную базовую заметку и оставить ссылку на неё. (Базовые заметки теперь существуют — осталось обновить AOF.)

## Algorithms and Data Structures

- [ ] Красно-чёрное дерево (самобалансирующийся BST) — используется в ядре Linux: CFS scheduler, epoll, VMA, ext4. Связано с `algorithms-and-data-structures/non-linear/03-bst.md`.
- [ ] Ring buffer / кольцевой буфер — NIC DMA ring buffer, io_uring SQ/CQ, ext4 journal, NVMe command queues. Связано с `algorithms-and-data-structures/linear/04-stack-queue-deque.md`.
- [ ] Trie (префиксное дерево) — FIB routing table (longest prefix match) в сетевом стеке ядра.
