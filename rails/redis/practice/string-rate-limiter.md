# Rate limiter на API-эндпоинте

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [STRING](../../../databases/redis/data-structures/00-string.md).

Биллинг-система выставляет партнёрам лимит — 100 запросов в минуту. При превышении API возвращает `429 Too Many Requests`. Требования: проверка и инкремент за одну атомарную операцию, автоматический сброс счётчика по окончании окна, минимальная задержка на каждый запрос.

HASH не подходит: нет TTL на отдельное поле, нельзя атомарно установить TTL при первом инкременте. LIST не подходит: нет атомарного `INCR`, подсчёт длины — это отдельная команда. STRING с `INCR` + `EXPIRE` решает задачу за один round-trip:

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

При 10 000 партнёров в памяти одновременно находится максимум 10 000 ключей по ~100 байт — меньше мегабайта. Латентность — один round-trip (два в начале нового окна).

Подробнее о STRING и его внутреннем устройстве: [STRING](../../../databases/redis/data-structures/00-string.md).
