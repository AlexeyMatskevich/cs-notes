# Очереди

**Предпосылки:** [List](../data-structures/02-list.md), [Sorted Set](../data-structures/04-sorted-set.md), [Stream](../data-structures/05-stream.md), [атомарность одной команды](../atomicity/00-single-command.md).

Веб-приложения часто выносят тяжёлые или некритичные задачи (отправка email, обработка изображений, индексация) в фоновую обработку. Для этого нужна очередь: продюсер добавляет задачу, обработчик забирает и выполняет. Redis предоставляет несколько структур данных с блокирующими операциями и атомарными перемещениями, на которых строятся очереди — от простых до надёжных.

## Простая очередь на LIST

`LPUSH` добавляет задачу в начало списка, `BRPOP` атомарно забирает задачу с конца (FIFO). `BRPOP` блокирует соединение, если список пуст, и возвращает элемент, как только он появится. Клиент не тратит CPU на polling.

```redis-cli
-- продюсер:
LPUSH queue:emails '{"to":"user@example.com","subject":"Welcome"}'

-- обработчик (блокирующий):
BRPOP queue:emails 0
-- → ["queue:emails", '{"to":"user@example.com","subject":"Welcome"}']
-- 0 = ждать бесконечно
```

Несколько обработчиков могут вызвать `BRPOP` на одной очереди — Redis отдаст каждое сообщение ровно одному из них.

Проблема: после `BRPOP` элемент удалён из Redis. Если обработчик упал до завершения работы — сообщение потеряно.

## Reliable queue: LMOVE (RPOPLPUSH)

Вместо простого `BRPOP` используется двухсписковая схема. `LMOVE source destination RIGHT LEFT` атомарно забирает элемент из конца основной очереди и помещает в начало «очереди обработки» (processing list).

```redis-cli
-- обработчик:
LMOVE queue:emails queue:emails:processing RIGHT LEFT
-- → забрал из queue:emails, поместил в queue:emails:processing

-- после успешной обработки:
LREM queue:emails:processing 1 '<сообщение>'
-- удалить из processing-списка
```

Эта схема работает, если элементы в очереди уникальны. Если одинаковый payload может встречаться несколько раз, `LREM 1 '<сообщение>'` может удалить не тот элемент. На практике в очереди кладут уникальный ID задачи, а payload хранят отдельно (например, `HSET jobs <id> <json>`), либо сразу используют Streams.

Если обработчик упал — сообщение остаётся в processing-списке. Отдельный процесс (monitor) периодически проверяет `LRANGE queue:emails:processing 0 -1` и возвращает элементы, висящие дольше таймаута, в основную очередь. Чтобы определить время начала обработки, используют ZSET со score = timestamp или хранят timestamp внутри payload.

Блокирующий вариант — `BLMOVE source destination RIGHT LEFT timeout` (Redis 6.2+).

## Delayed queue на SORTED SET

Не все задачи нужно выполнять немедленно — напоминания, отложенные уведомления, retry с задержкой. Задачи, которые нужно выполнить не сейчас, а в определённое время, хранятся в ZSET с timestamp выполнения как score.

```redis-cli
-- добавить задачу с выполнением через 5 минут:
ZADD queue:delayed 1700000300 '{"task":"send_reminder","user":123}'

-- обработчик периодически проверяет:
ZRANGEBYSCORE queue:delayed 0 <текущий_timestamp> LIMIT 0 10
-- → задачи, время которых наступило

-- после получения задачи — удалить и обработать:
ZREM queue:delayed '<сообщение>'
```

Для атомарности «выбрать и удалить» оборачивают в Lua-скрипт:

```redis-cli
EVAL "
  local items = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
  if #items > 0 then
    redis.call('ZREM', KEYS[1], items[1])
    return items[1]
  end
  return nil
" 1 queue:delayed 1700000060
```

Без Lua два обработчика могут одновременно прочитать одну задачу через `ZRANGEBYSCORE`, и оба попытаются её обработать.

## Очереди с приоритетом

Иногда задачи имеют разный приоритет — критичные должны обрабатываться раньше обычных. `BRPOP` принимает несколько ключей и обрабатывает их в порядке перечисления. Первым проверяется первый ключ:

```redis-cli
BRPOP queue:high queue:medium queue:low 0
-- задачи из queue:high обрабатываются первыми
```

Альтернатива — ZSET с приоритетом как score. Задачи с меньшим score (выше приоритет) обрабатываются первыми.

## Streams как очередь

LIST и ZSET требуют ручной реализации подтверждения и обработки сбоев. [Streams](../data-structures/05-stream.md) — наиболее полнофункциональное решение для очередей в Redis. Consumer groups обеспечивают распределение сообщений между обработчиками с подтверждением (`XACK`). Необработанные сообщения (pending) автоматически отслеживаются. `XCLAIM` и `XAUTOCLAIM` позволяют перенаправить зависшие сообщения. Streams хранят историю и позволяют повторное чтение.

## Выбор реализации

| Требование | Реализация |
|------------|-----------|
| Простая FIFO-очередь, потеря допустима | LIST + `BRPOP` |
| FIFO с гарантией обработки | LIST + `BLMOVE` (reliable queue) |
| Отложенные задачи | ZSET + Lua |
| Приоритеты | `BRPOP` нескольких LIST или ZSET |
| Consumer groups, подтверждение, повторное чтение | Stream |

Для критичных задач (платежи, заказы) Redis-очередь — не замена message broker (RabbitMQ, Kafka). Redis теряет данные при падении без персистентности, не даёт гарантий exactly-once delivery. Streams приближаются к гарантиям message broker, но в пределах RAM и одного кластера.

## См. также

- [Практика в Ruby/Rails: LIST](../../../rails/redis/02-data-structures-in-practice.md) — LPUSH/BRPOP, очереди и capped lists
- [Sidekiq](../../../rails/sidekiq.md) — фоновые задачи через Redis LIST + BRPOP

## Sources

- Redis Documentation: Patterns — Reliable queue. <https://redis.io/commands/rpoplpush/#pattern-reliable-queue>
- Redis Documentation: Streams. <https://redis.io/docs/data-types/streams/>
