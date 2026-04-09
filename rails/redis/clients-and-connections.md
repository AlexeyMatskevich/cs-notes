---
tags:
  - domain/rails
  - theme/caching
  - theme/performance
  - type/concept
aliases:
  - redis-rb
  - connection_pool
  - hiredis
order: 0
---

# Клиенты и соединения

**Предпосылки:** [Redis: архитектура](../../databases/redis/redis.md), [TCP](../../networking/transport/tcp.md) (соединение), [Puma](../../ruby/internal/concurrency.md#puma-reactor--thread-pool) (воркеры + потоки).

[Структуры данных на практике](data-structures-in-practice.md) ->

## Зачем нужен пул соединений

Puma запускает несколько воркер-процессов, в каждом — несколько потоков. При 3 воркерах по 5 потоков приложение обрабатывает до 15 запросов одновременно. Каждый из этих потоков может обращаться к [Redis](../../databases/redis/redis.md): читать кеш, проверять лимиты запросов, публиковать в Pub/Sub.

Один объект `Redis.new` — это одно [TCP](../../networking/transport/tcp.md)-соединение с сервером. Несколько потоков могут пользоваться им безопасно, но не параллельно: гем `redis` защищает доступ к соединению мьютексом, поэтому в каждый момент через него идёт только одна команда.

Если один поток отправил `GET` и ждёт ответ Redis, остальные потоки, которым нужен тот же клиент, ждут своей очереди. Поэтому один общий клиент в Puma становится узким местом: все обращения к Redis внутри процесса выстраиваются последовательно.

Пул убирает это узкое место. Вместо одного общего соединения у процесса есть несколько соединений, и разные потоки могут обращаться к Redis одновременно.

## connection_pool

Гем `connection_pool` создаёт заданное количество соединений и выдаёт каждому потоку своё на время блока.

```ruby
# config/initializers/redis.rb
require 'connection_pool'

REDIS = ConnectionPool.new(size: ENV.fetch('RAILS_MAX_THREADS', 5).to_i + 2, timeout: 3) do
  Redis.new(url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0'))
end
```

Размер пула — `RAILS_MAX_THREADS + небольшой запас`. Puma с 5 потоками — минимум `size: 5`. Запас в 1–2 соединения нужен, если Redis используется из фоновых потоков (таймеры, колбэки).

Использование — через `with`:

```ruby
REDIS.with do |conn|
  conn.get('user:123:name')
end
```

`with` берёт свободное соединение из пула, передаёт в блок и возвращает обратно после выполнения. Если все соединения заняты, поток ждёт до `timeout` секунд и поднимает исключение.

Держать соединение нужно только на время Redis-команд. Если внутри `with` сделать HTTP-запрос, `sleep`, тяжёлый SQL или долгую CPU-работу, соединение из пула будет простаивать занятым, а остальные потоки начнут ждать или получать `ConnectionPool::TimeoutError`.

Если Redis используется только как кэш Rails, отдельный `ConnectionPool.new` обычно не нужен: `:redis_cache_store` уже настраивает пул соединений по умолчанию.

## Когда нужен не пул, а выделенное соединение

Некоторые команды захватывают соединение надолго:

- `SUBSCRIBE` и `PSUBSCRIBE` переводят клиент в режим [Pub/Sub](../../databases/redis/data-structures/pub-sub.md);
- `BRPOP`, `BLPOP`, `XREAD BLOCK`, `XREADGROUP BLOCK` держат соединение в блокирующем ожидании;
- долгоживущий [Pub/Sub](../../databases/redis/data-structures/pub-sub.md)-подписчик или подписчик ActionCable работает часами, а не миллисекундами.

Такие соединения нельзя брать из обычного пула Puma для веб-запросов. Иначе один подписчик или один воркер с `BRPOP` навсегда «съест» слот пула. Для них создают отдельный клиент или отдельный специализированный пул. Это частный случай [bulkhead](../../system-design/reliability-patterns.md#bulkhead-изоляция-ресурсов): блокирующие и долгоживущие операции изолируют от коротких запросов, чтобы они не забрали общий ресурс целиком.

Поэтому ActionCable, [Sidekiq](../sidekiq/sidekiq.md) и собственные потоки-подписчики обычно управляют своими соединениями отдельно от `REDIS`, который обслуживает обычные запросы приложения.

## Ruby-клиенты для Redis

Стандартный клиент — гем `redis` (redis-rb). Он покрывает все команды Redis, стабилен и поддерживается. Для большинства Rails-проектов этого достаточно.

```ruby
# Gemfile
gem 'redis', '~> 5.0'
```

Гем `redis-client` — более низкоуровневый клиент. Он не маппит Redis-команды на Ruby-методы, а работает через `call("SET", ...)`. Его часто видно в инфраструктурном коде и библиотеках. Важное отличие: отдельный клиент `RedisClient.new_client` нельзя шарить между потоками, поэтому для многопоточного Rails-кода обычно создают `new_pool`.

Опциональная оптимизация для `redis` — гем `hiredis-client`. Это C-расширение, которое ускоряет разбор ответов Redis. Особенно заметно это на больших ответах (`LRANGE`, `SMEMBERS`, `ZRANGE`) и длинных пакетах команд, а не на маленьких `GET`/`SET`, где время чаще уходит на сеть.

```ruby
# Gemfile
gem 'redis', '~> 5.0'
gem 'hiredis-client'
```

Если приложение загружает гемы через `Bundler.require`, `redis` начнёт использовать `hiredis-client` автоматически. Если гемы подключаются вручную, может понадобиться явный `require "hiredis-client"`.

`REDIS_URL` следует формату `redis://host:port/db_number`. Номер базы (от 0 до 15 по умолчанию) — способ логически разделить ключи внутри одного инстанса. Разные номера баз изолируют пространства ключей, но разделяют одну и ту же память и CPU.

## Несколько инстансов Redis

Один инстанс Redis обслуживает и кеш, и сессии, и [Sidekiq](../sidekiq/sidekiq.md) — но у этих задач разные требования к сохранности данных и поведению при нехватке памяти. Если Redis для кеша вытеснит ключ Sidekiq-очереди, задача потеряется. Разделение на инстансы — это ещё один [bulkhead](../../system-design/reliability-patterns.md#bulkhead-изоляция-ресурсов): кеш, сессии и очереди получают разные лимиты памяти, разные политики eviction и не делят одну общую область отказа.

Кеш страниц и фрагментов — данные, которые можно пересчитать. Персистентность не нужна: при рестарте кеш прогреется заново. Политика вытеснения `allkeys-lru` — Redis сам удаляет давно неиспользуемые ключи при нехватке памяти. Если Redis для кеша упадёт, приложение продолжит работать, просто медленнее (запросы пойдут в PostgreSQL).

Сессии — данные с TTL, потеря которых означает разлогин пользователей. [AOF](../../databases/redis/persistence/aof.md) с `appendfsync everysec` даёт потерю максимум секунды данных при падении. Политика `volatile-ttl` — при нехватке памяти Redis удаляет ключи с наименьшим оставшимся TTL (самые старые сессии).

[Sidekiq](../sidekiq/sidekiq.md) хранит в Redis [очереди](../../databases/redis/data-structures/list.md) задач и служебные ключи процесса. Поэтому Redis для Sidekiq нельзя настраивать как кеш с политиками вытеснения вроде `allkeys-lru`: при нехватке памяти Redis не должен удалять элементы очереди. Обычно для Sidekiq выделяют отдельный инстанс Redis с политикой `noeviction`.

Насколько агрессивная персистентность нужна этому инстансу, зависит от того, какую потерю задач приложение готово пережить при сбое.

Подключение Sidekiq к Redis настраивается отдельно от пула соединений приложения. `connection_pool` нужен Rails-коду, который берёт короткие соединения на время запроса. Sidekiq сам создаёт и управляет своими соединениями.

```ruby
# config/initializers/redis.rb
require 'connection_pool'

REDIS = ConnectionPool.new(size: ENV.fetch('RAILS_MAX_THREADS', 5).to_i + 2, timeout: 3) do
  Redis.new(url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0'))
end

REDIS_CACHE = ConnectionPool.new(size: ENV.fetch('RAILS_MAX_THREADS', 5).to_i + 2, timeout: 3) do
  Redis.new(url: ENV.fetch('REDIS_CACHE_URL', 'redis://localhost:6380/0'))
end

# config/initializers/sidekiq.rb
Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch('REDIS_JOBS_URL', 'redis://localhost:6381/0') }
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV.fetch('REDIS_JOBS_URL', 'redis://localhost:6381/0') }
end
```

Три переменные окружения — `REDIS_URL`, `REDIS_CACHE_URL`, `REDIS_JOBS_URL` — указывают на разные порты или разные серверы. Каждый инстанс настраивается независимо в `redis.conf`: свой `maxmemory`, своя политика вытеснения, свои параметры персистентности.

## Sources

- redis-rb README: thread safety, connection pooling, hiredis. <https://github.com/redis/redis-rb>
- redis-client README: `new_pool`, raw clients и thread safety. <https://github.com/redis-rb/redis-client>
- connection_pool README. <https://github.com/mperham/connection_pool>
- Rails Guides: `:redis_cache_store` connection pooling. <https://guides.rubyonrails.org/caching_with_rails.html>
- Sidekiq Wiki: Using Redis. <https://github.com/sidekiq/sidekiq/wiki/Using-Redis>

---

[Структуры данных на практике](data-structures-in-practice.md) ->
