# Структуры данных Redis на практике

**Предпосылки:** [Клиенты и соединения](00-clients-and-connections.md), [STRING](../../databases/redis/data-structures/00-string.md), [HASH](../../databases/redis/data-structures/01-hash.md), [LIST](../../databases/redis/data-structures/02-list.md), [SET](../../databases/redis/data-structures/03-set.md), [ZSET](../../databases/redis/data-structures/04-sorted-set.md), [Pub/Sub](../../databases/redis/data-structures/08-pub-sub.md), [MULTI/EXEC](../../databases/redis/atomicity/01-multi-exec.md).

Теоретическая часть — в заметках по каждой структуре данных. Здесь — конкретные команды и Ruby-код, который используется в Rails-приложениях.

## STRING

STRING — простейшая структура: ключ → значение. В Rails чаще всего применяется для кеша с TTL и атомарных счётчиков.

```ruby
REDIS.with do |r|
  # Базовые операции
  r.set('user:123:name', 'John')
  r.get('user:123:name')              # → "John"

  # С автоудалением (TTL)
  r.set('session:abc', 'data', ex: 3600)  # истечёт через час
  r.ttl('session:abc')                     # сколько секунд осталось

  # Атомарный счётчик
  r.set('page:home:views', 0)
  r.incr('page:home:views')           # → 1
  r.incr('page:home:views')           # → 2
  r.incrby('page:home:views', 10)     # → 12
end
```

`INCR` возвращает новое значение. Это одна атомарная операция — увеличить и вернуть. Никакая другая команда не вклинится между чтением и записью, даже при десятках параллельных Puma-процессов.

Подробнее о STRING и его внутреннем устройстве: [STRING](../../databases/redis/data-structures/00-string.md).

## HASH

HASH хранит набор полей внутри одного ключа — аналог `Hash` в Ruby. В Rails удобен для хранения объекта целиком (профиль пользователя, состояние агента) без сериализации в JSON.

```ruby
REDIS.with do |r|
  # Запись
  r.hset("user:123", "name", "John")
  r.hset("user:123", "name", "John", "age", 30)  # несколько полей за раз

  # Чтение
  r.hget("user:123", "name")                      # одно поле → "John"
  r.hmget("user:123", "name", "age")              # несколько → ["John", "30"]
  r.hgetall("user:123")                           # все → Hash

  # Проверки
  r.hexists("user:123", "name")                   # есть ли поле?
  r.hkeys("user:123")                             # список полей

  # Атомарные операции
  r.hincrby("user:123", "login_count", 1)         # +1 к числовому полю
  r.hdel("user:123", "temporary_field")           # удалить поле
end
```

HASH экономит память по сравнению с отдельными STRING-ключами на каждое поле. Каждый ключ в Redis несёт накладные расходы (~50–70 байт на метаданные). Один HASH `user:123` с тремя полями — один overhead вместо трёх. Плюс `HGETALL` читает все поля атомарно за один round-trip.

Подробнее: [HASH](../../databases/redis/data-structures/01-hash.md).

## LIST

LIST — двусвязный список. Основное применение в Rails — очереди задач (Sidekiq использует `LPUSH` + `BRPOP`) и ограниченные списки (activity log).

```ruby
REDIS.with do |r|
  # Добавление
  r.lpush("queue:emails", "job1")      # в начало
  r.rpush("queue:emails", "job2")      # в конец

  # Извлечение
  r.lpop("queue:emails")               # забрать из начала
  r.rpop("queue:emails")               # забрать из конца
  r.brpop("queue:emails", timeout: 5)  # блокирующий pop (ждёт до 5 сек)

  # Чтение без удаления
  r.lrange("queue:emails", 0, -1)      # все элементы
  r.lrange("queue:emails", 0, 9)       # первые 10
  r.llen("queue:emails")               # длина

  # Обрезка
  r.ltrim("queue:emails", 0, 99)       # оставить только первые 100
end
```

Паттерн capped list — `LPUSH` + `LTRIM` — поддерживает фиксированный размер списка. Новый элемент добавляется в начало, затем `LTRIM` обрезает хвост. Полезно для хранения последних N действий пользователя:

```ruby
def log_activity(user_id, action)
  key = "user:#{user_id}:activity"

  REDIS.with do |r|
    r.lpush(key, { action: action, at: Time.now.iso8601 }.to_json)
    r.ltrim(key, 0, 99)  # оставить только последние 100
  end
end

def recent_activity(user_id, limit: 20)
  key = "user:#{user_id}:activity"

  REDIS.with do |r|
    r.lrange(key, 0, limit - 1).map { |json| JSON.parse(json) }
  end
end
```

Подробнее: [LIST](../../databases/redis/data-structures/02-list.md).

## SET

SET хранит неупорядоченное множество уникальных элементов. В Rails удобен для тегов, списков онлайн-пользователей, отслеживания уникальных сессий — всюду, где важна уникальность и быстрая проверка принадлежности.

```ruby
REDIS.with do |r|
  r.sadd("user:123:tags", "ruby")
  r.sadd("user:123:tags", "rails", "api")  # несколько за раз
  r.sadd("user:123:tags", "ruby")          # дубликат — игнорируется

  r.smembers("user:123:tags")              # все элементы → Set
  r.sismember("user:123:tags", "ruby")     # есть ли элемент? → true/false
  r.scard("user:123:tags")                 # количество элементов

  r.srem("user:123:tags", "api")           # удалить элемент
end
```

