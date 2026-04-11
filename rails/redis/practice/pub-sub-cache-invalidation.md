---
tags:
  - domain/rails
  - theme/caching
  - type/pattern
aliases:
  - cache invalidation
  - Pub/Sub
order: 3
---

# Инвалидация локального кеша между процессами

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [Pub/Sub](../../../databases/redis/data-structures/pub-sub.md), [[system-design/caching#когерентность-локальный-vs-внешний-кэш|когерентность кэша]].

Rails-приложение кеширует настройки (feature flags, конфиг тарифов) в памяти процесса для скорости. Когда администратор меняет настройку, все Puma-воркеры и Sidekiq-процессы на всех серверах должны сбросить свой локальный кеш за секунды.

Это типичная задача [[system-design/caching#когерентность-локальный-vs-внешний-кэш|когерентности локального vs внешнего кэша]]: данные уже обновились в основном хранилище, теперь нужно быстро донести факт изменения до всех локальных копий.

Альтернативы не подходят: структура с персистентным хранением сообщений избыточна, когда при перезапуске процесс загрузит свежие данные. Очередь с `BRPOP` доставляет сообщение только одному получателю, а нужно всем. [Pub/Sub](../../../databases/redis/data-structures/pub-sub.md) рассылает сообщение каждому подписчику одновременно:

```ruby
# Публикация: контроллер администратора
class Admin::SettingsController < ApplicationController
  def update
    Setting.update(params[:key], params[:value])

    REDIS.with do |r|
      r.publish("cache:invalidate", { key: params[:key], at: Time.now.to_i }.to_json)
    end

    head :ok
  end
end

# Подписчик: запускается в отдельном потоке при старте приложения
class CacheInvalidationSubscriber
  def self.start
    Thread.new do
      # Отдельное соединение — подписка блокирует клиента
      subscriber = Redis.new(url: ENV["REDIS_URL"])
      subscriber.subscribe("cache:invalidate") do |on|
        on.message do |_channel, message|
          data = JSON.parse(message)
          Rails.cache.delete(data["key"])
          Rails.logger.info("Cache invalidated: #{data['key']}")
        end
      end
    end
  end
end

# В config/initializers/cache_subscriber.rb
CacheInvalidationSubscriber.start unless Rails.env.test?
```

Подписка блокирует соединение — подписавшийся клиент не может выполнять другие команды. Поэтому подписчик создаётся на отдельном соединении, не из `connection_pool`. `PSUBSCRIBE` подписывается по маске — один подписчик может ловить все каналы `cache:*`:

```ruby
subscriber.psubscribe("cache:*") do |on|
  on.pmessage do |_pattern, channel, message|
    # channel = "cache:invalidate", "cache:warm", etc.
  end
end
```

Если Puma запускается с `preload_app!`, поток-подписчик нужно стартовать после `fork`, например в `on_worker_boot`. Иначе подписчик запустится в master-процессе и не будет обслуживать рабочие Puma-воркеры.

Если подписчика нет в момент публикации — сообщение пропадает. Для сценария кеш-инвалидации это нормально: процесс, который не был запущен, не имеет устаревшего кеша.

По модели обмена это именно [[system-design/message-queues#point-to-point-и-pubsub|Pub/Sub]], а не очередь: одно событие должно дойти до всех живых процессов сразу, без `acknowledgment` и без хранения истории.
