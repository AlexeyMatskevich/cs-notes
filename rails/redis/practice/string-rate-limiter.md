---
tags:
  - domain/rails
  - theme/performance
  - type/pattern
aliases:
  - rate limiter
  - INCR
order: 3
---

# Rate limiter на API-эндпоинте

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [STRING](../../../databases/redis/data-structures/string.md).

Биллинг-система выставляет партнёрам лимит — 100 запросов в минуту. При превышении API возвращает `429 Too Many Requests`. Требования: атомарный инкремент счётчика, автоматический сброс по окончании окна, минимальная задержка на каждый запрос.

HASH не подходит: нет TTL на отдельное поле, нельзя атомарно установить TTL при первом инкременте. LIST не подходит: нет атомарного `INCR`, подсчёт длины — это отдельная команда. STRING с `INCR` + `EXPIRE` решает задачу:

```ruby
class RateLimiter
  LIMIT = 100
  WINDOW = 60 # секунд

  def initialize(redis_pool)
    @redis_pool = redis_pool
  end

  def allow?(partner_id)
    key = "ratelimit:#{partner_id}:#{current_window}"

    @redis_pool.with do |r|
      count = r.incr(key)
      r.expire(key, WINDOW) if count == 1  # TTL только при создании ключа
      count <= LIMIT
    end
  end

  private

  def current_window
    Time.now.to_i / WINDOW
  end
end
```

`INCR` на несуществующем ключе создаёт его со значением 1 — отдельного `SET` не нужно. `EXPIRE` вызывается только при `count == 1`, т.е. при первом запросе в окне. Все последующие инкременты не трогают TTL. Через 60 секунд ключ исчезает, и счётчик начинается заново.

`INCR` и `EXPIRE` — две отдельные команды, а не одна атомарная операция. В начале нового окна выполняются обе (два round-trip), в последующих запросах — только `INCR` (один round-trip). Если процесс упадёт после `INCR`, но до `EXPIRE`, ключ останется без TTL и счётчик не сбросится. На практике окно между двумя вызовами — микросекунды, и сценарий крайне редок. Если гарантия важна, можно обернуть пару в Lua-скрипт или вызывать `EXPIRE` для каждого запроса (идемпотентно, но лишний round-trip).

При 10 000 партнёров в памяти одновременно находится максимум 10 000 ключей по ~100 байт — меньше мегабайта.
