---
tags:
  - domain/rails
  - theme/queues
  - type/pattern
aliases:
  - BRPOP
  - background queue
order: 3
---

# Очередь фоновых задач с блокирующим ожиданием

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [LIST](../../../databases/redis/data-structures/list.md).

Сервис отправки email должен обрабатывать задачи по мере поступления. Несколько воркеров слушают одну очередь. Когда задач нет — воркер не должен тратить CPU на polling.

На языке system design это [[system-design/message-queues#temporal-decoupling-развязка-во-времени|temporal decoupling]]: HTTP-запрос только ставит задачу, а выполнение происходит позже в отдельном воркере.

SET не подходит: нет понятия «первый» или «последний» элемент, порядок не определён. STRING не подходит: это одно значение, не коллекция. ZSET здесь избыточен: score для простой FIFO-очереди не нужен. LIST с `LPUSH` + `BRPOP` решает задачу:

```ruby
# Продюсер: Rails-контроллер после действия пользователя
class EmailEnqueuer
  def self.enqueue(payload)
    REDIS.with do |r|
      r.lpush("queue:emails", payload.to_json)
    end
  end
end

# Консьюмер: фоновый процесс (воркер)
class EmailWorker
  def initialize
    # BRPOP держит соединение в ожидании, поэтому воркеру нужен
    # отдельный клиент, а не обычный пул Puma.
    @redis = Redis.new(url: ENV.fetch("REDIS_QUEUE_URL", ENV.fetch("REDIS_URL")))
  end

  def run
    loop do
      # BRPOP блокирует соединение до появления элемента или таймаута
      result = @redis.brpop("queue:emails", timeout: 5)
      next unless result

      _queue, payload = result
      process(JSON.parse(payload))
    end
  end

  private

  def process(data)
    UserMailer.send(data["template"], data["to"], data["params"]).deliver_now
  end
end
```

[`BRPOP`](../../../databases/redis/data-structures/list.md) — ключевая операция. Воркер отдаёт выделенное соединение Redis'у и засыпает. Redis будит его только при появлении элемента в списке. Без `BRPOP` пришлось бы делать `RPOP` в цикле с `sleep` — это polling, который тратит CPU и добавляет задержку до величины `sleep`.

Это простая очередь с гарантией не выше [[system-design/delivery-guarantees#at-most-once-не-более-одного-раза|at-most-once]]: после `BRPOP` элемент исчезает из Redis. Если процесс упал после получения задачи, но до завершения обработки, задача потеряна. Для учебного примера этого достаточно; для подтверждений обработки и recovery нужны [Stream](stream-payment-audit.md) или готовый фреймворк вроде Sidekiq.

По модели доставки это [[system-design/message-queues#point-to-point-и-pubsub|point-to-point]]: каждую задачу должен получить один воркер, а не все подписчики сразу.

Если нужно ограничить длину списка (например, хранить только последние N записей), применяется паттерн `LPUSH` + `LTRIM` — см. [ограниченный лог активности](list-capped-activity-log.md).
