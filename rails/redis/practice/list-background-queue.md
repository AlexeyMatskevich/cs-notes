# Очередь фоновых задач с блокирующим ожиданием

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [LIST](../../../databases/redis/data-structures/02-list.md).

Сервис отправки email должен обрабатывать задачи по мере поступления. Несколько воркеров слушают одну очередь. Когда задач нет — воркер не должен тратить CPU на polling.

SET не подходит: нет понятия «первый» или «последний» элемент, порядок не определён. STRING не подходит: это одно значение, не коллекция. ZSET — overkill: score для простой FIFO-очереди не нужен. LIST с `LPUSH` + `BRPOP` решает задачу:

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
  def run
    loop do
      # BRPOP блокирует соединение до появления элемента или таймаута
      result = REDIS.with { |r| r.brpop("queue:emails", timeout: 5) }
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

`BRPOP` — ключевая операция. Воркер отдаёт соединение Redis'у и засыпает. Redis будит его только при появлении элемента в списке. Без `BRPOP` пришлось бы делать `RPOP` в цикле с `sleep` — это polling, который тратит CPU и добавляет задержку до величины `sleep`.

Паттерн capped list (`LPUSH` + `LTRIM`) полезен для хранения последних N действий без неограниченного роста:

```ruby
def log_activity(user_id, action)
  key = "user:#{user_id}:activity"

  REDIS.with do |r|
    r.lpush(key, { action: action, at: Time.now.iso8601 }.to_json)
    r.ltrim(key, 0, 99)  # только последние 100
  end
end
```

Подробнее: [LIST](../../../databases/redis/data-structures/02-list.md).
