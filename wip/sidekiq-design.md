---
phase: design
status: approved
topic: Sidekiq — обучающая серия
files:
  - rails/sidekiq/index.md
  - rails/sidekiq/00-architecture.md
  - rails/sidekiq/01-job-lifecycle.md
  - rails/sidekiq/02-guarantees.md
  - rails/sidekiq/03-retry-and-errors.md
  - rails/sidekiq/04-signals-and-deploy.md
  - rails/sidekiq/05-job-design.md
  - rails/sidekiq/06-concurrency-and-scaling.md
  - rails/sidekiq/07-testing.md
  - rails/index.md
---

# Design: Sidekiq

## Черновик объяснения

**Объяснение.** Читатель построил простую очередь на LPUSH+BRPOP руками (list-background-queue.md). Он знает паттерны: reliable queue (LMOVE), delayed queue (ZSET), retry с backoff + jitter, сигналы для graceful shutdown, потоки для I/O overlap. Но он никогда не видел, как эти паттерны собираются в одну систему. Sidekiq — эта система. На каждом стыке — конкретное решение с конкретным trade-off. Объяснение строится как прослеживание знакомых паттернов через конкретные решения Sidekiq.

**Главная сложность.** Читатель может считать Sidekiq обёрткой над LPUSH+BRPOP. Настоящая трудность — увидеть взаимодействие паттернов как системы: retry влияет на сигналы, сигналы на deploy, deploy на идемпотентность, дизайн jobs на retry. И на каждом стыке — конкретный trade-off (почему BRPOP а не LMOVE в OSS? почему степень 4 в retry? зачем TSTP перед TERM?).

**Момент понимания.** Когда читатель прослеживает job от `perform_async` до завершения И до отказа, и на каждом шаге узнаёт знакомый паттерн: «BRPOP — это простая очередь из redis/patterns, поэтому OSS теряет job при crash. LMOVE — reliable queue, поэтому Pro существует. retry sorted set — delayed queue с ZSET. Poller — monitor-процесс. Capsules — bulkhead. TSTP → TERM — graceful shutdown из linux/signals.»

## Перспектива читателя

### Ментальная модель

Читатель собрал картинку из фрагментов в предпосылках:
- message-queues.md: «воркеры конкурируют за задачи, 25 retry за 21 день»
- ruby-concurrency.md: «процессы и потоки, задачи из Redis, thread pool»
- redis clients: «Sidekiq = Redis с noeviction + RDB»

Модель: «отдельный процесс (или несколько), который тянет jobs из Redis, выполняет в потоках, повторяет при ошибках. Production-версия моего EmailWorker.»

### Ключевые вопросы читателя

1. BRPOP удаляет до выполнения. Sidekiq использует LMOVE? Какая гарантия? ← **Центральный момент 02-guarantees.md**
2. Как retry откладывает попытку на 10 минут, потом на часы? ZSET? ← **Подтвердить связь в 03-retry.md**
3. GVL + thread pool — jobs конкурентны только при I/O? ← **05-concurrency.md**
4. Что происходит с job при SIGTERM? ← **04-signals.md**
5. Что такое «job» в Sidekiq — Ruby-класс? Hash в Redis? ← **Определить в 00-architecture.md**

### Расхождения с черновиком

- Читатель правильно угадывает retry = ZSET pattern → подтвердить связь явно
- Термины «job», «worker» не определены → определить в файле 00
- Crash-recovery — главный вопрос → центральный момент в файле 02
- noeviction reasoning → включить в Redis data model (файл 00)

## Грубый эскиз

- **Домен:** `rails/sidekiq/`
- **Слой знания:** технология / прикладной
- **Scope:** серия из 8 файлов + index.md
- **Пол:** Redis queue patterns, Ruby concurrency, reliability patterns (в предпосылках)
- **Потолок:** production monitoring setup, Kubernetes deployment, исходники Sidekiq построчно, сравнение с Resque/DelayedJob

## Педагогический дизайн

### Граница знаний

**Читатель знает** (из предпосылок):

