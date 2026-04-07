---
phase: research
status: draft
topic: Sidekiq — обучающая серия
files: []
---

# Research: Sidekiq

## Состояние репозитория

### Существующая заметка

`rails/sidekiq.md` — 1126 строк, 10 разделов. Написана как справочник для собеседования. Фактическая база хорошая, но:

- Заголовок "Глубокое погружение для собеседования" + раздел "Типичные вопросы на собеседовании" — нарушение правила no interview framing
- Нет блока `Предпосылки`
- Нет мотивации ("зачем вообще нужна фоновая обработка?")
- 1126 строк в одном файле при норме 80-150 для серии
- OSS и Pro перемешаны без разделения
- Структура — энциклопедия, не нарратив (feature-list arc)
- Ссылки на зависимости есть, но бессистемные

### Структура `rails/`

```
rails/
├── redis/
│   ├── index.md
│   ├── 00-clients-and-connections.md
│   ├── 01-data-structures-in-practice.md
│   ├── 02-blocking-pitfalls.md
│   └── practice/
└── sidekiq.md          ← будет заменён на sidekiq/
```

Нет `rails/index.md` — нужно создать при реорганизации.

### Смежные заметки (с оценкой)

| Заметка | Что покрывает | Качество | Роль для Sidekiq |
|---------|--------------|----------|------------------|
| `databases/redis/data-structures/02-list.md` | LIST, BRPOP, O(1) | Хорошая | Фундамент: как работают очереди |
| `databases/redis/patterns/03-queues.md` | Простая → reliable → delayed → Streams | Образцовая | Фундамент: паттерны очередей в Redis |
| `ruby/ruby-concurrency.md` | GVL, I/O overlap, Thread vs Fiber | Хорошая | Объясняет почему Sidekiq эффективен |
| `system-design/08-delivery-guarantees.md` | at-least/at-most/exactly-once | Хорошая | Контракт Sidekiq |
| `system-design/06-reliability-patterns.md` | Retry, idempotency, timeout, circuit breaker | Хорошая | Паттерны надёжности |
| `system-design/09-message-queues.md` | Temporal decoupling, ACK, point-to-point | Хорошая | Мотивация: зачем нужны очереди |
| `linux/programming/00-signals.md` | SIGTERM, SIGINT, обработчики | Хорошая | Signals и graceful shutdown |
| `linux/foundations/03-threads.md` | Потоки ОС, shared memory | Хорошая | Модель concurrency |
| `rails/redis/00-clients-and-connections.md` | Connection pool, конфигурация | Хорошая | Практика подключений |
| `rails/redis/practice/list-background-queue.md` | Простая очередь на LIST | Хорошая | Предшественник: "руками" то, что делает Sidekiq |
| `databases/postgresql/concurrency/06-queues-and-skip-locked.md` | Очереди в PostgreSQL | Хорошая | Альтернатива: зачем Redis, а не БД? |

### Пробелы

- Нет обучающего материала "что такое background processing и зачем"
- Нет сравнения подходов (DB queue vs Redis queue vs message broker)
- Нет объяснения "почему именно так устроен Sidekiq" (причинно-следственные связи)
- Серия `rails/redis/` ссылается на `sidekiq.md`, но ссылки станут битыми при реорганизации

## Зависимости

### Кандидаты в предпосылки серии (index.md)

Лёгкий набор — читатель знает Rails, но не знает background jobs:

- `programming/` — базовые концепции (подразумеваются, не перечисляются)
- Ruby/Rails — подразумеваются как baseline серии

### Предпосылки конкретных файлов (per-file)

| Файл серии (предварительно) | Предпосылки |
|----------------------------|-------------|
| Мотивация + архитектура | Нет (вводная) |
| Как работает (lifecycle, Redis) | [Redis Lists](../databases/redis/data-structures/02-list.md), [Очереди в Redis](../databases/redis/patterns/03-queues.md) |
| Гарантии + идемпотентность | [Гарантии доставки](../system-design/08-delivery-guarantees.md), [Reliability patterns](../system-design/06-reliability-patterns.md) |
| Retry + error handling | Предыдущие файлы серии |
| Signals + deploy | [Сигналы](../linux/programming/00-signals.md) |
| Concurrency + масштабирование | [Ruby concurrency](../ruby/ruby-concurrency.md), [Потоки](../linux/foundations/03-threads.md) |

### Каскадные обновления

