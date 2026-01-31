# Паттерны использования Redis в Rails

**Предпосылки:** [Клиенты и соединения](00-clients-and-connections.md), [Pub/Sub](../../databases/redis/data-structures/08-pub-sub.md), [STRING и INCR](../../databases/redis/data-structures/00-string.md), [LIST](../../databases/redis/data-structures/02-list.md), [Lua-скрипты](../../databases/redis/atomicity/02-lua-scripting.md).

## ActionCable: координация WebSocket'ов между процессами

Rails-приложение на Puma запускает несколько процессов (worker'ов). Каждый процесс держит свой набор WebSocket-соединений. Процессы изолированы — у них нет общей памяти. Когда Sidekiq-джоб хочет отправить сообщение пользователю через WebSocket, он не знает, к какому Puma-процессу подключён этот пользователь, и не может напрямую достучаться до чужого сокета.

ActionCable решает проблему через Redis [Pub/Sub](../../databases/redis/data-structures/08-pub-sub.md). Каждый Puma-процесс при старте создаёт отдельный поток, который подписывается на Redis-канал:

```ruby
# Под капотом ActionCable делает примерно следующее:
subscriber = Redis.new(url: ENV['REDIS_URL'])
subscriber.psubscribe("_action_cable_internal_*") do |on|
  on.pmessage do |pattern, channel, message|
    # ActionCable определяет, какие WebSocket'ы в этом процессе
    # подписаны на channel, и рассылает им message
  end
end
```

Вызов `psubscribe` блокирует поток навсегда — он только слушает. Поэтому ActionCable выделяет для подписки отдельный поток, не занимая потоки Puma, которые обрабатывают HTTP-запросы и WebSocket I/O.

Когда код публикует сообщение в канал ActionCable (например, `ActionCable.server.broadcast("chat_42", data)`), происходит `PUBLISH` в Redis. Все Puma-процессы получают это сообщение через свои subscriber-потоки. Каждый процесс проверяет, есть ли у него WebSocket-соединения, подписанные на этот канал, и отправляет данные только нужным клиентам.

Один паттерн `psubscribe("_action_cable_internal_*")` ловит все сообщения для всех каналов ActionCable. Маршрутизация по конкретным каналам (`chat_42`, `notifications_user_123`) происходит уже внутри ActionCable на стороне Ruby.

Итого на каждый Puma-процесс: 5 потоков Puma (HTTP + WebSocket I/O) + 1 поток Redis subscriber. Этот дополнительный поток держит одно выделенное TCP-соединение к Redis, которое не входит в connection_pool приложения.

Конфигурация ActionCable:

```yaml
# config/cable.yml
production:
  adapter: redis
  url: <%= ENV.fetch('REDIS_URL') %>
  channel_prefix: myapp_production
```

`channel_prefix` добавляет префикс ко всем каналам, чтобы несколько приложений могли разделять один Redis без коллизий имён.

## Rate limiting

Задача — ограничить количество запросов с одного IP-адреса до N в минуту. Наивный подход (счётчик в памяти процесса) не работает: Puma-процессы изолированы, каждый считает только свои запросы.

Redis-решение использует [INCR](../../databases/redis/data-structures/00-string.md) — атомарную команду «увеличить на 1 и вернуть новое значение». Ключ содержит IP и номер текущей минуты, TTL автоматически удаляет старые ключи:

```ruby
def allow_request?(ip)
  REDIS.with do |r|
    minute = Time.now.to_i / 60
    key = "ratelimit:#{ip}:#{minute}"

    count = r.incr(key)
    r.expire(key, 60) if count == 1

    count <= 100
  end
end
```

`INCR` на несуществующем ключе создаёт его со значением 1. `expire` устанавливается только при `count == 1` (создание ключа), потому что повторный вызов `expire` сбросит таймер. Через минуту деление `Time.now.to_i / 60` даст следующее число — запросы пойдут в новый ключ, а старый удалится по TTL.

Все Puma-процессы инкрементируют один и тот же ключ в Redis. INCR атомарен — гонки невозможны. Если один процесс получил `count = 100`, следующий `INCR` от любого процесса вернёт 101, и запрос будет отклонён.

## Распределённые блокировки

Когда несколько процессов или Sidekiq-воркеров могут одновременно обработать один и тот же ресурс (например, один заказ), нужен механизм блокировки. Блокировка в памяти процесса (`Mutex`) не работает между процессами. Redis предоставляет примитивы для распределённой блокировки.

Базовый подход — `SET` с флагами `NX` (only if Not eXists) и `EX` (Expire). Подробнее о механике: [распределённые блокировки](../../databases/redis/patterns/02-distributed-locks.md).

```ruby
def with_lock(resource_id, ttl: 30)
  key = "lock:#{resource_id}"
  lock_id = "#{Process.pid}:#{Thread.current.object_id}:#{SecureRandom.hex(8)}"

  acquired = REDIS.with { |r| r.set(key, lock_id, nx: true, ex: ttl) }
  return false unless acquired

  begin
    yield
  ensure
    REDIS.with { |r| r.eval(UNLOCK_SCRIPT, keys: [key], argv: [lock_id]) }
  end
end
```

`nx: true` — Redis выполнит `SET` только если ключа нет. Если ключ уже существует (другой процесс держит блокировку), `SET` вернёт `nil`. `ex: ttl` — ключ автоматически удалится через `ttl` секунд. Это страховка: если процесс упадёт, не выполнив `ensure`, блокировка не зависнет навсегда.

### Проблема удаления чужой блокировки

`lock_id` — уникальный идентификатор, привязанный к процессу и потоку. Он нужен, чтобы при освобождении блокировки не удалить чужую. Сценарий: процесс A захватил блокировку с TTL 30 секунд, работа заняла 35 секунд. На 30-й секунде TTL истёк, блокировка удалилась. На 31-й секунде процесс B захватил блокировку. На 35-й секунде процесс A закончил работу и вызвал `DEL` — удалив блокировку процесса B.

Решение — перед удалением проверить, что значение ключа совпадает с нашим `lock_id`. Но `GET` + `DEL` — две команды, между которыми может произойти что угодно. Атомарность обеспечивает [Lua-скрипт](../../databases/redis/atomicity/02-lua-scripting.md):

```ruby
UNLOCK_SCRIPT = <<~LUA
  if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
  else
    return 0
  end
LUA
```

Redis исполняет Lua-скрипт атомарно: никакая другая команда не выполнится между `GET` и `DEL`. Если значение ключа не совпадает с нашим `lock_id` (блокировка уже чужая), скрипт возвращает 0 и ничего не удаляет.

### Гем redlock

Для production-кода лучше использовать гем `redlock`, который реализует алгоритм [Redlock](../../databases/redis/patterns/02-distributed-locks.md) — захват блокировки на нескольких независимых Redis-инстансах для устойчивости к падению одного из них:

```ruby
# Gemfile
gem 'redlock'

# Использование
lock_manager = Redlock::Client.new([ENV['REDIS_URL']])

lock_manager.lock("resource:123", 5000) do |locked|
  if locked
    process_order(123)
  else
    raise "Resource is busy"
  end
end
```

Под капотом `redlock` использует тот же Lua-скрипт для безопасного освобождения блокировки.

## Защита от cache stampede

Cache stampede (thundering herd) — ситуация, когда TTL популярного кеша истекает и сотни параллельных запросов одновременно идут в PostgreSQL за одними и теми же данными. PostgreSQL получает лавину одинаковых тяжёлых запросов и может деградировать.

Подробнее о теории: [кеширование](../../databases/redis/patterns/00-caching.md).

### Блокировка на перестроение

Первый запрос, обнаруживший пустой кеш, захватывает блокировку и перестраивает кеш. Остальные запросы ждут и делают retry:

```ruby
def get_cached_data(key, ttl: 300)
  REDIS.with do |r|
    cached = r.get(key)
    return JSON.parse(cached) if cached

    lock_key = "lock:#{key}"
    acquired = r.set(lock_key, "1", nx: true, ex: 30)

    if acquired
      data = expensive_database_query()
      r.set(key, data.to_json, ex: ttl)
      r.del(lock_key)
      data
    else
      sleep(0.1)
      get_cached_data(key, ttl: ttl)
    end
  end
end
```

Один процесс выполняет запрос к PostgreSQL, остальные ждут 100ms и перечитывают кеш. Блокировка с TTL 30 секунд — страховка на случай, если процесс-перестроитель упадёт.

### Упреждающее обновление (early expiration)

Вместо того чтобы ждать истечения TTL, кеш обновляется в фоне заранее. Если TTL = 300 секунд и early_ttl = 60 секунд, то при оставшемся TTL меньше 60 секунд запрос возвращает текущее (ещё валидное) значение и ставит фоновую задачу на обновление:

```ruby
def get_cached_data(key, ttl: 300, early_ttl: 60)
  REDIS.with do |r|
    cached = r.get(key)
    remaining_ttl = r.ttl(key)

    if cached && remaining_ttl > early_ttl
      return JSON.parse(cached)
    end

    if cached && remaining_ttl <= early_ttl
      RefreshCacheJob.perform_async(key)
      return JSON.parse(cached)
    end

    refresh_cache(key, ttl)
  end
end
```

Кеш обновляется до истечения TTL → одновременного обращения к PostgreSQL не происходит. Подход работает для данных с предсказуемым TTL и регулярным трафиком. Для редких, но тяжёлых запросов лучше подходит блокировка.

| Подход | Когда использовать |
|--------|-------------------|
| Блокировка | Редкие, тяжёлые запросы |
| Early expiration | Популярные данные с регулярным трафиком |
| Оба вместе | Критичные высоконагруженные системы |

## Ограниченные списки (capped lists)

Задача — хранить последние N действий пользователя (activity log, история уведомлений). PostgreSQL справится, но каждая запись — это INSERT + обновление индексов + VACUUM мёртвых строк. Для данных, которые нужны только «последние 100 штук» и потеря которых не критична, Redis [LIST](../../databases/redis/data-structures/02-list.md) проще и быстрее.

`LPUSH` добавляет элемент в начало списка, `LTRIM` обрезает список до заданной длины. Выполненные подряд, они поддерживают фиксированный размер:

```ruby
def log_activity(user_id, action)
  key = "user:#{user_id}:activity"

  REDIS.with do |r|
    r.lpush(key, { action: action, at: Time.now.iso8601 }.to_json)
    r.ltrim(key, 0, 99)
  end
end

def recent_activity(user_id, limit: 20)
  key = "user:#{user_id}:activity"

  REDIS.with do |r|
    r.lrange(key, 0, limit - 1).map { |json| JSON.parse(json) }
  end
end
```

`LPUSH` + `LTRIM` — две команды, а не одна, но порядок гарантирует корректность: после `LPUSH` список может быть на 1 элемент длиннее лимита, `LTRIM` тут же обрезает. Даже если процесс упадёт между ними, список будет содержать 101 элемент вместо 100 — не критично.

`LRANGE(key, 0, limit - 1)` возвращает элементы с начала списка (самые свежие) без удаления. `LPUSH` и `LTRIM` выполняются за O(1) (LTRIM удаляет элементы с конца, и при обрезке на 1 элемент это константа). `LRANGE` — O(limit).
