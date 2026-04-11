---
tags:
  - domain/rails
  - theme/concurrency
  - theme/performance
  - type/concept
aliases:
  - Capsules
  - Sidekiq scaling
order: 6
---

# Concurrency и масштабирование

**Предпосылки:** [Sidekiq: дизайн задач](job-design.md), [Ruby concurrency](../../ruby/internal/concurrency.md), [потоки](../../linux/foundations/threads.md).

<- [Дизайн задач](job-design.md) | [Тестирование и практики](testing.md) ->

Задачи спроектированы: маленькие, атомарные, идемпотентные. Их стало десять тысяч в час, а один Sidekiq-процесс с пятью потоками обрабатывает 30 в минуту. Пользователи ждут email 15 минут. Как обработать больше?

## Потоки и GVL

[Sidekiq](sidekiq.md) использует потоки для параллельной обработки [задач](job-lifecycle.md). Настройка `concurrency` определяет количество Processor-потоков:

```yaml
# config/sidekiq.yml
:concurrency: 5
```

Ruby-потоки работают под [[ruby/internal/concurrency#gvl-почему-потоки-не-ускоряют-cpu-код|GVL]], но для I/O-bound задач это не проблема: GVL освобождается при блокирующем I/O, и потоки эффективно чередуют CPU и [[ruby/internal/concurrency#io-overlap-потоки-полезны-даже-с-gvl|I/O overlap]]. Для CPU-bound задач потоки не дают ускорения — здесь помогут дополнительные процессы.

## Concurrency: сколько потоков?

Больше потоков — больше I/O overlap, но больше потребление ресурсов:

**Память.** Каждый поток имеет свой стек и может держать свои Ruby-объекты. 50 потоков потребляют заметно больше памяти, чем 10.

**Пул соединений к базе.** Каждый поток может одновременно выполнять запрос к PostgreSQL — значит, нужно столько же соединений. Правило: `database.yml pool ≥ concurrency`.

```yaml
# database.yml
production:
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>
```

**Redis connections.** У [Sidekiq](sidekiq.md) есть не только соединения рабочих Processor-потоков, но и служебные подключения для внутренних операций. Поэтому суммарное число Redis-соединений всегда больше `concurrency`, а точное значение зависит от версии, Capsules и включённых Pro-механизмов.

Типичный подход: для I/O-bound задач 10–25 потоков, для CPU-bound — мало потоков (2–5), зато несколько процессов.

## Несколько процессов: CPU-параллелизм

Каждый Ruby-процесс имеет свой GVL. Два процесса = два GVL = два ядра CPU работают одновременно. Это способ обойти ограничение GVL для CPU-bound нагрузки.

```bash
# Два процесса, каждый с 5 потоками
bundle exec sidekiq -c 5  # процесс 1
bundle exec sidekiq -c 5  # процесс 2
```

Запуск нескольких процессов — через systemd, Procfile, docker-compose или Kubernetes replicas. Sidekiq не управляет дочерними процессами: каждый процесс независим, со своим подключением к Redis.

Дополнительное преимущество: изоляция. Если один процесс убит OOM-killer — остальные продолжают работать.

## Приоритеты очередей

Не все задачи одинаково важны. Платёж важнее аналитики, email важнее resize аватара. Sidekiq обрабатывает очереди по приоритету, и есть два режима:

**Strict** — очереди проверяются в фиксированном порядке:

```yaml
:queues:
  - critical
  - default
  - low
```

Sidekiq забирает задачи из `critical`, пока она не опустеет, потом из `default`, потом из `low`. Риск: если `critical` постоянно наполняется, `low` никогда не обработается (starvation).

**Weighted** — вероятностный выбор:

```yaml
:queues:
  - [critical, 3]
  - [default, 2]
  - [low, 1]
```

Из шести обращений к Redis в среднем три достанутся `critical`, два — `default`, одно — `low`. Все очереди получают внимание, но с разной частотой. Starvation маловероятен, хотя при экстремальной нагрузке на приоритетные очереди возможны задержки.

## Bulkhead: изоляция через процессы и очереди

Один медленный job-класс, который делает HTTP-запросы к медленному API, может занять все потоки. Пока все потоки ждут ответа от API, задачи из других очередей стоят — это [[system-design/reliability-patterns#cascading-failure-механизм|cascading failure]] внутри одного процесса.

Решение из [[system-design/reliability-patterns#bulkhead-изоляция-ресурсов|reliability patterns]] — [[system-design/reliability-patterns#bulkhead-изоляция-ресурсов|bulkhead]]: выделить отдельный процесс для медленных задач:

```bash
bundle exec sidekiq -q critical -q default  # процесс 1: быстрые задачи
bundle exec sidekiq -q external_api         # процесс 2: медленные API-вызовы
```

Медленный API забивает все потоки процесса 2 — процесс 1 продолжает обрабатывать critical и default без задержек.

> [!info]- Capsules: bulkhead внутри одного процесса (Sidekiq 7.0+)
> Capsule (капсула) — изолированная группа настроек внутри одного процесса. У каждой капсулы свой concurrency и свой набор очередей:
>
> ```ruby
> Sidekiq.configure_server do |config|
>   # Основная капсула (default) — 5 потоков для обычных задач
>   config.concurrency = 5
>   config.queues = %w[critical default]
>
>   # Отдельная капсула — 3 потока для медленных API
>   config.capsule("slow_api") do |cap|
>     cap.concurrency = 3
>     cap.queues = %w[external_api]
>   end
> end
> ```
>
> Внутри каждой капсулы — свой Manager с отдельным набором Processor-ов. Медленные API-[задачи](job-design.md) не могут занять потоки основной капсулы. Bulkhead без отдельного процесса — меньше overhead на память и управление.

## Backpressure: когда Redis переполнен

Redis настроен с политикой [[rails/sidekiq/architecture#данные-в-redis|`noeviction`]]: при исчерпании памяти вызов `perform_async` получит exception — это [[system-design/message-queues#backpressure|backpressure]]: система сигнализирует, что не справляется.

Мониторинг глубины очереди (`Sidekiq::Queue.new("default").latency`) помогает заметить накопление до того, как Redis переполнится. Если latency растёт — задачи добавляются быстрее, чем обрабатываются. Решения: увеличить concurrency, добавить процессы, оптимизировать задачи, или перенести некритичные задачи на off-peak часы.

---

Потоки, процессы, очереди, Capsules — инфраструктура масштабирования на месте. Остаётся вопрос разработки: RSpec-тест вызывает `perform_async`, [задача](job-lifecycle.md) уходит в Redis — тест проходит, но ничего не проверяет. И параллельно — выбор API: Rails предоставляет ActiveJob, Sidekiq предоставляет `Sidekiq::Job`. Это рассматривается в [тестировании и практиках](testing.md).

---

<- [Дизайн задач](job-design.md) | [Тестирование и практики](testing.md) ->

## Sources

- [Sidekiq Wiki — Advanced Options](https://github.com/sidekiq/sidekiq/wiki/Advanced-Options)
- [Sidekiq Wiki — Using Redis](https://github.com/sidekiq/sidekiq/wiki/Using-Redis)
- Mike Perham, [Sidekiq 7.0 Beta](https://www.mikeperham.com/2022/09/27/sidekiq-7.0-beta-now-available/)
