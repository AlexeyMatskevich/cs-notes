# Ежедневная активность и retention миллионов пользователей

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [Bitmap и Bitfield](../../../databases/redis/data-structures/07-bitmap-and-bitfield.md).

Продукт отслеживает DAU/WAU/MAU и retention (какая доля пользователей вернулась через 7 дней). Пользователей — 10 миллионов. Нужно быстро отвечать на два типа вопросов: «сколько уникальных пользователей были активны за период?» и «был ли конкретный пользователь активен в конкретный день?».

HyperLogLog отвечает на первый вопрос, но не на второй. SET — 10 миллионов user_id × ~50 байт = 500 МБ на один день. Bitmap — 10 миллионов бит = 1.25 МБ на один день. При 365 днях: SET = 180 ГБ, Bitmap = 456 МБ.

Побитовые операции `BITOP AND/OR` вычисляют retention и WAU/MAU на сервере за O(n) байт — без передачи данных в Ruby:

```ruby
class ActivityTracker
  def initialize(redis_pool)
    @redis = redis_pool
  end

  def mark_active(user_id)
    key = "active:#{Date.today.iso8601}"
    @redis.with { |r| r.setbit(key, user_id, 1) }
  end

  def active?(user_id, date)
    key = "active:#{date.iso8601}"
    @redis.with { |r| r.getbit(key, user_id) == 1 }
  end

  def dau(date)
    @redis.with { |r| r.bitcount("active:#{date.iso8601}") }
  end

  def wau(start_date)
    keys = (0..6).map { |i| "active:#{(start_date + i).iso8601}" }
    result_key = "wau:#{start_date.iso8601}"

    @redis.with do |r|
      r.bitop("OR", result_key, *keys)
      count = r.bitcount(result_key)
      r.del(result_key)
      count
    end
  end

  # Retention: из тех, кто был активен в day_a, сколько вернулось в day_b?
  def retention(day_a, day_b)
    result_key = "retention:#{day_a}:#{day_b}"

    @redis.with do |r|
      r.bitop("AND", result_key, "active:#{day_a.iso8601}", "active:#{day_b.iso8601}")
      returned = r.bitcount(result_key)
      total = r.bitcount("active:#{day_a.iso8601}")
      r.del(result_key)

      total.zero? ? 0.0 : (returned.to_f / total * 100).round(2)
    end
  end
end
```

`BITOP AND` вычисляет пересечение двух дней за O(n) байт (1.25 МБ при 10 миллионах пользователей) без передачи данных клиенту. `BITOP OR` объединяет 7 дней для WAU. Bitmap эффективен при плотных числовых ID. Если ID разреженные (UUID), бо́льшая часть бит останется нулевой — для таких случаев лучше HyperLogLog (без ответа на «был ли конкретный?») или SET.

## BITFIELD: компактные числовые поля

`BITFIELD` хранит несколько целых чисел разной разрядности в одной строке — экономит ключи, когда для сущности нужно несколько небольших счётчиков:

```ruby
REDIS.with do |r|
  # Хранить level (8 бит, 0-255) и score (16 бит, 0-65535) в одной строке
  r.bitfield("player:#{user_id}", "SET", "u8", 0, level)
  r.bitfield("player:#{user_id}", "SET", "u16", 8, score)

  # Прочитать оба поля за один вызов
  level, score = r.bitfield("player:#{user_id}", "GET", "u8", 0, "GET", "u16", 8)

  # Атомарный инкремент с защитой от переполнения
  r.bitfield("player:#{user_id}", "OVERFLOW", "SAT", "INCRBY", "u16", 8, 100)
end
```

Подробнее: [Bitmap и Bitfield](../../../databases/redis/data-structures/07-bitmap-and-bitfield.md).