| Концепция | Источник |
|-----------|---------|
| Temporal decoupling, ACK, point-to-point, DLQ, backpressure | system-design/09-message-queues.md |
| At-least-once, exactly-once = idempotency | system-design/08-delivery-guarantees.md |
| Retry с backoff + jitter, circuit breaker, bulkhead, idempotency key | system-design/06-reliability-patterns.md |
| Redis LIST, BRPOP, FIFO queue | databases/redis/data-structures/02-list.md |
| Simple queue (BRPOP), reliable queue (LMOVE), delayed queue (ZSET) | databases/redis/patterns/03-queues.md |
| SIGTERM, SIGTSTP, graceful shutdown, self-pipe trick | linux/programming/00-signals.md |
| Потоки ОС, shared memory, mutex, race conditions | linux/foundations/03-threads.md |
| GVL, I/O overlap, Puma architecture | ruby/ruby-concurrency.md |
| connection_pool, Redis instances (Sidekiq = noeviction) | rails/redis/00-clients-and-connections.md |
| Hand-built LPUSH+BRPOP queue | rails/redis/practice/list-background-queue.md |

**Читатель НЕ знает:**

- Трёхролевая архитектура Sidekiq (client / broker / server)
- Внутренности сервера (Launcher → Manager → Processor + Poller + Heartbeat)
- JSON-сериализация и ограничения (почему нельзя Ruby-объекты)
- Client/server middleware pipeline
- BasicFetch (BRPOP) vs SuperFetch (LMOVE) — конкретная инстанциация
- Формула retry (степень 4 + jitter), почему именно так
- Redis data model (конкретные ключи и структуры)
- TSTP как «quiet» для deploy
- IterableJob, Capsules, Transactional Push, Batches
- Job design: атомарность, fan-out, композиция
- ActiveJob vs Sidekiq::Job trade-off
- Тестирование (fake/inline/disable)

### Мотивация

Простая очередь на LIST+BRPOP из предыдущей практики обрабатывает email: LPUSH кладёт задачу, BRPOP забирает, воркер обрабатывает. Но цикл обслуживает один тип задачи с одним поведением. В реальном приложении их десятки — email, resize картинок, платёжная сверка, аналитика — каждый со своими требованиями к retry, приоритету и обработке ошибок. Собирать это руками — писать собственный фреймворк. Sidekiq — готовый фреймворк, который собирает знакомые паттерны (Redis-очереди, retry с backoff, сигналы для shutdown, потоки для I/O overlap) в одну систему.

### Точка входа

Простая очередь из предыдущей практики работает: LPUSH добавляет задачу, BRPOP забирает, воркер обрабатывает. Но цикл обслуживает один тип задачи с одним поведением. Добавь resize картинок — нужен второй цикл или роутинг. Добавь retry — воркер ловит исключения, считает задержку, пишет в sorted set. Добавь graceful shutdown — обработчики сигналов. Каждое дополнение — паттерн, который читатель уже знает, но собирать их руками — строить фреймворк фоновых задач. Sidekiq — этот фреймворк.

### Сценарий

Тип: сценарий применения. Rails-приложение начинает с простой отправки email в фоне и постепенно сталкивается с проблемами, которые каждый файл серии решает. Сквозной пример — обработка заказа: email подтверждения, resize аватара, платёжная сверка, аналитика.

### Дуга

```
Простая очередь руками → много типов задач → нужен фреймворк
  → 00: Sidekiq — архитектура (три роли, Redis data model)

Архитектура понятна → как конкретно задача проходит путь?
  → 01: lifecycle (perform_async → JSON → LPUSH → BRPOP → perform)

Job выполнился → процесс упал mid-execution. BRPOP удалил задачу.
  → 02: BasicFetch vs SuperFetch. At-least-once → идемпотентность

Job упал с exception (email-сервис down)
  → 03: retry (формула, sorted sets, DLQ, death handlers)

Retry обрабатывает ошибки кода → нужен deploy нового кода
  → 04: сигналы (TSTP → TERM), deploy sequence, IterableJob

Один job работает корректно → но реальная задача = группа jobs
  → 05: job design (атомарность, fan-out, bulkhead, Batches)

Jobs спроектированы → нагрузка растёт
  → 06: concurrency (threads + GVL), processes, priorities, Capsules

Система масштабирована → как тестировать?
  → 07: testing (fake/inline/disable), ActiveJob vs Sidekiq::Job
```

### Карта деталей