| Файл | Что менять |
|------|-----------|
| `rails/redis/index.md` | Обновить ссылки на `sidekiq.md` → `sidekiq/` |
| `rails/redis/practice/list-background-queue.md` | Проверить ссылки |
| `databases/redis/patterns/03-queues.md` | Обновить cross-link на Sidekiq |
| `system-design/09-message-queues.md` | Добавить cross-link на Sidekiq как конкретную реализацию |
| `CLAUDE.md` | Обновить file map (rails/ описание) |
| Создать `rails/index.md` | Новый файл — карта Rails-материалов |

## Характеристики

- **Слой знания:** технология / прикладной (Sidekiq — конкретный инструмент, но объяснение опирается на фундаментальные концепции из system-design и redis)
- **Scope:**
  - IN: мотивация background processing, архитектура Sidekiq, жизненный цикл job, гарантии и идемпотентность, retry и error handling, signals и deploy, middleware, масштабирование (concurrency, processes, queues), Pro/Enterprise фичи (в `<details>`), тестирование (fake/inline/disable), ActiveJob vs Sidekiq::Job (секция), Transactional Push, IterableJob, Capsules
  - OUT: Embedded Mode, Sidekiq 8 profiling (нишевые), Resque/DelayedJob (краткое упоминание при мотивации, не отдельная тема), написание production monitoring/alerting, специфика Kubernetes deployment

## Внешние источники

### Архитектура (точно известно, из документации)

**Три роли системы:**
- **Client** (Rails app) — сериализует вызов метода в JSON, отправляет через client middleware, LPUSH в Redis list
- **Broker** (Redis) — хранит очереди (List), расписание (Sorted Set), retry (Sorted Set), dead (Sorted Set), метаданные процессов (Hash, Set)
- **Server** (Sidekiq process) — многопоточный процесс: Launcher → Manager(s) → Processor(s), + Poller thread, + Heartbeat thread

**Структуры данных Redis:**

| Структура | Ключ | Назначение |
|-----------|------|-----------|
| List | `queue:<name>` | Рабочие очереди. LPUSH/BRPOP |
| Sorted Set | `schedule` | Отложенные jobs (score = timestamp) |
| Sorted Set | `retry` | Jobs на повторную попытку (score = время retry) |
| Sorted Set | `dead` | Dead letter queue (max 10000, TTL 6 мес) |
| Set | `queues` | Индекс имён очередей |
| Set | `processes` | ID активных Sidekiq-процессов |
| Hash | `<identity>` | Метаданные процесса (hostname, pid, concurrency, busy, beat) |

**Fetch-механизмы:**
- BasicFetch (OSS): `BRPOP` с timeout 2 сек. Job удаляется из Redis до начала выполнения.
- SuperFetch (Pro): `LMOVE` в приватную очередь процесса. Job остаётся в Redis до acknowledge.

**Retry:** `delay = (retry_count ** 4) + 15 + (rand(10) * (retry_count + 1))`. 25 retry ≈ 20 дней. Степень 4 (а не 2) — агрессивный backoff, чтобы дать время на deploy фикса. Jitter — предотвращение thundering herd при массовых retry.

**Poller:** периодически проверяет `schedule` и `retry` sorted sets. Lua-скрипт для атомарного ZRANGE+ZREM. Интервал масштабируется с числом процессов (anti-thundering-herd).

**Signals:** TSTP (quiet), TERM/INT (shutdown с timeout), TTIN (backtrace). Self-pipe trick для безопасной обработки сигналов.

**Capsules (7.0+):** изолированная группа настроек внутри процесса. Свой concurrency и набор очередей. Manager создаётся per-capsule.

**Transactional Push (7.2+):** `Sidekiq.transactional_push!` — jobs отправляются в Redis только после commit ActiveRecord-транзакции.

**IterableJob (7.3+):** cursor-based итерация для long-running jobs. При shutdown сохраняет cursor, перезапускается с сохранённого места.

### Типичные заблуждения

1. **"Exactly-once execution"** — нет, at-least-once. Job может выполниться повторно при: retry, crash+orphan recovery (Pro), requeue при hard shutdown.
2. **"FIFO порядок"** — Redis list = FIFO, но при concurrency > 1 потоки обрабатывают параллельно. Порядок завершения не гарантирован.
3. **"Retry безопасен для любой задачи"** — только при идемпотентности. `balance += 100` при retry удвоит сумму.
4. **"perform_async внутри транзакции — ок"** — антипаттерн. Job попадает в Redis до commit. При rollback — job обрабатывает несуществующие данные.
5. **"Можно передавать Ruby-объекты"** — нет, JSON.dump/parse. ActiveRecord → `"#<User:0x...>"`, Symbol → String, Time → String.
6. **"Больше потоков = быстрее"** — не для CPU-bound из-за GVL. Для I/O-bound — да (I/O overlap). Больше потоков → memory fragmentation.
7. **"ActiveJob — правильный способ"** — trade-off: абстракция + GlobalID, но ~30% overhead, несовместимость с Batches (Pro), ограниченный контроль retry.

