# Дизайн задач

**Предпосылки:** [Sidekiq: сигналы и deploy](04-signals-and-deploy.md), [reliability patterns § bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов), [event-driven architecture](../../system-design/13-event-driven-architecture.md), [message queues](../../system-design/09-message-queues.md).

<- [Сигналы и deploy](04-signals-and-deploy.md) | [Concurrency и масштабирование](06-concurrency-and-scaling.md) ->

`ProcessOrderJob#perform` делает четыре вещи: резервирует товар, списывает оплату, отправляет email, записывает аналитику. Аналитика падает — весь job уходит в retry. Повторная попытка списывает оплату второй раз. Проблема не в retry — проблема в том, как спроектирован job.

## Один большой job — проблема

Наивный подход — один job, который делает всё:

```ruby
class ProcessOrderJob
  include Sidekiq::Job

  def perform(order_id)
    order = Order.find(order_id)
    PaymentService.charge(order)      # 1. списать оплату
    WarehouseService.reserve(order)    # 2. зарезервировать
    UserMailer.confirmation(order).deliver_now  # 3. email
    AnalyticsService.track(order)      # 4. аналитика
  end
end
```

Аналитика упала — exception поднимается до `JobRetry`, задача уходит в retry. При повторной попытке выполнятся все четыре шага заново — включая `charge`, который уже списал деньги. Двойное списание.

Проблема глубже, чем повторное списание. Некритичное действие (аналитика) роняет критичное (оплату). Это частный случай [cascading failure](../../system-design/06-reliability-patterns.md#cascading-failure-механизм): сбой в одном компоненте бьёт по всему потоку. В [reliability patterns](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов) решение — [bulkhead](../../system-design/06-reliability-patterns.md#bulkhead-изоляция-ресурсов): изолировать критичное от некритичного, чтобы сбой одного не затрагивал другое.

## Один job = одна атомарная операция

Принцип: каждый job делает одну операцию, которая либо полностью выполняется, либо нет. Job должен быть [идемпотентным](../../system-design/06-reliability-patterns.md#idempotency-безопасность-повторных-запросов) — безопасным для повторного выполнения.

```ruby
class ChargePaymentJob
  include Sidekiq::Job

  def perform(order_id)
    order = Order.find(order_id)
    return if order.charged?
    PaymentService.charge(order)
  end
end
```

Одна операция, один retry-цикл, один набор ошибок. Если `ChargePaymentJob` упадёт — повторится только charge. Analytics работает независимо в своём job с отдельным retry.

## Fan-out: один job порождает несколько

Когда одно событие запускает несколько независимых действий — job-координатор ставит sub-jobs:

```ruby
class ProcessOrderJob
  include Sidekiq::Job

  def perform(order_id)
    ChargePaymentJob.perform_async(order_id)
    ReserveWarehouseJob.perform_async(order_id)
    SendConfirmationJob.perform_async(order_id)
    TrackAnalyticsJob.perform_async(order_id)
  end
end
```

Каждый sub-job:
- со своим retry-циклом (analytics может упасть 10 раз — payment не пострадает)
- со своей очередью (критичные в `critical`, аналитика в `low`)
- со своим набором ошибок (RateLimitError у API, SMTP timeout у email)

Для массовых операций (обработать 10 000 записей) — тот же паттерн, но с `perform_bulk` (метод класса, который группирует задачи в чанки и отправляет за несколько round-trip к Redis вместо отдельного вызова на каждую задачу):

```ruby
class BatchImportJob
  include Sidekiq::Job

  def perform(file_id)
    rows = CsvFile.find(file_id).parse
    ImportRowJob.perform_bulk(rows.map { |r| [r.id] })
  end
end
```

## Когда нужна координация: Batches

Fan-out решает изоляцию, но создаёт новую задачу: как узнать, что все sub-jobs завершились? Нужно отправить итоговый email после завершения всего импорта, или оповестить пользователя, что заказ полностью обработан.

<details>
<summary>Batches (Sidekiq Pro)</summary>

Batch — группа jobs, за завершением которой можно наблюдать через callbacks:

```ruby
batch = Sidekiq::Batch.new
batch.description = "Import CSV #42"
batch.on(:success, ImportCallbacks, file_id: 42)
batch.on(:complete, ImportCallbacks, file_id: 42)

batch.jobs do
  csv_rows.each { |row| ImportRowJob.perform_async(row.id) }
end
```

```ruby
class ImportCallbacks
  def on_success(status, options)
    # Все jobs завершились успешно
    Mailer.import_done(options['file_id']).deliver_now
  end

  def on_complete(status, options)
    # Все jobs завершились (успешно или нет)
    if status.failures > 0
      Mailer.import_partial(options['file_id'], status.failures).deliver_now
    end
  end
end
```

`on_success` вызывается, когда все jobs batch завершились успешно. `on_complete` — когда все jobs выполнились хотя бы по одному разу, независимо от результата (даже если часть ушла в retry). Это значит, что `on_complete` может сработать, пока часть jobs ещё повторяется. Если нужно реагировать на окончательную смерть job — есть callback `:death`.

Ограничение: Batches не совместимы с ActiveJob — ActiveJob перехватывает retry, и Sidekiq видит job как «успешный», даже если он ещё повторяется.

</details>

<details>
<summary>OSS-альтернативы для координации</summary>

Для OSS Sidekiq есть community gems: [sidekiq-batch](https://github.com/breamware/sidekiq-batch) (API, близкий к Pro Batches) и [sidekiq-grouping](https://github.com/gzigzigzeo/sidekiq-grouping) (группировка мелких задач в пачки для оптимизации).

Простейший подход без gems — хранить прогресс в Redis или базе данных:

```ruby
class ImportRowJob
  include Sidekiq::Job

  def perform(row_id, batch_key)
    import(row_id)
    remaining = Redis.current.decr(batch_key)
    NotifyCompletionJob.perform_async(batch_key) if remaining == 0
  end
end
```

</details>

## Command vs Event: модель интеграции

`perform_async` — это команда в терминах [event-driven architecture](../../system-design/13-event-driven-architecture.md): вызывающий код знает конкретного получателя и ожидает конкретное действие. `ChargePaymentJob.perform_async(order_id)` — «ты, ChargePaymentJob, обработай этот заказ».

Альтернативная модель — событие: «заказ создан, кому интересно — обрабатывайте». Вызывающий код не знает получателей. Это территория [pub/sub](../../system-design/09-message-queues.md#point-to-point-и-pubsub) и специализированных брокеров сообщений. Sidekiq работает в модели команд — point-to-point с конкурирующими consumers.

Когда Sidekiq-команды начинают обрастать сложной маршрутизацией (один job ставит 15 sub-jobs, и каждый из них — ещё несколько), это сигнал, что система может выиграть от перехода к событийной модели. Но для большинства Rails-приложений прямые команды проще и достаточны.

---

Задачи спроектированы: маленькие, атомарные, идемпотентные, каждая со своим retry. Их стало десять тысяч в час. Одного процесса с пятью потоками не хватает — как масштабировать?

---

<- [Сигналы и deploy](04-signals-and-deploy.md) | [Concurrency и масштабирование](06-concurrency-and-scaling.md) ->

## Sources

- [Sidekiq Wiki — Best Practices](https://github.com/sidekiq/sidekiq/wiki/Best-Practices)
- [Sidekiq Wiki — Batches](https://github.com/sidekiq/sidekiq/wiki/Batches)
- Mike Perham, [How does Sidekiq work?](https://www.mikeperham.com/how-sidekiq-works/)