| Деталь | Файл (шаг дуги) |
|--------|-----------------|
| perform_async, perform_in, perform_at | 00, 01 |
| Три роли: client / broker / server | 00 |
| Redis keys: queue:\<name\>, schedule, retry, dead, processes, \<identity\> | 00 |
| Launcher → Manager → Processor + Poller + Heartbeat | 00 |
| JSON-сериализация, class/args/queue/jid, ограничения | 01 |
| Client middleware, server middleware pipeline | 01 |
| Три точки потери: push, fetch, scheduling | 02 |
| BasicFetch (BRPOP), SuperFetch (Pro, `config.super_fetch!`) | 02 |
| Reliable push (Pro, `reliable_push!`), reliable scheduler (Pro, `reliable_scheduler!`) | 02 |
| Идемпотентность jobs, типичные ловушки | 02 |
| perform_async в транзакции, Transactional Push (7.2+) | 02 |
| Retry formula: count^4 + 15 + jitter, почему степень 4 | 03 |
| Sorted sets: schedule, retry, dead. Poller thread | 03 |
| Death handlers, custom retry options | 03 |
| TSTP (quiet), TERM/INT (shutdown), TTIN (backtrace) | 04 |
| Deploy sequence: TSTP → deploy → TERM | 04 |
| IterableJob (7.3+): cursor-based resume | 04 |
| Атомарность jobs, один job = одна операция | 05 |
| Fan-out: один job порождает N sub-jobs | 05 |
| Bulkhead внутри job vs отдельные jobs | 05 |
| Batches (Pro: callbacks; OSS: sidekiq-batch, sidekiq-grouping) | 05 |
| concurrency setting, thread pool, GVL overlap | 06 |
| Несколько процессов для CPU parallelism | 06 |
| Weighted vs strict queue priority | 06 |
| Capsules (7.0+): in-process bulkhead | 06 |
| Testing: fake, inline, disable | 07 |
| ActiveJob vs Sidekiq::Job trade-off | 07 |
| Strict argument checking | 07 |

### Связи

**Предпосылки серии (index.md):** Ruby, Rails, базовое понимание Redis.

**Per-file предпосылки:**

| Файл | Предпосылки |
|------|-------------|
| 00-architecture | [Redis Lists](../../databases/redis/data-structures/02-list.md), [Очереди в Redis](../../databases/redis/patterns/03-queues.md), [Message Queues](../../system-design/09-message-queues.md), [Background queue](../redis/practice/list-background-queue.md) |
| 01-job-lifecycle | Предыдущий файл серии |
| 02-guarantees | [Гарантии доставки](../../system-design/08-delivery-guarantees.md), [Reliability patterns § idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов) |
| 03-retry-and-errors | Предыдущие файлы серии |
| 04-signals-and-deploy | [Сигналы](../../linux/programming/00-signals.md) |
| 05-job-design | [Reliability patterns § bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов), [Event-driven architecture](../../system-design/13-event-driven-architecture.md) |
| 06-concurrency-and-scaling | [Ruby concurrency](../../ruby/ruby-concurrency.md), [Потоки](../../linux/foundations/03-threads.md) |
| 07-testing | Предыдущие файлы серии |

### Интеграция с system-design (cross-links)

Ключевой принцип: Sidekiq — конкретная реализация абстрактных паттернов из system-design. Каждый cross-link подтверждает связь: «это тот самый паттерн, который ты знаешь, вот как он реализован здесь».

