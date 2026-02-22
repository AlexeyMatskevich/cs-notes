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

- [ ] Файловые дескрипторы (file descriptors): что это, зачем нужны, как ОС через них абстрагирует файлы/сокеты/пайпы.
- [ ] Мультиплексирование ввода-вывода (I/O multiplexing): epoll, kqueue, select — как ОС позволяет одному потоку следить за тысячами сокетов. Связь с event loop Redis (`src/ae.c`).
- [ ] `write()` vs `fsync()`/`fdatasync()`: page cache, flush, durability, почему latency `fsync` задаёт верхнюю границу throughput для “одна транзакция = один fsync” (на примерах WAL/AOF).
- [ ] Redis AOF: переписать `databases/redis/persistence/01-aof.md`, вынести объяснение `fsync`/`write()` в отдельную базовую заметку и оставить ссылку на неё.
