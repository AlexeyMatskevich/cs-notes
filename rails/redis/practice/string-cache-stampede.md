---
tags:
  - domain/rails
  - theme/caching
  - theme/performance
  - type/pattern
aliases:
  - cache stampede
  - thundering herd
order: 3
---

# Защита от cache stampede

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [STRING](../../../databases/redis/data-structures/string.md), [Lua-скрипты](../../../databases/redis/atomicity/lua-scripting.md), [теория cache stampede](../../../system-design/caching.md#cache-stampede).

Популярный кеш с TTL 5 минут хранит результат тяжёлого SQL-запроса. В момент, когда TTL истекает, 1000 параллельных запросов обнаруживают пустой кеш и одновременно отправляют один и тот же запрос в PostgreSQL. База получает лавину одинаковых тяжёлых запросов и деградирует — p99 latency (время, в которое укладываются 99% запросов) подскакивает, вплоть до таймаутов у пользователей.

Это cache stampede (thundering herd). Два подхода к защите: блокировка на перестроение и упреждающее обновление. Подробнее о теории: [кеширование в Redis](../../../databases/redis/patterns/caching.md) и [общая заметка о caching](../../../system-design/caching.md#cache-stampede).

## Блокировка на перестроение

Первый запрос, обнаруживший пустой кеш, захватывает блокировку через `SET NX EX` и перестраивает кеш. Остальные запросы видят блокировку, ждут и делают retry:

```ruby
UNLOCK_SCRIPT = <<~LUA
  if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
  else
    return 0
  end
LUA

def get_cached_data(key, ttl: 300, max_retries: 50)
  max_retries.times do
    cached = REDIS.with { |r| r.get(key) }
    return JSON.parse(cached) if cached

    lock_key = "lock:#{key}"
    lock_id = SecureRandom.uuid
    acquired = REDIS.with { |r| r.set(lock_key, lock_id, nx: true, ex: 30) }

    if acquired
      begin
        data = expensive_database_query()
        REDIS.with { |r| r.set(key, data.to_json, ex: ttl) }
        return data
      ensure
        REDIS.with { |r| r.eval(UNLOCK_SCRIPT, keys: [lock_key], argv: [lock_id]) }
      end
    end

    sleep(0.1)
  end

  # Все retry исчерпаны — выполнить запрос напрямую
  expensive_database_query()
end
```

Один процесс выполняет запрос к PostgreSQL, остальные ждут 100ms и перечитывают кеш. Блокировка с TTL 30 секунд — страховка на случай, если процесс-перестроитель упадёт. `lock_id` и Lua-скрипт нужны по той же причине, что и в [распределённой блокировке](string-distributed-lock.md): если TTL истёк, другой процесс уже захватил lock, и обычный `DEL` мог бы снести чужую блокировку.

Важная деталь — границы ресурса. Redis-соединение держится только на коротких операциях `GET` / `SET` / `SET NX` / `EVAL`. `sleep` и `expensive_database_query()` выполняются вне `REDIS.with`, чтобы не занимать соединение из обычного пула приложения на всё время ожидания и SQL.

Цикл с ограниченным числом retry вместо рекурсии: рекурсия при 1000 одновременных запросах с глубоким retry рискует переполнить стек.

## Упреждающее обновление (early expiration)

Блокировка спасает от лавины, но ценой задержки: пока один запрос перестраивает кеш, остальные ждут. Если кеш можно обновить *до* истечения TTL, задержки не будет вовсе.

Если TTL = 300 секунд и early_ttl = 60 секунд, то при оставшемся TTL меньше 60 секунд запрос возвращает текущее (ещё валидное) значение и ставит фоновую задачу на обновление:

```ruby
def get_cached_data(key, ttl: 300, early_ttl: 60)
  cached, remaining_ttl = REDIS.with do |r|
    value = r.get(key)
    [value, value ? r.ttl(key) : nil]
  end

  if cached && remaining_ttl > early_ttl
    return JSON.parse(cached)
  end

  if cached && remaining_ttl <= early_ttl
    enqueued = REDIS.with { |r| r.set("refresh:#{key}", 1, nx: true, ex: 30) }
    RefreshCacheJob.perform_async(key) if enqueued
    return JSON.parse(cached)
  end

  refresh_cache(key, ttl)
end
```

В зоне early expiration запросы продолжают отдавать текущее значение, а фоновый refresh ставится не чаще одного раза за короткое окно благодаря `SET NX EX` на ключе `refresh:*`. Это не защищает от всех дублей навсегда, но убирает бурст из тысяч одинаковых джобов в секунду.

Кеш обновляется до истечения TTL — одновременного обращения к PostgreSQL не происходит. Подход работает для данных с предсказуемым TTL и регулярным трафиком. Для редких, но тяжёлых запросов лучше подходит блокировка.

| Подход | Когда использовать |
|--------|-------------------|
| Блокировка | Редкие, тяжёлые запросы |
| Early expiration | Популярные данные с регулярным трафиком |
| Оба вместе | Критичные высоконагруженные системы |

## Sources

- Redis docs: distributed locks and safe unlock. <https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/>
