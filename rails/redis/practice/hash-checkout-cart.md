# Состояние корзины в e-commerce checkout

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [HASH](../../../databases/redis/data-structures/01-hash.md).

В процессе оформления заказа корзина содержит несколько связанных полей: список товаров, адрес доставки, выбранный способ оплаты, промокод, этап checkout. Фронтенд обновляет поля по одному — пользователь выбрал доставку, затем ввёл промокод, затем подтвердил оплату.

Хранить каждое поле как отдельный STRING-ключ (`cart:42:items`, `cart:42:address`, `cart:42:promo`) — дорого по памяти (~70 байт overhead на ключ) и неудобно: чтение всей корзины требует нескольких `GET`. JSON-строка в одном STRING-ключе требует прочитать всё, десериализовать, изменить одно поле и записать обратно — это read-modify-write, а значит гонка между процессами без блокировки.

HASH позволяет обновлять отдельные поля атомарно (`HSET`), читать всё за один `HGETALL`, и платить overhead один раз за весь объект:

```ruby
class CheckoutCart
  def initialize(redis_pool, order_id)
    @redis_pool = redis_pool
    @key = "cart:#{order_id}"
  end

  def set_shipping(address, method)
    @redis_pool.with do |r|
      r.hset(@key, "shipping_address", address.to_json, "shipping_method", method)
    end
  end

  def apply_promo(code)
    @redis_pool.with do |r|
      r.hset(@key, "promo_code", code)
    end
  end

  def advance_step(step)
    @redis_pool.with do |r|
      r.hset(@key, "step", step)
    end
  end

  def snapshot
    @redis_pool.with do |r|
      r.hgetall(@key)
    end
  end

  def finalize!(ttl: 3600)
    @redis_pool.with do |r|
      r.expire(@key, ttl)
    end
  end
end
```

Два Puma-процесса могут одновременно вызвать `set_shipping` и `apply_promo` — каждый пишет в своё поле, конфликта нет. С JSON в STRING второй процесс перезаписал бы изменения первого. [`HINCRBY`](../../../databases/redis/data-structures/01-hash.md) работает для числовых полей (количество товаров) без read-modify-write.