SET выигрывает у LIST, когда нужна уникальность или проверка «есть ли элемент?». `SISMEMBER` — O(1), тогда как поиск в LIST — O(N). Удаление конкретного элемента через `SREM` тоже O(1).

Операции над множествами позволяют находить пересечения, объединения и разности без загрузки данных в Ruby:

```ruby
REDIS.with do |r|
  r.sadd("user:1:interests", "ruby", "python", "go")
  r.sadd("user:2:interests", "python", "java", "go")

  # Общие интересы
  r.sinter("user:1:interests", "user:2:interests")
  # → ["python", "go"]

  # Все интересы вместе
  r.sunion("user:1:interests", "user:2:interests")
  # → ["ruby", "python", "go", "java"]

  # Что есть у первого, но нет у второго
  r.sdiff("user:1:interests", "user:2:interests")
  # → ["ruby"]
end
```

Подробнее: [SET](../../databases/redis/data-structures/03-set.md).

## ZSET (Sorted Set)

ZSET хранит элементы с числовым score и автоматически сортирует по нему. В Rails типичные применения — рейтинги (leaderboard), очереди с приоритетом и отложенные задачи (Sidekiq scheduled jobs используют ZSET с timestamp в качестве score).

```ruby
REDIS.with do |r|
  # zadd(key, score, member)
  r.zadd("leaderboard", 100, "alice")
  r.zadd("leaderboard", 250, "bob")
  r.zadd("leaderboard", 175, "carol")

  # Топ-3 по возрастанию score
  r.zrange("leaderboard", 0, 2)
  # → ["alice", "carol", "bob"]

  # Топ-3 по убыванию (лидеры)
  r.zrevrange("leaderboard", 0, 2)
  # → ["bob", "carol", "alice"]

  # С показом score
  r.zrevrange("leaderboard", 0, 2, with_scores: true)
  # → [["bob", 250.0], ["carol", 175.0], ["alice", 100.0]]

  # Позиция игрока в рейтинге (индекс с 0)
  r.zrevrank("leaderboard", "carol")
  # → 1 (второе место)

  # Увеличить score
  r.zincrby("leaderboard", 50, "alice")
  # alice теперь 150

  # Выбрать по диапазону score
  r.zrangebyscore("leaderboard", 100, 200)
  # → элементы со score от 100 до 200
end
```

ZSET решает проблему, с которой не справляется LIST: гарантированный порядок в распределённой системе. Если несколько сервисов пишут в LIST, порядок зависит от сетевых задержек. В ZSET порядок определяется score (например, timestamp события), а не порядком прихода в Redis. Дополнительные возможности — выборка по диапазону score, удаление конкретного элемента за O(log N), определение позиции в очереди:

```ruby
REDIS.with do |r|
  # Выбрать звонки старше 30 секунд
  threshold = Time.now.to_i - 30
  r.zrangebyscore("queue:calls", "-inf", threshold)

  # Удалить конкретный элемент из середины — O(log N)
  r.zrem("queue:calls", call_uuid)

  # Узнать позицию в очереди
  r.zrank("queue:calls", call_uuid)  # "Вы 5-й в очереди"
end
```

Подробнее: [ZSET](../../databases/redis/data-structures/04-sorted-set.md).

## Pub/Sub

Pub/Sub — механизм рассылки сообщений подписчикам в реальном времени. В Rails используется в первую очередь через ActionCable (подробнее: [паттерны использования](01-patterns.md)), но иногда применяется напрямую — для инвалидации кеша между процессами или внутренней сигнализации.

```ruby
# Публикация (отправитель)
REDIS.with do |r|
  r.publish("notifications:user:123", { event: "new_message", from: "alice" }.to_json)
end
# Возвращает количество подписчиков, получивших сообщение
```

Подписка блокирует соединение — подписавшийся клиент больше не может выполнять другие команды (GET, SET, INCR). Поэтому подписка создаётся на отдельном соединении, не из connection_pool:

```ruby
# Подписка (получатель) — отдельное соединение!
subscriber = Redis.new(url: ENV['REDIS_URL'])
subscriber.subscribe("notifications:user:123") do |on|
  on.message do |channel, message|
    data = JSON.parse(message)
    puts "Получено на #{channel}: #{data}"
  end
end
```

`PSUBSCRIBE` подписывается по маске — один подписчик ловит все каналы, подходящие под шаблон:

```ruby
subscriber = Redis.new(url: ENV['REDIS_URL'])
subscriber.psubscribe("notifications:*") do |on|
  on.pmessage do |pattern, channel, message|
    # pattern = "notifications:*"
    # channel = "notifications:user:123" (конкретный)
  end
end
```

Подробнее: [Pub/Sub](../../databases/redis/data-structures/08-pub-sub.md).

## MULTI/EXEC

`MULTI/EXEC` выполняет несколько команд атомарно. Между `MULTI` и `EXEC` команды буферизуются и выполняются единым блоком — никакая команда от другого клиента не вклинится.

```ruby
REDIS.with do |r|
  r.multi do |transaction|
    transaction.incr("counter:a")
    transaction.incr("counter:b")
    transaction.set("status", "done")
  end
  # Все три команды выполнятся атомарно
end
```

Ограничение `MULTI/EXEC`: нельзя использовать результат одной команды в другой внутри транзакции и нет условной логики (if/else). Для таких случаев — [Lua-скрипты](../../databases/redis/atomicity/02-lua-scripting.md).

Подробнее: [MULTI/EXEC](../../databases/redis/atomicity/01-multi-exec.md).
