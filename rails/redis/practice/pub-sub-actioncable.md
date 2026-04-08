# ActionCable: координация WebSocket'ов между процессами

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [Pub/Sub](../../../databases/redis/data-structures/pub-sub.md).

Rails-приложение на Puma запускает несколько процессов (воркеров). Каждый процесс держит свой набор WebSocket-соединений. Процессы изолированы — у них нет общей памяти. Когда Sidekiq-джоб завершает обработку заказа и хочет отправить уведомление пользователю через WebSocket, он не знает, к какому Puma-процессу подключён этот пользователь, и не может напрямую достучаться до чужого сокета.

Это тоже задача выбора между [point-to-point и Pub/Sub](../../../system-design/message-queues.md#point-to-point-и-pubsub): сообщение должно попасть во все Puma-процессы, а уже каждый процесс локально решает, есть ли у него нужный WebSocket.

Отправить сообщение напрямую в конкретный процесс нельзя: у Sidekiq нет информации о том, какой Puma-воркер обслуживает нужный WebSocket, а между процессами нет shared memory. Вариант с общей базой (PostgreSQL LISTEN/NOTIFY) добавляет лишний hop и не предназначен для высокочастотных уведомлений.

ActionCable решает проблему через Redis Pub/Sub. Каждый Puma-процесс при старте создаёт отдельный поток, который подписывается на Redis-канал:

```ruby
# Под капотом ActionCable делает примерно следующее:
subscriber = Redis.new(url: ENV['REDIS_URL'])
subscriber.subscribe("action_cable/some_channel") do |on|
  on.message do |channel, message|
    # ActionCable определяет, какие WebSocket'ы в этом процессе
    # подписаны на channel, и рассылает им message
  end
end
```

ActionCable использует `subscribe` на конкретные каналы (с префиксом `action_cable/`), подписывая и отписывая каналы динамически по мере подключения клиентов. Вызов `subscribe` блокирует поток — он только слушает. Поэтому ActionCable выделяет для подписки отдельный поток, не занимая потоки Puma, которые обрабатывают HTTP-запросы и WebSocket I/O.

Когда код публикует сообщение в канал ActionCable (например, `ActionCable.server.broadcast("chat_42", data)`), происходит `PUBLISH` в Redis. Все Puma-процессы получают это сообщение через свои потоки подписки. Каждый процесс проверяет, есть ли у него WebSocket-соединения, подписанные на этот канал, и отправляет данные только нужным клиентам.

Это publish/subscribe, а не очередь задач: здесь не нужен `acknowledgment`, повторное чтение истории или гарантия «получил ровно один consumer». Нужна быстрая рассылка всем живым процессам.

Итого на каждый Puma-процесс: 5 потоков Puma (HTTP + WebSocket I/O) + 1 поток Redis-подписки. Этот дополнительный поток держит одно выделенное TCP-соединение к Redis, которое не входит в [connection_pool](../clients-and-connections.md#connection_pool) приложения.

Конфигурация ActionCable:

```yaml
# config/cable.yml
production:
  adapter: redis
  url: <%= ENV.fetch('REDIS_URL') %>
  channel_prefix: myapp_production
```

`channel_prefix` добавляет префикс ко всем каналам, чтобы несколько приложений могли разделять один Redis без коллизий имён. Подробнее о механике подписок: [Pub/Sub](../../../databases/redis/data-structures/pub-sub.md).
