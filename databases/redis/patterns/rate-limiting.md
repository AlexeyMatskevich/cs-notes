---
tags:
  - domain/redis
  - theme/performance
  - type/pattern
aliases:
  - Rate Limiting
  - Fixed Window
  - Sliding Window
  - Token Bucket
order: 26
---

# Rate limiting

**Предпосылки:** [String](../data-structures/string.md), [Hash](../data-structures/hash.md), [Sorted Set](../data-structures/sorted-set.md), [Lua-скрипты](../atomicity/lua-scripting.md).

← [Кеширование](caching.md) | [Распределённые блокировки](distributed-locks.md) →

Бот отправляет 10 000 запросов в секунду к API каталога товаров. Сервер перегружен, честные пользователи получают таймауты. Нужен механизм, который считает запросы от каждого клиента и отклоняет лишние — [[system-design/reliability-patterns#rate-limiting-ограничение-входящей-нагрузки|rate limiter]]. Redis подходит для этой задачи: атомарные счётчики, микросекундная латентность и TTL позволяют реализовать проверку за одно обращение на каждый запрос.

## Fixed window

Простейший подход: ключ содержит идентификатор окна (текущая минута), значение — счётчик запросов. `INCR` атомарно увеличивает счётчик и возвращает новое значение. Если значение превышает лимит — запрос отклоняется.

```redis-cli
-- IP 192.168.1.1, лимит 100 запросов в минуту
-- ключ включает текущую минуту (unix time — секунды с 1 января 1970, / 60):
INCR ratelimit:192.168.1.1:28421876
-- → 1 (первый запрос в этом окне)
-- TTL устанавливается только при создании ключа (когда INCR вернул 1):
-- if result == 1 then EXPIRE ratelimit:... 60
```

Недостаток: на границе окон возможен всплеск. Если за последнюю секунду минуты пришло 100 запросов и за первую секунду следующей минуты ещё 100 — за 2 секунды прошло 200 запросов при лимите 100/мин.

## Sliding window log

Всплеск на границе окон — не теоретическая проблема: для API с лимитом 1000 req/min пропуск 2000 запросов за 2 секунды может вызвать каскадную деградацию. Для точного ограничения используется SORTED SET, где каждый запрос — элемент с timestamp как score.

```redis-cli
-- добавить текущий запрос
ZADD ratelimit:192.168.1.1 1700000060.123 "req-uuid-1"

-- удалить записи старше 60 секунд
ZREMRANGEBYSCORE ratelimit:192.168.1.1 0 1700000000.123

-- подсчитать запросы в окне
ZCARD ratelimit:192.168.1.1
-- → если больше лимита — отклонить
```

Преимущество: скользящее окно без всплесков на границах. Недостаток: каждый запрос хранится в [ZSET](../data-structures/sorted-set.md), потребление памяти пропорционально количеству запросов в окне. Для высоконагруженных систем это может быть дорого.

На практике эти три операции оборачивают в [Lua-скрипт](../atomicity/lua-scripting.md) для атомарности:

```redis-cli
EVAL "
  local key = KEYS[1]
  local now = tonumber(ARGV[1])
  local window = tonumber(ARGV[2])
  local limit = tonumber(ARGV[3])

  redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
  local count = redis.call('ZCARD', key)

  if count < limit then
    redis.call('ZADD', key, now, ARGV[4])
    redis.call('EXPIRE', key, window)
    return 1
  else
    return 0
  end
" 1 ratelimit:192.168.1.1 1700000060.123 60 100 "req-uuid-1"
```

## Sliding window counter

Sliding window log точен, но дорог по памяти. Fixed window дёшев, но допускает всплески. Sliding window counter — компромисс между fixed window и sliding window log. Используются два fixed window (текущее и предыдущее). Оценка количества запросов в скользящем окне:

```text
count = prev_window_count × (1 - elapsed/window_size) + current_window_count
```

Если текущая минута прошла на 40% (24 секунды), то: `count = prev × 0.6 + current`. Точность приближённая, но потребление памяти — два счётчика вместо N записей в [ZSET](../data-structures/sorted-set.md).

## Token bucket

Предыдущие подходы считают запросы за окно и жёстко отклоняют всё сверх лимита. Но для некоторых API допустим короткий всплеск (burst), если средняя нагрузка остаётся в норме — например, мобильный клиент после потери связи отправляет пачку накопившихся запросов. Token bucket работает иначе: Redis хранит количество доступных «токенов». Каждый запрос забирает токен, токены пополняются с фиксированной скоростью. Если токенов нет — запрос отклоняется.

```redis-cli
-- Lua-скрипт для token bucket:
-- KEYS[1] = ключ для хранения {tokens, last_refill_time}
-- ARGV[1] = now, ARGV[2] = rate (токенов/сек), ARGV[3] = capacity

EVAL "
  local key = KEYS[1]
  local now = tonumber(ARGV[1])
  local rate = tonumber(ARGV[2])
  local capacity = tonumber(ARGV[3])

  local data = redis.call('HMGET', key, 'tokens', 'ts')
  local tokens = tonumber(data[1]) or capacity
  local ts = tonumber(data[2]) or now

  local elapsed = now - ts
  tokens = math.min(capacity, tokens + elapsed * rate)

  if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HSET', key, 'tokens', tokens, 'ts', now)
    redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)
    return 1
  else
    redis.call('HSET', key, 'tokens', tokens, 'ts', now)
    return 0
  end
" 1 bucket:192.168.1.1 1700000060.123 10 100
```

Token bucket допускает короткие всплески (если накопились токены), но ограничивает среднюю скорость. Это полезно для API, где допустим burst, но нужен контроль средней нагрузки.

## Выбор подхода

| Подход | Точность | Память | Сложность |
|--------|----------|--------|-----------|
| Fixed window | всплеск на границе | минимум (1 ключ) | минимальная |
| Sliding window counter | приближённая | минимум (2 ключа) | низкая |
| Sliding window log | точная | O(запросов в окне) | средняя |
| Token bucket | burst + средняя | минимум (1 хеш) | средняя |

## См. также

- [Rate limiter на STRING в Rails](../../../rails/redis/practice/string-rate-limiter.md) — INCR + TTL из Puma-процессов

## Sources

- Redis Documentation: Rate limiting pattern. <https://redis.io/glossary/rate-limiting/>
- Cloudflare blog, «How we built rate limiting capable of scaling to millions of domains», 2017

---

← [Кеширование](caching.md) | [Распределённые блокировки](distributed-locks.md) →
