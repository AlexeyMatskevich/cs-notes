# Защита от cache stampede

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [STRING](../../../databases/redis/data-structures/00-string.md), [Lua-скрипты](../../../databases/redis/atomicity/02-lua-scripting.md), [теория cache stampede](../../../system-design/07-caching.md#cache-stampede).

Популярный кеш с TTL 5 минут хранит результат тяжёлого SQL-запроса. В момент, когда TTL истекает, 1000 параллельных запросов обнаруживают пустой кеш и одновременно отправляют один и тот же запрос в PostgreSQL. База получает лавину одинаковых тяжёлых запросов и деградирует — p99 latency (время, в которое укладываются 99% запросов) подскакивает, вплоть до таймаутов у пользователей.

Это cache stampede (thundering herd). Два подхода к защите: блокировка на перестроение и упреждающее обновление. Подробнее о теории: [кеширование](../../../databases/redis/patterns/00-caching.md).

## Блокировка на перестроение

Первый запрос, обнаруживший пустой кеш, захватывает блокировку через `SET NX EX` и перестраивает кеш. Остальные запросы видят блокировку, ждут и делают retry:

```ruby
def get_cached_data(key, ttl: 300, max_retries: 50)
  REDIS.with do |r|
    max_retries.times do
      cached = r.get(key)
      return JSON.parse(cached) if cached

      lock_key = "lock:#{key}"
      acquired = r.set(lock_key, "1", nx: true, ex: 30)

      if acquired
        data = expensive_database_query()
        r.set(key, data.to_json, ex: ttl)
        r.del(lock_key)
        return data
      end

      sleep(0.1)
    end

    # Все retry исчерпаны — выполнить запрос напрямую
    expensive_database_query()
  end
end
```

Один процесс выполняет запрос к PostgreSQL, остальные ждут 100ms и перечитывают кеш. Блокировка с TTL 30 секунд — страховка на случай, если процесс-перестроитель упадёт. Цикл с ограниченным числом retry вместо рекурсии: рекурсия при 1000 одновременных запросах с глубоким retry рискует переполнить стек.

## Упреждающее обновление (early expiration)

Блокировка спасает от лавины, но ценой задержки: пока один запрос перестраивает кеш, остальные ждут. Если кеш можно обновить *до* истечения TTL, задержки не будет вовсе.

Если TTL = 300 секунд и early_ttl = 60 секунд, то при оставшемся TTL меньше 60 секунд запрос возвращает текущее (ещё валидное) значение и ставит фоновую задачу на обновление:

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

В зоне early expiration каждый запрос вызывает `perform_async` — при 1000 запросах в секунду Sidekiq получит 1000 одинаковых джобов. На практике `RefreshCacheJob` при запуске проверяет TTL: если кеш уже обновлён (TTL > early_ttl), джоб завершается без работы. Альтернатива — захватывать блокировку перед `perform_async`, чтобы поставить только один джоб.

Кеш обновляется до истечения TTL — одновременного обращения к PostgreSQL не происходит. Подход работает для данных с предсказуемым TTL и регулярным трафиком. Для редких, но тяжёлых запросов лучше подходит блокировка.

| Подход | Когда использовать |
|--------|-------------------|
| Блокировка | Редкие, тяжёлые запросы |
| Early expiration | Популярные данные с регулярным трафиком |
| Оба вместе | Критичные высоконагруженные системы |