**00-architecture.md:**
- [Temporal decoupling](../../system-design/09-message-queues.md#temporal-decoupling-развязка-во-времени) — мотивация: зачем background processing
- [Point-to-point](../../system-design/09-message-queues.md#point-to-point-и-pubsub) — модель Sidekiq: competing consumers
- [Microservices § Sidekiq в монолите](../../system-design/12-microservices.md) — контекст: где живёт Sidekiq в архитектуре

**01-job-lifecycle.md:**
- [ACK](../../system-design/09-message-queues.md#acknowledgment) — Sidekiq не использует explicit ACK в OSS (BRPOP = implicit)

**02-guarantees.md:**
- [At-least-once](../../system-design/08-delivery-guarantees.md#at-least-once-не-менее-одного-раза) — контракт Sidekiq при SuperFetch
- [Exactly-once = at-least-once + idempotency](../../system-design/08-delivery-guarantees.md#exactly-once--at-least-once--idempotency) — ключевая формула
- [Idempotency key](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов) — паттерн для Sidekiq jobs

**03-retry-and-errors.md:**
- [Retry с backoff](../../system-design/06-reliability-patterns.md#retry-with-backoff-повторная-попытка) — Sidekiq применяет тот же паттерн, но с power of 4
- [DLQ](../../system-design/09-message-queues.md#dead-letter-queue) — dead set = DLQ
- [Transient vs permanent failure](../../system-design/06-reliability-patterns.md#transient-vs-permanent-failure) — различение в контексте retry

**04-signals-and-deploy.md:**
- [Graceful shutdown](../../linux/programming/00-signals.md#практические-паттерны) — Sidekiq реализует тот же паттерн

**05-job-design.md:**
- [Bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) — изоляция критичного от некритичного внутри jobs
- [Bulkhead § Sidekiq queues](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) — reliability-patterns уже содержит пример с Sidekiq очередями
- [Cascading failure](../../system-design/06-reliability-patterns.md#cascading-failure-механизм) — что происходит, когда один медленный job забивает все потоки
- [Event-driven architecture § command vs event](../../system-design/13-event-driven-architecture.md) — perform_async = command, Kafka publish = event. Осознанный выбор.
- [Idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов) — retry-safe design requires idempotent jobs

**06-concurrency-and-scaling.md:**
- [Bulkhead § отдельные очереди](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) — Capsules = bulkhead внутри процесса
- [Backpressure](../../system-design/09-message-queues.md#backpressure) — что происходит, когда Redis забит (noeviction → ошибка записи)

## Валидация

1. **Граница знаний — полна?** Да. Все технические концепции, используемые в серии, либо в предпосылках файла, либо объясняются впервые.
2. **Мотивация — создаёт любопытство?** Да. «Ты построил queue руками — вот что ещё нужно для production» — конкретная боль.
3. **Точка входа — доступна при предпосылках?** Да. Опирается на list-background-queue.md, который читатель уже прошёл.
4. **Дуга — история, где каждый шаг создаёт следующий?** Да. Без терминов: «простая очередь → нужен фреймворк → как работает → что если crash → что если ошибка → что если deploy → как проектировать задачи → как масштабировать → как тестировать».
5. **Структура — разрывы в правильных местах?** Да. Каждый файл имеет свои предпосылки и самодостаточный сценарий.
6. **Интеграция — полная?** Да. Cross-links в 6 из 8 файлов к 5 заметкам system-design. Обратные ссылки из system-design обновляются.

PASS.

## Файловая структура из дуги

```
rails/sidekiq/
├── index.md                          # карта серии + trade-offs
├── 00-architecture.md                # зачем + три роли + Redis data model
├── 01-job-lifecycle.md               # perform_async → completion, middleware
├── 02-guarantees.md                  # BasicFetch vs SuperFetch, idempotency
├── 03-retry-and-errors.md            # формула retry, sorted sets, DLQ
├── 04-signals-and-deploy.md          # TSTP/TERM, deploy sequence, IterableJob
├── 05-job-design.md                  # атомарность, fan-out, batches, композиция
├── 06-concurrency-and-scaling.md     # threads, processes, priorities, capsules
└── 07-testing.md                     # fake/inline, ActiveJob, argument validation

rails/index.md                        # НОВЫЙ: карта Rails-материалов
```

## Дизайн файлов

### index.md

Предпосылки серии: Ruby, Rails, базовое понимание Redis.

Секции: вводный абзац (что такое Sidekiq, зачем серия), порядок изучения (ссылки на все файлы с описаниями), «Как всё связано» (ключевые trade-offs: OSS vs Pro, threads vs processes, ActiveJob vs Sidekiq::Job), Sources.

### 00-architecture.md (~130-150 строк)

**Предпосылки:** [Redis Lists](../../databases/redis/data-structures/02-list.md), [Очереди в Redis](../../databases/redis/patterns/03-queues.md), [Message Queues](../../system-design/09-message-queues.md), [Background queue](redis/practice/list-background-queue.md).

**Мотивация:** Простая очередь руками работает для одного типа задачи. В реальном приложении десятки типов, каждый со своими требованиями.

**Вход:** Мост от list-background-queue.md: «цикл с BRPOP обслуживает один тип. Добавь retry, shutdown, monitoring — получишь фреймворк. Sidekiq — этот фреймворк.»

**Под-дуга:**
1. Определения: job (Ruby-класс + JSON в Redis), worker (устаревший синоним), queue (Redis LIST key)
2. Три роли: Client (Rails app → serialize → LPUSH), Broker (Redis → хранит), Server (Sidekiq process → BRPOP → execute)
3. Redis data model (таблица: List queue:\<name\>, Sorted Set schedule/retry/dead, Set queues/processes, Hash \<identity\>). Зачем noeviction.
4. Server internals: Launcher → Manager → Processors + Poller (schedule/retry) + Heartbeat
5. perform_async / perform_in / perform_at — три способа поставить задачу

**system-design cross-links:**
- [Temporal decoupling](../../system-design/09-message-queues.md#temporal-decoupling-развязка-во-времени) при мотивации
- [Point-to-point](../../system-design/09-message-queues.md#point-to-point-и-pubsub) при описании модели competing consumers

**Завершение → 01:** «Архитектура — карта. Теперь проследим путь одной задачи через неё.»

### 01-job-lifecycle.md (~100-130 строк)

**Предпосылки:** предыдущий файл серии.

**Мотивация:** Карта есть, но как конкретно задача проходит путь?

**Вход:** `SendEmailJob.perform_async(user_id)` — что происходит дальше?

**Под-дуга:**
1. Client side: perform_async → Sidekiq::Client → сериализация в JSON → client middleware chain → LPUSH в queue:\<name\>
2. JSON constraint: почему только примитивы (String, Integer, Float, Boolean, Array, Hash, nil). ActiveRecord → «#\<User:0x...\>». Symbol → String. Time → String.
3. Server side: BRPOP → десериализация → server middleware chain → perform(args)
4. Middleware pipeline: client (before push) и server (around perform). Пример: логирование, метрики.
5. Scheduled jobs: perform_in → ZADD в schedule sorted set (score = timestamp). Poller проверяет, переносит в queue.

**Завершение → 02:** «Job успешно выполнился. А что если Sidekiq-процесс убит mid-execution?»

### 02-guarantees.md (~110-130 строк)

**Предпосылки:** [Гарантии доставки](../../system-design/08-delivery-guarantees.md), [Reliability patterns § idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов).

**Мотивация:** Процесс убит OOM mid-job. Что случилось с задачей?

**Вход:** BRPOP удалил задачу из Redis. Процесс мёртв. Задача потеряна навсегда.

**Под-дуга:**
1. Три точки потери: push (client → Redis), fetch (Redis → worker), scheduling (sorted set → queue). Каждая — отдельный механизм, каждая может потерять job независимо.
2. **Fetch** — самая наглядная. BasicFetch (default): BRPOP = простая очередь из redis/patterns. Job удалён из Redis до начала выполнения. Crash/OOM/SIGKILL = потеря. SuperFetch (Pro, opt-in через `config.super_fetch!`, `<details>`): LMOVE в приватную очередь процесса = reliable queue из redis/patterns. Job в Redis до acknowledge. Orphan recovery при crash.
3. **Push** — client отправляет LPUSH, но Redis может быть недоступен. Reliable push (Pro, opt-in через `Sidekiq::Client.reliable_push!`, `<details>`): при сбое Redis сохраняет job локально и повторяет. Default push: job потерян при сбое сети.
4. **Scheduling** — Poller переносит jobs из sorted sets в queue. Default scheduler: ZRANGEBYSCORE + LPUSH не атомарны, crash между ними = потеря или дублирование. Reliable scheduler (Pro, opt-in через `config.reliable_scheduler!`, `<details>`): атомарное продвижение.
5. Контракт: default OSS = at-most-once при crash на каждой из трёх точек. Pro mechanisms значительно сужают окна потерь, но не закрывают полностью — у каждого есть оставшиеся loss windows (`reliable_push!` = in-memory buffer, теряется при рестарте клиентского процесса, не совместим с Batches; `reliable_scheduler!` unsafe на Redis Cluster). Называть это «hard at-least-once» — преувеличение; корректнее: best-effort [at-least-once](../../system-design/08-delivery-guarantees.md#at-least-once-не-менее-одного-раза) с конкретными оговорками в `<details>`. Важно: покупка Pro без включения — не меняет гарантий.
6. At-least-once → возможны дубликаты → [idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов). Конкретные паттерны: unique constraint, idempotency key, status check.
7. Ловушка: perform_async внутри ActiveRecord-транзакции. Job попадает в Redis до commit. Rollback → job обрабатывает несуществующие данные. Решение: Transactional Push (7.2+).

**system-design cross-links:**
- [At-least-once](../../system-design/08-delivery-guarantees.md#at-least-once-не-менее-одного-раза) — контракт
- [Exactly-once = at-least-once + idempotency](../../system-design/08-delivery-guarantees.md#exactly-once--at-least-once--idempotency) — формула
- [Idempotency key](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов) — конкретный механизм

**Завершение → 03:** «Знаем о потерях и дубликатах. Но что если job просто упал с ошибкой — email-сервис вернул 500?»

### 03-retry-and-errors.md (~110-140 строк)

**Предпосылки:** предыдущие файлы серии. (Retry backoff уже в предпосылках файла 02 через reliability-patterns.)

**Мотивация:** Job raises exception. Email-сервис down.

**Вход:** Exception в perform → Sidekiq ловит → что дальше?

**Под-дуга:**
1. Processor wraps server middleware chain с `JobRetry`. Exception из perform или middleware поднимается до `JobRetry#process_retry` → ZADD в retry sorted set (score = время следующей попытки). Важно: retry — это уровень Processor, не middleware. Server middleware (логирование, метрики) работает внутри retry boundary.
2. Формула delay: `(count ** 4) + 15 + (rand(10) * (count + 1))`. Сравнение с [exponential backoff](../../system-design/06-reliability-patterns.md#retry-with-backoff-повторная-попытка) из system-design: степень 4 (не 2) — агрессивный backoff, чтобы дать время на deploy фикса. Jitter — предотвращение thundering herd.
3. retry sorted set = delayed queue pattern из [redis/patterns](../../databases/redis/patterns/03-queues.md#отложенные-задачи-delayed-queue). Poller переносит jobs из retry/schedule sorted sets в очередь. Default: ZRANGEBYSCORE + LPUSH (не атомарно, crash между ними = дубликат или потеря). Reliable scheduler (Pro): атомарное продвижение через Lua. Интервал Poller масштабируется с числом процессов.
4. 25 retry ≈ 21 день. После — ZADD в dead sorted set (max 10000, TTL 6 мес). Dead set = [DLQ](../../system-design/09-message-queues.md#dead-letter-queue).
5. Death handlers: `config.death_handlers << ->(job, ex) { ... }`. Custom retry per job: `sidekiq_options retry: 5`.
6. [Transient vs permanent failure](../../system-design/06-reliability-patterns.md#transient-vs-permanent-failure): retry спасает от transient (API down на час). Permanent (невалидный email) — бессмысленно, нужен dead set.

**system-design cross-links:**
- [Retry с backoff](../../system-design/06-reliability-patterns.md#retry-with-backoff-повторная-попытка) — сравнение формул
- [DLQ](../../system-design/09-message-queues.md#dead-letter-queue) — dead set это DLQ
- [Transient vs permanent](../../system-design/06-reliability-patterns.md#transient-vs-permanent-failure) — контекст для retry

**Завершение → 04:** «Retry обрабатывает ошибки кода. Но что если причина — инфраструктурная: deploy нового кода, перезапуск сервера?»

### 04-signals-and-deploy.md (~90-120 строк)

**Предпосылки:** [Сигналы](../../linux/programming/00-signals.md).

**Мотивация:** Deploy нового кода → старый процесс должен остановиться без потери in-flight jobs.

**Вход:** `cap production deploy` — 10 jobs выполняются. Что происходит?

**Под-дуга:**
1. TSTP = quiet: процесс перестаёт забирать новые jobs, дорабатывает текущие. Аналогия: [graceful shutdown](../../linux/programming/00-signals.md#практические-паттерны) — stop accepting, finish current.
2. TERM/INT = shutdown: timeout (default 25 sec), затем принудительное завершение. Текущие jobs прерываются, незавершённые requeue.
3. Deploy sequence: TSTP → deploy new code → TERM old process. Зачем два шага: TSTP даёт время дорабатывать, пока новый код ещё не готов.
4. TTIN = backtrace всех потоков (debug).
5. Self-pipe trick для безопасной обработки сигналов (ссылка на linux/signals).
6. Edge case: SIGKILL (OOM, `kill -9`) → нет graceful shutdown → jobs потеряны (OSS) или orphaned (Pro).
7. IterableJob (7.3+, `<details>`): для long-running jobs. Cursor-based: при shutdown сохраняет позицию, при restart продолжает.

**Завершение → 05:** «Один job работает, обрабатывает ошибки, корректно останавливается. Но реальная задача — не один job, а группа: обработать заказ = зарезервировать + оплатить + отправить email. Как проектировать?»

### 05-job-design.md (~110-140 строк)

**Предпосылки:** [Reliability patterns § bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов), [Event-driven architecture](../../system-design/13-event-driven-architecture.md).

**Мотивация:** Обработка заказа — цепочка операций. Один большой job делает всё: reserve → charge → email → analytics. Одна ошибка в analytics роняет весь job → retry перезапускает charge → двойное списание.

**Вход:** OrderProcessingJob.perform: payment + email + analytics в одном perform. Analytics упал → retry → charge повторно.

**Под-дуга:**
1. Один большой job = одна ошибка роняет всё. Retry = повторение всех шагов. Наглядный пример из [reliability-patterns](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов): некритичное не должно ронять критичное.
2. Принцип: один job = одна атомарная операция. Job должен быть идемпотентным (cross-link: [idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов)).
3. Fan-out: один job порождает N sub-jobs. ChargePaymentJob → SendEmailJob.perform_async + TrackAnalyticsJob.perform_async. Каждый job со своим retry-циклом.
4. [Bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) внутри job: begin/rescue для некритичного vs отдельные jobs (лучше). reliability-patterns.md уже содержит пример с Sidekiq очередями — cross-link.
5. Координация: когда все sub-jobs завершены? Batches (Pro: callbacks on_success, on_complete; `<details>`). OSS альтернативы: sidekiq-batch, sidekiq-grouping (`<details>`).
6. perform_async = [команда](../../system-design/13-event-driven-architecture.md) (знаю получателя, жду действие). Kafka publish = событие (не знаю, кто обработает). Осознанный выбор модели. Когда Sidekiq-команды перерастают в event-driven — ссылка на EDA.

**system-design cross-links:**
- [Bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) — изоляция внутри jobs + очереди
- [Cascading failure](../../system-design/06-reliability-patterns.md#cascading-failure-механизм) — один медленный job забивает все потоки
- [Command vs event](../../system-design/13-event-driven-architecture.md) — модель интеграции
- [Idempotency](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов) — retry-safe design

**Завершение → 06:** «Jobs спроектированы: маленькие, атомарные, идемпотентные. Их стало 10 000 в час. Как обработать?»

### 06-concurrency-and-scaling.md (~110-140 строк)

**Предпосылки:** [Ruby concurrency](../../ruby/ruby-concurrency.md), [Потоки](../../linux/foundations/03-threads.md).

**Мотивация:** 10 потоков, все I/O-bound. 10 000 jobs/час. Не справляемся.

**Вход:** 1000 emails/минуту, Sidekiq обрабатывает 60. Пользователи ждут 15 минут.

**Под-дуга:**
1. Thread pool + [GVL](../../ruby/ruby-concurrency.md#gvl-почему-потоки-не-ускоряют-cpu-код): потоки полезны для I/O-bound (email, HTTP, DB). CPU-bound jobs не ускоряются потоками.
2. concurrency setting: больше потоков → больше I/O overlap, но больше memory + connection pool. Правило: concurrency ≤ DB pool size.
3. Несколько процессов: каждый со своим GVL. CPU parallelism. systemd / Procfile / docker-compose.
4. Queue priorities: weighted (`critical,3 default,2 low,1` → вероятностная) vs strict (`critical default low` → critical обрабатывается первым). Weighted = fair scheduling. Strict = starvation risk для low.
5. [Bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) через очереди: отдельные процессы для critical и low. Один забит тяжёлыми jobs — второй работает.
6. Capsules (7.0+, `<details>`): изолированная группа настроек внутри одного процесса. Свой concurrency, свои очереди. In-process bulkhead без отдельного процесса.
7. [Backpressure](../../system-design/09-message-queues.md#backpressure): Redis с noeviction → при исчерпании памяти LPUSH возвращает ошибку → producer получает exception. Мониторинг queue depth.

**system-design cross-links:**
- [Bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) — очереди и процессы как bulkhead
- [Backpressure](../../system-design/09-message-queues.md#backpressure) — Redis memory limits

**Завершение → 07:** «Система масштабирована. Как тестировать? И какой API выбрать?»

### 07-testing.md (~90-120 строк)

**Предпосылки:** предыдущие файлы серии.

**Мотивация:** RSpec тест для job, но perform_async уходит в Redis...

**Вход:** Тест OrderJob: проверить, что email отправлен после выполнения job.

**Под-дуга:**
1. Testing modes: `Sidekiq::Testing.fake!` (jobs в массив, не в Redis), `Sidekiq::Testing.inline!` (немедленное выполнение), `Sidekiq::Testing.disable!` (реальный Redis).
2. Fake mode: assert enqueued (`SendEmailJob.jobs.size`), drain (`SendEmailJob.drain`).
3. Когда какой: unit tests → fake, integration → inline или disable.
4. ActiveJob vs Sidekiq::Job (trade-off): ActiveJob = абстракция + GlobalID + adapter switching, но ~30% overhead, несовместимость с Batches (Pro), ограниченный контроль retry. Sidekiq::Job = прямой доступ, performance, Pro-фичи. Для большинства Rails-приложений без смены backend — Sidekiq::Job.
5. `Sidekiq.strict_args!` в initializer — глобальная strict argument checking (ловит Symbol, Time, ActiveRecord в аргументах при enqueue через `JobUtil#verify_json`).
6. Gotchas: Time.now в тестах (freeze), Redis state между тестами.

**Нет следующего файла — завершение серии.**

## Integration plan

### Обновление существующих файлов

| Файл | Что менять |
|------|-----------|
| `rails/redis/index.md` | Обновить ссылку `sidekiq.md` → `sidekiq/index.md` |
| `rails/redis/practice/list-background-queue.md` | Обновить ссылку на Sidekiq если есть |
| `databases/redis/patterns/03-queues.md` | «См. также» → `../../rails/sidekiq/index.md` вместо `sidekiq.md`. Добавить cross-link на 02-guarantees.md (BasicFetch/SuperFetch как конкретная инстанциация) |
| `system-design/09-message-queues.md` | «См. также» → `../rails/sidekiq/index.md`. Уточнить inline cross-links (point-to-point → 00-architecture, retry → 03-retry, DLQ → 03-retry) |
| `system-design/06-reliability-patterns.md` | Bulkhead section: обновить ссылки на sidekiq.yml пример → `../rails/sidekiq/06-concurrency-and-scaling.md`. Idempotency section: добавить cross-link на 02-guarantees.md |
| `system-design/12-microservices.md` | Обновить все ссылки `sidekiq.md` → `sidekiq/index.md` |
| `system-design/13-event-driven-architecture.md` | Обновить ссылки, добавить cross-link на 05-job-design.md (command vs event) |
| `CLAUDE.md` | Обновить file map: `rails/` описание |

### Создание новых файлов

| Файл | Описание |
|------|----------|
| `rails/index.md` | Карта Rails-материалов: Redis серия + Sidekiq серия. Предпосылки: Ruby, Rails. |
| `rails/sidekiq/index.md` | Карта серии Sidekiq |
| `rails/sidekiq/00-architecture.md` | Зачем + три роли + Redis data model |
| `rails/sidekiq/01-job-lifecycle.md` | perform_async → completion |
| `rails/sidekiq/02-guarantees.md` | BasicFetch vs SuperFetch, idempotency |
| `rails/sidekiq/03-retry-and-errors.md` | Retry formula, sorted sets, DLQ |
| `rails/sidekiq/04-signals-and-deploy.md` | TSTP/TERM, deploy, IterableJob |
| `rails/sidekiq/05-job-design.md` | Атомарность, fan-out, batches |
| `rails/sidekiq/06-concurrency-and-scaling.md` | Threads, processes, priorities, capsules |
| `rails/sidekiq/07-testing.md` | Testing modes, ActiveJob, practices |

### Удаление

| Файл | Причина |
|------|---------|
| `rails/sidekiq.md` | Заменяется серией `rails/sidekiq/` |
