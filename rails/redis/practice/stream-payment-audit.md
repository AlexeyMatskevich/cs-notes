# Аудит-лог платёжных операций

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [Stream](../../../databases/redis/data-structures/stream.md).

Платёжная система записывает каждую операцию (создание платежа, подтверждение, возврат) в лог. Несколько сервисов читают этот лог параллельно: один обновляет баланс мерчанта, другой отправляет уведомления, третий строит аналитику. Нельзя терять события, а после сбоя сервис должен продолжить чтение. При этом нужно принять важное ограничение: повторная доставка возможна, значит обработчики должны быть [идемпотентны](../../../system-design/reliability-patterns.md#idempotency-безопасность-повторных-запросов).

LIST с `BRPOP` не подходит: элемент удаляется при чтении, и если обработчик упал после `BRPOP`, но до завершения обработки — событие потеряно. Pub/Sub не подходит: сообщения не сохраняются, пропущенное — потеряно навсегда. Stream с consumer groups решает обе проблемы: хранит историю и даёт [at-least-once](../../../system-design/delivery-guarantees.md#at-least-once-не-менее-одного-раза) доставку внутри каждой группы.

```ruby
# Инициализация (один раз, например в db/seeds.rb или initializer)
REDIS.with do |r|
  r.xgroup(:create, "payments:events", "balance_updaters", "0", mkstream: true)
  r.xgroup(:create, "payments:events", "notifiers", "0", mkstream: true)
  r.xgroup(:create, "payments:events", "analytics", "0", mkstream: true)
rescue Redis::CommandError => e
  raise unless e.message.include?("BUSYGROUP")
end

# Продюсер: платёжный сервис
class PaymentEventPublisher
  def self.publish(event_type, payment_id, details)
    REDIS.with do |r|
      r.xadd("payments:events", {
        event: event_type,
        payment_id: payment_id,
        amount: details[:amount].to_s,
        merchant_id: details[:merchant_id],
        at: Time.now.iso8601
      })
    end
  end
end

# Консьюмер: сервис баланса мерчанта
class MerchantBalanceWorker
  def initialize
    # BLOCK удерживает соединение, поэтому у стрим-воркера оно своё.
    @redis = Redis.new(url: ENV.fetch("REDIS_STREAMS_URL", ENV.fetch("REDIS_URL")))
  end

  def run(consumer_name)
    loop do
      entries = @redis.xreadgroup(
        "balance_updaters", consumer_name,
        "payments:events", ">",
        count: 10, block: 5000
      )
      next unless entries&.any?

      entries.each do |_stream, messages|
        messages.each do |id, fields|
          update_merchant_balance(fields)
          @redis.xack("payments:events", "balance_updaters", id)
        end
      end
    end
  end
end
```

Каждая consumer group (`balance_updaters`, `notifiers`, `analytics`) получает каждое сообщение независимо. Внутри группы новое сообщение в каждый момент времени принадлежит одному воркеру, пока не подтверждено через `XACK`. Если воркер упал между `XREADGROUP` и `XACK`, сообщение остаётся в pending-списке. Другой воркер может забрать зависшие сообщения с помощью `XAUTOCLAIM`:

```ruby
# Перехват зависших сообщений (запускать периодически)
def claim_stale_messages(group, consumer_name, stream, idle_ms: 60_000)
  REDIS.with do |r|
    result = r.xautoclaim(stream, group, consumer_name, idle_ms, "0")
    claimed = result[1]

    claimed.each do |id, fields|
      yield id, fields
      r.xack(stream, group, id)
    end
  end
end
```

Если `MerchantBalanceWorker` упал после `update_merchant_balance(fields)`, но до `XACK`, другое приложение позже перезаберёт то же сообщение и вызовет обработчик повторно. Поэтому эффект обработки нужно делать идемпотентным: например, сохранять `stream message ID` или бизнесовый `payment_id + event` в таблице обработанных событий и не проводить одну и ту же операцию дважды.

В терминах [очередей сообщений](../../../system-design/message-queues.md#две-модели-очередь-сообщений-и-лог) Stream здесь ближе к логу, чем к простой очереди: события сохраняются, читаются по позиции и могут быть перечитаны после сбоя.

[Stream](../../../databases/redis/data-structures/stream.md) хранит историю: `XRANGE` позволяет перечитать прошлые события для отладки или восстановления. `XTRIM` с `MAXLEN` ограничивает размер потока, чтобы не расходовать память бесконечно.

## Sources

- Redis documentation: `XREADGROUP`. <https://redis.io/docs/latest/commands/xreadgroup/>
- Redis documentation: `XAUTOCLAIM`. <https://redis.io/docs/latest/commands/xautoclaim/>
- Redis documentation: Streams. <https://redis.io/docs/latest/develop/data-types/streams/>
