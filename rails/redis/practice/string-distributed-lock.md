# Распределённая блокировка для Sidekiq-воркеров

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [STRING и INCR](../../../databases/redis/data-structures/string.md), [Lua-скрипты](../../../databases/redis/atomicity/lua-scripting.md).

Два Sidekiq-воркера берут из очереди джобы на обработку одного и того же заказа — например, из-за retry после таймаута или дублирования сообщения. Оба читают заказ, оба вызывают платёжный шлюз, пользователю списывают деньги дважды. Результат: возврат, тикет в поддержку, потеря доверия.

Блокировка в памяти процесса (`Mutex`) не спасает — Sidekiq-воркеры работают в разных процессах, часто на разных серверах. Нужен общий ресурс, видимый всем процессам. Redis подходит: он доступен по сети, а `SET` с флагом NX даёт атомарную проверку «занят ли ресурс». Механика и ограничения подробно разобраны в [теории распределённых блокировок](../../../databases/redis/patterns/distributed-locks.md) — ниже конкретная реализация для Rails.

Ключевая деталь — `lock_id`, уникальный идентификатор, привязанный к процессу и потоку. Без него возникает проблема удаления чужой блокировки: воркер A захватил блокировку с TTL 30 секунд, работа заняла 35 секунд, TTL истёк, воркер B захватил блокировку, а воркер A при завершении выполнил `DEL` — удалив блокировку воркера B. С `lock_id` Lua-скрипт перед удалением атомарно проверяет, что значение ключа совпадает с нашим идентификатором.

```ruby
UNLOCK_SCRIPT = <<~LUA
  if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
  else
    return 0
  end
LUA

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

`nx: true` — Redis выполнит `SET` только если ключа нет. Если ключ уже существует (другой воркер держит блокировку), `SET` вернёт `nil`, и `with_lock` возвращает `false` без выполнения блока. `ex: ttl` — ключ автоматически удалится через `ttl` секунд: страховка на случай, если процесс упадёт, не выполнив `ensure`.

Для production-кода с повышенными требованиями к надёжности — гем `redlock`. Он реализует алгоритм Redlock: захват блокировки на нескольких независимых Redis-инстансах, чтобы падение одного не привело к потере блокировки:

```ruby
# Gemfile
gem 'redlock'

# Важно: один URL = один Redis = та же единая точка отказа.
# Для Redlock нужны несколько независимых Redis-инстансов.
lock_manager = Redlock::Client.new([
  ENV.fetch("REDIS_LOCK_1_URL"),
  ENV.fetch("REDIS_LOCK_2_URL"),
  ENV.fetch("REDIS_LOCK_3_URL"),
  ENV.fetch("REDIS_LOCK_4_URL"),
  ENV.fetch("REDIS_LOCK_5_URL")
])

lock_manager.lock("resource:order:123", 5000) do |locked|
  if locked
    process_order(123)
  else
    raise "Resource is busy"
  end
end
```

Базовый `with_lock` на одном Redis уменьшает вероятность двойной обработки, но не делает её невозможной при падении Redis, failover или долгой паузе клиента. Поэтому его применяют там, где операция уже [идемпотентна](../../../system-design/reliability-patterns.md#idempotency-безопасность-повторных-запросов) или дубль можно пережить.

Redlock уменьшает риск потери блокировки из-за отказа одного Redis, но не решает проблему «клиент завис дольше TTL и продолжил работу со старой блокировкой». Поэтому даже с Redlock для необратимых действий нужны внешние гарантии: идемпотентные ключи в платёжном шлюзе, уникальные ограничения в базе, fencing tokens или все вместе.

Практическое правило:

- один Redis + `SET NX EX` + Lua — координация и снижение дублей;
- несколько независимых Redis + Redlock — если блокировки на одном узле уже недостаточно;
- деньги, инвентарь, необратимые внешние действия — не полагаться только на lock, держать защиту на стороне ресурса.

## Sources

- Redis docs: distributed locks. <https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/>
- Redlock gem. <https://github.com/leandromoreira/redlock-rb>
