# Инвалидация локального кеша между процессами

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [Pub/Sub](../../../databases/redis/data-structures/08-pub-sub.md), [когерентность кэша](../../../system-design/07-caching.md#когерентность-локальный-vs-внешний-кэш).

Rails-приложение кеширует настройки (feature flags, конфиг тарифов) в памяти процесса для скорости. Когда администратор меняет настройку, все Puma-воркеры и Sidekiq-процессы на всех серверах должны сбросить свой локальный кеш за секунды.

Stream не подходит: здесь не нужна гарантия доставки и persistence — если процесс был перезапущен, он загрузит свежие данные при старте. Consumer groups — избыточная сложность для fire-and-forget сигнала. LIST с `BRPOP` доставляет сообщение только одному получателю, а нужно всем. Pub/Sub рассылает сообщение каждому подписчику одновременно:

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

Если подписчика нет в момент публикации — сообщение пропадает. Для сценария кеш-инвалидации это нормально: процесс, который не был запущен, не имеет устаревшего кеша.

Подробнее: [Pub/Sub](../../../databases/redis/data-structures/08-pub-sub.md).
