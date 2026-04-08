# Retry и обработка ошибок

**Предпосылки:** [архитектура Sidekiq](architecture.md), [жизненный цикл задачи](job-lifecycle.md), [гарантии и идемпотентность](guarantees.md), [reliability patterns](../../system-design/reliability-patterns.md).

<- [Гарантии и идемпотентность](guarantees.md) | [Сигналы и deploy](signals-and-deploy.md) ->

Задача может быть потеряна при crash — но это edge case. Гораздо чаще задача просто падает с ошибкой: email-сервис вернул 500, база данных не ответила за timeout, сторонний API ограничил частоту запросов. Во всех этих случаях имеет смысл попробовать ещё раз через некоторое время.

## Как Sidekiq перехватывает ошибку

Исключение из `perform` не уходит в никуда. Processor оборачивает server middleware chain в `JobRetry` — это не middleware, а обёртка уровнем выше. Если `perform` (или любой server middleware) выбросит исключение, оно поднимается до `JobRetry#process_retry`:

```
Processor
  └── JobRetry (перехватывает исключение)
        └── server middleware chain
              └── perform(args)
```

`JobRetry` увеличивает счётчик попыток в хеше задачи и кладёт задачу в sorted set `retry` через `ZADD`:

```
ZADD retry <время_следующей_попытки> '<обновлённый_json>'
```

Score — Unix timestamp следующей попытки. Задача лежит в `retry`, пока Poller не обнаружит, что её время наступило, и не переместит в рабочую очередь.

## Формула задержки

Sidekiq вычисляет задержку между попытками по формуле:

```
delay = (count ** 4) + 15 + (rand(10) * (count + 1))
```

Три компоненты:

**count⁴** — экспоненциальный backoff. В [reliability patterns](../../system-design/reliability-patterns.md#retry-with-backoff-повторная-попытка) типичный backoff использует степень 2 (удвоение). Sidekiq использует степень 4 — гораздо более агрессивный рост. Первые попытки идут быстро (секунды), последние — через дни. Логика: если ошибка не прошла за первые пять попыток, скорее всего нужен deploy фикса, а не ещё одна попытка через минуту.

**+15** — минимальная задержка 15 секунд даже при count=0. Моментальный retry редко полезен — [transient failure](../../system-design/reliability-patterns.md#transient-vs-permanent-failure) обычно длится хотя бы несколько секунд.

**rand(10) × (count + 1)** — jitter (случайное смещение). Если 1000 задач упали одновременно (сервис лёг), без jitter все 1000 попытаются retry в одну секунду, создавая thundering herd — лавину одновременных запросов, которая перегружает восстанавливающийся сервис. Случайное смещение распределяет нагрузку.

Примерные значения (count — номер retry, начиная с 0; первое выполнение не учитывается):

| Retry (count) | Задержка | Суммарное время |
|---------|----------|----------------|
| 0 | ~15–25 сек | 15 сек |
| 1 | ~16–36 сек | ~1 мин |
| 4 | ~270–320 сек | ~15 мин |
| 10 | ~2.8–3 часа | ~12 часов |
| 24 | ~19–20 дней | ~21 день |

25 попыток ≈ 21 день — достаточно времени, чтобы заметить проблему, написать фикс и задеплоить.

## Retry sorted set и Poller

Sorted set `retry` работает как [delayed queue](../../databases/redis/patterns/queues.md#отложенные-задачи-delayed-queue): score = timestamp следующей попытки. Poller периодически выполняет `ZRANGEBYSCORE retry -inf <now>` и перемещает «созревшие» задачи в рабочие очереди.

По умолчанию `ZRANGEBYSCORE` + `LPUSH` — не атомарная операция. Crash между ними может привести к дубликату или потере. Reliable scheduler (Pro) решает это через Lua-скрипт.

Интервал проверки Poller адаптируется: чем больше Sidekiq-процессов в кластере, тем реже каждый процесс проверяет sorted sets. Это предотвращает thundering herd на уровне инфраструктуры — по той же логике, что jitter в формуле retry предотвращает его на уровне задач.

## Dead set: когда retry бессмысленен

После 25 попыток (по умолчанию) задача переносится в sorted set `dead` — это [Dead Letter Queue](../../system-design/message-queues.md#dead-letter-queue). Dead set ограничен: максимум 10 000 задач, хранение 6 месяцев. Задачи из dead set можно вручную запустить заново через Web UI.

Не каждая ошибка заслуживает 25 попыток. [Transient failure](../../system-design/reliability-patterns.md#transient-vs-permanent-failure) (API down на час) — retry поможет. Permanent failure (невалидный email, несуществующий order_id) — 25 попыток бессмысленны, задача займёт место в retry set, потратит ресурсы и всё равно окажется в dead.

## Настройка retry-поведения

Стандартные 25 попыток подходят не для каждой задачи. Внешний API с rate limit ответит через час — 5 попыток достаточно. Невалидные данные не починятся за 21 день retry — бессмысленно пробовать, лучше отключить retry и сразу отправить в dead set. API со строгим rate limit вернёт заголовок Retry-After — здесь нужна кастомная формула вместо стандартного backoff.

```ruby
class SendEmailJob
  include Sidekiq::Job

  # 5 попыток — достаточно для transient errors вроде таймаутов SMTP
  sidekiq_options retry: 5

  # retry: false — при ошибке задача отбрасывается (не попадает ни в retry, ни в dead set)
  # retry: 0 — при ошибке задача сразу в dead set (без retry, но можно запустить вручную)
  # sidekiq_options retry: false

  # Кастомная формула задержки
  sidekiq_retry_in do |count, exception, job_hash|
    case exception
    when RateLimitError
      3600  # час — API сказал "слишком часто"
    else
      :default  # стандартная формула
    end
  end

  # Обработка исчерпания попыток (per-job)
  sidekiq_retries_exhausted do |job, exception|
    Notifier.alert("Job #{job['jid']} died: #{exception.message}")
  end
end
```

Глобальный обработчик для всех задач, попавших в dead set:

```ruby
Sidekiq.configure_server do |config|
  config.death_handlers << ->(job, ex) {
    ErrorTracker.notify(ex, job: job)
  }
end
```

---

Retry обрабатывает ошибки кода — email-сервис вернул 500, retry подождёт и попробует снова. Но что если причина не в коде, а в инфраструктуре: нужен deploy новой версии, перезапуск сервера, обновление зависимостей? Как остановить Sidekiq, не теряя in-flight задачи?

---

<- [Гарантии и идемпотентность](guarantees.md) | [Сигналы и deploy](signals-and-deploy.md) ->

## Sources

- [Sidekiq Wiki — Error Handling](https://github.com/sidekiq/sidekiq/wiki/Error-Handling)
- Mike Perham, [How does Sidekiq work?](https://www.mikeperham.com/how-sidekiq-works/)
