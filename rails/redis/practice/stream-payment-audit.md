# Аудит-лог платёжных операций

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [Stream](../../../databases/redis/data-structures/05-stream.md).

Платёжная система записывает каждую операцию (создание платежа, подтверждение, возврат) в лог. Несколько сервисов читают этот лог параллельно: один обновляет баланс мерчанта, другой отправляет уведомления, третий строит аналитику. Каждый сервис обрабатывает каждое событие ровно один раз. Если сервис упал — он должен продолжить с того места, где остановился.

LIST с `BRPOP` не подходит: элемент удаляется при чтении, и если обработчик упал после `BRPOP`, но до завершения обработки — событие потеряно. Pub/Sub не подходит: сообщения не сохраняются, пропущенное — потеряно навсегда. Stream с consumer groups решает обе проблемы:

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
  def run(consumer_name)
    REDIS.with do |r|
      loop do
        entries = r.xreadgroup(
          "balance_updaters", consumer_name,
          "payments:events", ">",
          count: 10, block: 5000
        )
        next unless entries&.any?

        entries.each do |_stream, messages|
          messages.each do |id, fields|
            update_merchant_balance(fields)
            r.xack("payments:events", "balance_updaters", id)
          end
        end
      end
    end
  end
end
```

Каждая consumer group (`balance_updaters`, `notifiers`, `analytics`) получает каждое сообщение независимо. Внутри группы сообщения распределяются между воркерами — ровно один воркер обрабатывает каждое сообщение. `XACK` подтверждает обработку. Если воркер упал между `XREADGROUP` и `XACK`, сообщение остаётся в pending-списке. Другой воркер может забрать зависшие сообщения с помощью `XAUTOCLAIM`:

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

Stream хранит историю: `XRANGE` позволяет перечитать прошлые события для отладки или восстановления. `XTRIM` с `MAXLEN` ограничивает размер потока, чтобы не расходовать память бесконечно.

Подробнее: [Stream](../../../databases/redis/data-structures/05-stream.md).
