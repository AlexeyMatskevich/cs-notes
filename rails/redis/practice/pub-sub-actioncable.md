# ActionCable: координация WebSocket'ов между процессами

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [Pub/Sub](../../../databases/redis/data-structures/08-pub-sub.md).

Rails-приложение на Puma запускает несколько процессов (worker'ов). Каждый процесс держит свой набор WebSocket-соединений. Процессы изолированы — у них нет общей памяти. Когда Sidekiq-джоб завершает обработку заказа и хочет отправить уведомление пользователю через WebSocket, он не знает, к какому Puma-процессу подключён этот пользователь, и не может напрямую достучаться до чужого сокета.

Отправить сообщение напрямую в конкретный процесс нельзя: у Sidekiq нет информации о том, какой Puma-worker обслуживает нужный WebSocket, а между процессами нет shared memory. Вариант с общей базой (PostgreSQL LISTEN/NOTIFY) добавляет лишний hop и не предназначен для высокочастотных уведомлений.

ActionCable решает проблему через Redis Pub/Sub. Каждый Puma-процесс при старте создаёт отдельный поток, который подписывается на Redis-канал:

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

Подробнее: [Pub/Sub](../../../databases/redis/data-structures/08-pub-sub.md).