### Edge cases

- **Crash mid-job (OSS):** BRPOP удалил job, процесс убит (SIGKILL/OOM) → job потерян навсегда. Pro решает через LMOVE + orphan recovery.
- **Redis down при requeue:** SIGTERM → bulk_requeue → Redis недоступен → jobs потеряны.
- **Redis eviction policy:** если не `noeviction`, Redis может удалить ключи очередей под давлением памяти.
- **Deploy без TSTP:** только TERM → мало времени → long-running jobs прерваны и requeued (дублирование).
- **Job завершился, Redis crashed до acknowledge (Pro):** job остаётся orphan → повторное выполнение → нужна идемпотентность.

### Авторитетные источники

- [Sidekiq Wiki (GitHub)](https://github.com/sidekiq/sidekiq/wiki) — основная документация
- [Mike Perham — How does Sidekiq work?](https://www.mikeperham.com/how-sidekiq-works/) — глубокое погружение в архитектуру
- [Mike Perham — Sidekiq 7.0 Beta](https://www.mikeperham.com/2022/09/27/sidekiq-7.0-beta-now-available/) — Capsules, embedded mode
- [Mike Perham — Iteration and Sidekiq 7.3.0](https://www.mikeperham.com/2024/07/03/iteration-and-sidekiq-7.3.0/) — IterableJob
- [Mike Perham — Introducing Sidekiq 8.0](https://www.mikeperham.com/2025/03/05/introducing-sidekiq-8.0/) — profiling, metrics
- [Dan Svetlov — Sidekiq Internals](https://dansvetlov.me/sidekiq-internals/) — разбор исходного кода
- [Sidekiq Redis Data Model](https://hype08.github.io/gradual-notes/thoughts/Sidekiq-Redis-Data-Model) — визуализация данных в Redis
- [Active Job Basics (Rails Guides)](https://edgeguides.rubyonrails.org/active_job_basics.html) — Rails-интерфейс

## Видение автора

### Аудитория
Читатель знает Ruby и Rails, но никогда не работал с background jobs. Серия начинается с мотивации "зачем", выводит на глубину постепенно.

### Нарративная дуга (направление, финализация на design-фазе)
Предложенная 7-шаговая тематическая дуга:
1. **Зачем** — мотивация (HTTP-запрос не должен ждать email/платёж), temporal decoupling
2. **Из чего состоит** — три роли (client/broker/server), Redis как backbone
3. **Как работает** — жизненный цикл job: от `perform_async` до завершения
4. **Что может пойти не так** — потери, дублирование, at-least-once → идемпотентность
5. **Как управлять** — retry, signals, shutdown, deploy
6. **Как расширять** — middleware, масштабирование, capsules
7. **Продвинутое** — тестирование, best practices

Каждый шаг создаёт потребность в следующем. Файловая нарезка — следствие дуги (решение на design-фазе).

### Решения по scope
- **Pro/Enterprise фичи:** полноценное раскрытие, но в `<details>` dropdowns
- **Q&A раздел:** убрать полностью, полезный контент растворить в нарративе
- **Тестирование:** отдельный файл в конце серии
- **ActiveJob vs Sidekiq::Job:** секция в одном из файлов (trade-off: абстракция vs контроль)
- **Новые фичи (7-8):** Transactional Push, IterableJob, Capsules — включить. Embedded Mode, Sidekiq 8 profiling — за scope
- **Предпосылки:** лёгкие для серии целиком (Ruby/Rails), тяжёлые per-file (Redis, signals, concurrency)

### Принципы написания
- Причинно-следственные связи: не только "формула retry delay", но *почему* степень 4 и *зачем* jitter
- Pro-фичи в dropdown — полезно для понимания landscape и принятия решений
- Существующая заметка — ценный источник фактов и примеров кода, но структура и фрейминг переписываются полностью
- Интеграция с репозиторием: ссылки на Redis, system-design, ruby, linux — не дублирование, а cross-links
- Нужен `rails/index.md` как карта Rails-материалов
