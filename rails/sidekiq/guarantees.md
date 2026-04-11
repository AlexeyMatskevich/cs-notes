---
tags:
  - domain/rails
  - theme/reliability
  - type/concept
aliases:
  - SuperFetch
  - BasicFetch
  - idempotency
order: 2
---

# Гарантии доставки и идемпотентность

**Предпосылки:** [архитектура Sidekiq](architecture.md), [жизненный цикл задачи](job-lifecycle.md), [гарантии доставки](../../system-design/delivery-guarantees.md), [[system-design/reliability-patterns#idempotency-безопасность-повторных-запросов|reliability patterns § idempotency]].

<- [Жизненный цикл задачи](job-lifecycle.md) | [Retry и обработка ошибок](retry-and-errors.md) ->

Sidekiq-процесс обрабатывает десять задач одновременно. OOM-killer убивает процесс. `BRPOP` извлёк все десять задач из Redis — они уже не в очереди. Процесс мёртв — они не в работе. Десять задач потеряны.

Это не единственное место, где задача может пропасть. В Sidekiq три точки потери — и на каждой по умолчанию задача не защищена.

## Три точки потери

### BasicFetch: Redis → Processor

Самая наглядная точка. `BRPOP` — это [простая очередь](../../databases/redis/patterns/queues.md): элемент удаляется из Redis в момент чтения. Между «забрал» и «обработал» нет страховки.

Сценарий: Processor выполнил `BRPOP`, получил [задачу](job-lifecycle.md), начал `perform`. Процесс убит `SIGKILL` (OOM, `kill -9`). [Задача](job-lifecycle.md) уже не в Redis и не в работающем процессе — потеряна.

При graceful shutdown (`SIGTERM`) Sidekiq возвращает in-flight задачи обратно в Redis (`bulk_requeue`). Но это работает только если процесс получил сигнал, имеет время на shutdown (timeout по умолчанию 25 секунд), и Redis доступен.

> [!info]- Pro: SuperFetch — private queue + orphan recovery
> `SuperFetch` (включается через `config.super_fetch!` в инициализаторе) заменяет basic fetch на схему «рабочая очередь → приватная очередь процесса → явное подтверждение». Sidekiq атомарно перемещает задачу из общей очереди в приватную очередь процесса (`queue:<name>:<hostname>:<pid>`), так что во время выполнения она остаётся в Redis. После успешного `perform` задача удаляется явным подтверждением (`LREM`).
>
> Если процесс убит — задача остаётся в приватной очереди. При старте Pro-процесса и в периодических проверках Sidekiq ищет приватные очереди мёртвых процессов (определяются по отсутствию heartbeat) и возвращает задачи в основную очередь.
>
> Цена надёжности: `SuperFetch` не может ждать работу так же дёшево, как блокирующий `BRPOP`, поэтому при большом числе очередей и процессов растёт polling-нагрузка на Redis. Восстановление orphan jobs тоже не мгновенное: обычно это минуты, а не миллисекунды.

### Push: client → Redis

Client выполняет `LPUSH` для отправки задачи в Redis. Если Redis недоступен в этот момент — `perform_async` выбросит исключение, и постановка не состоится. Задача «потеряна» только в том смысле, что она так и не попала в очередь.

> [!info]- Pro: reliable push
> `Sidekiq::Client.reliable_push!` — при сбое Redis задача сохраняется во внутреннюю in-memory очередь клиентского процесса и будет отправлена позже, когда следующее enqueue обнаружит восстановленное соединение.
>
> Ограничения: очередь локальна для процесса и живёт только в памяти, так что при рестарте клиента несохранённые задачи теряются. По умолчанию буфер хранит последние 1000 push и дренируется только при следующей успешной постановке задачи. Не совместим с Batches.

### Scheduling: sorted set → queue

[[rails/sidekiq/architecture#устройство-серверного-процесса|Poller]] перемещает «созревшие» [задачи](job-lifecycle.md) из sorted sets (`schedule`, `retry`) в рабочие очереди. Для этого нужны три шага: прочитать задачу (`ZRANGEBYSCORE`), удалить из sorted set (`ZREM`), добавить в рабочую очередь (`LPUSH`). По умолчанию эти шаги не атомарны. Crash между `ZREM` и `LPUSH` — задача удалена из sorted set, но не попала в очередь — потеря. Crash между `LPUSH` и `ZREM` — задача в очереди, но не удалена из sorted set — дубликат при следующей проверке.

> [!info]- Pro: reliable scheduler
> `config.reliable_scheduler!` — атомарное продвижение через Lua-скрипт. Одна неделимая операция: выбрать задачу из sorted set, удалить её оттуда, добавить в рабочую очередь.
>
> Ограничения: отложенная задача продвигается целиком внутри Redis, поэтому client middleware на этом шаге не вызывается. Lua-скрипты в Redis также выполняются на одном узле, что создаёт проблемы на Redis Cluster (ключи sorted set и рабочей очереди могут быть на разных узлах).

## Контракт: какая гарантия?

По умолчанию (OSS Sidekiq) каждая из трёх точек может потерять задачу — это [[system-design/delivery-guarantees#at-most-once-не-более-одного-раза|at-most-once]]: задача выполнится не более одного раза (возможно, ноль).

Pro-механизмы (`super_fetch!`, `reliable_push!`, `reliable_scheduler!`) значительно сужают окна потерь, приближая систему к [[system-design/delivery-guarantees#at-least-once-не-менее-одного-раза|at-least-once]]. Но у каждого механизма остаются оговорки (in-memory буфер теряется при рестарте, reliable scheduler несовместим с Redis Cluster). Более точная формулировка: best-effort at-least-once — система делает всё возможное, чтобы задача была выполнена хотя бы раз, но не гарантирует это при любых сбоях.

Важно: покупка Pro без явного включения механизмов (`config.super_fetch!` и т.д.) не меняет гарантий. Каждый механизм требует opt-in.

## At-least-once → нужна идемпотентность

At-least-once означает: задача может выполниться повторно. Retry после ошибки, orphan recovery после crash, дубликат из-за scheduling — всё это приводит к повторному выполнению. Если задача делает `balance += 100`, повторное выполнение удвоит сумму.

[[system-design/delivery-guarantees#exactly-once--at-least-once--idempotency|Exactly-once на транспортном уровне невозможна]]. Решение: at-least-once + [[system-design/reliability-patterns#idempotency-безопасность-повторных-запросов|идемпотентность]] = exactly-once по результату.

Три паттерна для идемпотентных задач:

```ruby
# 1. Проверка состояния перед действием
def perform(order_id)
  order = Order.find(order_id)
  return if order.processed?
  order.process!
end

# 2. Unique constraint в базе
def perform(order_id)
  Payment.create!(order_id: order_id, idempotency_key: "charge-#{order_id}")
rescue ActiveRecord::RecordNotUnique
  # уже создано — ничего не делать
end

# 3. Idempotency key с внешним сервисом
def perform(order_id)
  Stripe::Charge.create(
    amount: 1000,
    idempotency_key: "order-#{order_id}"
  )
end
```

Идемпотентность защищает от повторных выполнений. Но есть проблема до выполнения — задача может оказаться в очереди, хотя породившая её операция не состоялась.

## Ловушка: perform_async внутри транзакции

`ActiveRecord::Base.transaction` оборачивает SQL-операции в транзакцию базы данных: если внутри возникает ошибка или `raise ActiveRecord::Rollback`, все изменения в базе откатываются.

```ruby
ActiveRecord::Base.transaction do
  order = Order.create!(...)
  SendConfirmationJob.perform_async(order.id)  # LPUSH в Redis — уже выполнен!
  raise ActiveRecord::Rollback  # order откатится, но job уже в Redis
end
```

`perform_async` выполняет `LPUSH` немедленно — Redis не участвует в транзакции базы данных. Если транзакция откатится, [задача](job-lifecycle.md) в Redis обработает несуществующий order.

Два решения:

```ruby
# 1. after_commit callback
class Order < ApplicationRecord
  after_commit :enqueue_confirmation, on: :create

  private

  def enqueue_confirmation
    SendConfirmationJob.perform_async(id)
  end
end

# 2. Transactional Push (Sidekiq 7.0+)
Sidekiq.transactional_push!
# Теперь perform_async внутри транзакции буферизует задачу
# и отправит в Redis только после commit
```

Transactional Push интегрируется с ActiveRecord: если `perform_async` вызван внутри транзакции, задача буферизуется и отправляется в Redis только после успешного `COMMIT`. При rollback — задача отбрасывается. Вне транзакции `perform_async` работает как обычно — немедленный `LPUSH`.

Две важные оговорки из текущей документации: для Rails < 7.2 нужен gem `after_commit_everywhere`, а `push_bulk`/`perform_bulk` не буферизуются этой функцией.

---

Потери, дубликаты, идемпотентность — всё это про крайние случаи. В штатной работе задачи чаще падают по обычной причине: email-сервис вернул 500, база данных не ответила за timeout, API ограничил частоту. Для таких случаев в Sidekiq есть retry.

---

<- [Жизненный цикл задачи](job-lifecycle.md) | [Retry и обработка ошибок](retry-and-errors.md) ->

## Sources

- [Sidekiq Wiki — Reliability](https://github.com/sidekiq/sidekiq/wiki/Reliability)
- [Sidekiq Wiki — Pro Reliability Client](https://github.com/sidekiq/sidekiq/wiki/Pro-Reliability-Client)
- [Sidekiq Wiki — Advanced Options](https://github.com/sidekiq/sidekiq/wiki/Advanced-Options)
