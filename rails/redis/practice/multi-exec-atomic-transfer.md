# Атомарный перевод средств

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [MULTI/EXEC](../../../databases/redis/atomicity/01-multi-exec.md).

## Гонка без транзакции

Каждая отдельная команда Redis атомарна, но последовательность `GET` → решение → `SET` -- нет. Между чтением и записью сервер успевает обработать команду от другого клиента, и тот перезаписывает значение на основе уже устаревших данных:

```ruby
REDIS.with do |r|
  balance = r.get("balance:user:42").to_i  # → 100
  # ... другой Puma-воркер тоже читает 100
  r.set("balance:user:42", balance - 20)   # → 80
  # другой воркер пишет 100 - 30 = 70
  # Итог: 70 вместо 50. Списание 20 потеряно.
end
```

## WATCH: оптимистичная блокировка

`WATCH` позволяет выполнить паттерн «прочитать — решить — записать» безопасно. Redis наблюдает за ключами; если между `WATCH` и `EXEC` кто-то изменил наблюдаемый ключ, транзакция отменяется:

```ruby
def transfer(from_id, to_id, amount)
  key_from = "balance:user:#{from_id}"
  key_to   = "balance:user:#{to_id}"

  REDIS.with do |r|
    # WATCH помечает ключи для наблюдения:
    # если кто-то изменит их до EXEC — транзакция отменится
    r.watch(key_from, key_to) do |conn|
      balance = conn.get(key_from).to_i

      if balance < amount
        conn.unwatch  # снимаем наблюдение, транзакции не будет
        return :insufficient_funds
      end

      # MULTI открывает транзакцию — команды буферизуются, не выполняются
      result = conn.multi do |tx|
        tx.decrby(key_from, amount)
        tx.incrby(key_to, amount)
      end
      # EXEC выполняет буфер атомарно; nil — конфликт (WATCH сработал)

      result ? :ok : :conflict
    end
  end
end
```

При конфликте `result` будет `nil`. В продакшен-коде оборачивают retry-циклом:

```ruby
MAX_RETRIES = 5

MAX_RETRIES.times do
  case transfer(42, 99, 20)
  when :ok                 then break
  when :conflict           then next
  when :insufficient_funds then raise "Not enough funds"
  end
end
```

При низкой конкуренции конфликты редки. При высокой конкуренции за одни и те же ключи количество retry растёт — для условной логики без retry лучше подходит [Lua-скрипт](../../../databases/redis/atomicity/02-lua-scripting.md).

## Pipelining внутри MULTI

Библиотека `redis-rb` при использовании блочной формы `r.multi { |tx| ... }` автоматически буферизует все команды и отправляет MULTI + команды + EXEC одним пакетом. Транзакция из N команд обходится в один round-trip — [pipelining](../../../databases/redis/architecture/02-pipelining.md) получается бесплатно.

Подробнее: [MULTI/EXEC](../../../databases/redis/atomicity/01-multi-exec.md).
