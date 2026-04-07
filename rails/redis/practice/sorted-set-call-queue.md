# Очередь звонков колл-центра с приоритетами

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [ZSET](../../../databases/redis/data-structures/04-sorted-set.md).

Колл-центр принимает входящие звонки. У каждого звонка есть приоритет (VIP-клиенты обслуживаются первыми) и время постановки в очередь. Оператор берёт звонок с наивысшим приоритетом; при равном приоритете — самый ранний. Клиент видит свою позицию в очереди. Если клиент кладёт трубку — звонок удаляется из середины очереди.

LIST не подходит: вставка по приоритету — O(n), удаление из середины — O(n), определение позиции — O(n). SET не подходит: нет порядка. ZSET с составным score решает все задачи за O(log n):

```ruby
class CallQueue
  # Score = priority * 10_000_000_000 + (10_000_000_000 - timestamp)
  # Больший приоритет → бо́льший score → первый при ZREVRANGE
  # При равном приоритете — ранний звонок получает бо́льший score (вычитание timestamp)

  PRIORITY_MULTIPLIER = 10_000_000_000

  def initialize(redis_pool)
    @redis = redis_pool
    @key = "queue:calls"
  end

  def enqueue(call_id, priority: 1)
    score = priority * PRIORITY_MULTIPLIER + (PRIORITY_MULTIPLIER - Time.now.to_f)
    @redis.with { |r| r.zadd(@key, score, call_id) }
  end

  # Оператор берёт следующий звонок
  def dequeue
    @redis.with do |r|
      # ZPOPMAX — атомарно забрать элемент с наибольшим score
      result = r.zpopmax(@key)
      result&.first # call_id
    end
  end

  # Позиция клиента в очереди (от конца, т.к. сортировка по убыванию)
  def position(call_id)
    @redis.with do |r|
      rank = r.zrevrank(@key, call_id)
      rank ? rank + 1 : nil  # 1-based для отображения клиенту
    end
  end

  # Клиент положил трубку — удалить из середины за O(log n)
  def cancel(call_id)
    @redis.with { |r| r.zrem(@key, call_id) }
  end

  # Звонки, ожидающие больше max_wait_seconds
  # (мониторинг SLA — Service Level Agreement, договорное время ответа оператора)
  #
  # Составной score смешивает приоритет и время, поэтому простой ZRANGEBYSCORE
  # не может отфильтровать «все звонки старше X секунд» независимо от приоритета.
  # Обходим всю очередь и фильтруем в Ruby — при типичном размере очереди
  # (десятки-сотни звонков) это не проблема.
  def stale_calls(max_wait_seconds: 30)
    cutoff_time = Time.now.to_f - max_wait_seconds

    @redis.with do |r|
      r.zrangebyscore(@key, "-inf", "+inf", with_scores: true)
       .select { |_member, score|
         timestamp = PRIORITY_MULTIPLIER - (score % PRIORITY_MULTIPLIER)
         timestamp < cutoff_time
       }
       .map(&:first)
    end
  end
end
```

[`ZREVRANK`](../../../databases/redis/data-structures/04-sorted-set.md) за O(log n) возвращает позицию элемента — клиент видит «Вы 5-й в очереди». `ZREM` удаляет конкретный элемент из середины за O(log n). `ZRANGEBYSCORE` выбирает элементы по диапазону score — полезно для мониторинга SLA. Ни одна другая структура Redis не даёт все четыре операции одновременно.
