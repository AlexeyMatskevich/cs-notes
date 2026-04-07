# Sidekiq: архитектура

**Предпосылки:** [Redis Lists](../../databases/redis/data-structures/02-list.md), [очереди в Redis](../../databases/redis/patterns/03-queues.md), [message queues](../../system-design/09-message-queues.md), [фоновая очередь на LIST](../redis/practice/list-background-queue.md), базовое знание Rails (ActiveRecord, RSpec).

[Следующая тема: жизненный цикл job](01-job-lifecycle.md) ->

Простая очередь из предыдущей практики работает: `LPUSH` добавляет задачу, `BRPOP` забирает, воркер обрабатывает. Но цикл обслуживает один тип задачи с одним поведением. Добавь resize картинок — нужен второй цикл или роутинг по типу задачи. Добавь retry при ошибках — воркер ловит исключения, считает задержку, пишет в sorted set. Добавь graceful shutdown — обработчики сигналов. Каждое дополнение — паттерн, который уже знаком из предпосылок, но собирать их руками — строить собственный фреймворк фоновых задач. Sidekiq — готовый фреймворк, который объединяет эти паттерны в одну систему.

## Терминология

**Job** (задача) — единица работы в Sidekiq. Это Ruby-класс с методом `perform` и одновременно JSON-хеш в Redis. Класс определяет *что делать*, JSON в Redis — *конкретный вызов* с аргументами.

```ruby
class SendEmailJob
  include Sidekiq::Job

  def perform(user_id)
    user = User.find(user_id)
    UserMailer.welcome(user).deliver_now
  end
end
```

Термин **worker** встречается в старом коде и документации — это устаревший синоним job. В точной терминологии Sidekiq: class = job class, выполняющий поток = processor, процесс ОС = process.

**Queue** (очередь) — Redis LIST с ключом `queue:<имя>`. У каждого job класса есть очередь по умолчанию (`default`), которую можно переопределить через `sidekiq_options queue: 'critical'`.

## Три роли

Sidekiq реализует [point-to-point](../../system-design/09-message-queues.md#point-to-point-и-pubsub) модель: несколько consumers конкурируют за задачи из общей очереди. Система состоит из трёх ролей:

**Client** — Rails-приложение, которое ставит задачи. Вызов `SendEmailJob.perform_async(user_id)` сериализует аргументы в JSON, прогоняет через client middleware (цепочку обработчиков, которые могут дополнить или отклонить задачу перед отправкой) и выполняет `LPUSH` в Redis.

**Broker** — Redis. Хранит очереди, расписание, retry, метаданные процессов. Redis выбран потому, что Sidekiq использует знакомые структуры: LIST для очередей, Sorted Set для отложенных задач и retry, Set и Hash для метаданных. Это те же паттерны из [очередей в Redis](../../databases/redis/patterns/03-queues.md), собранные вместе.

**Server** — процесс Sidekiq, который забирает задачи из Redis и выполняет их в потоках. Один сервер обрабатывает задачи параллельно: пока один поток ждёт ответа от SMTP-сервера, другой обрабатывает картинку. Это возможно благодаря тому, что потоки Ruby освобождают GVL при блокирующем I/O ([подробнее — Ruby concurrency](../../ruby/ruby-concurrency.md#gvl-почему-потоки-не-ускоряют-cpu-код)).

В терминах [temporal decoupling](../../system-design/09-message-queues.md#temporal-decoupling-развязка-во-времени): client и server работают независимо. Rails-приложение кладёт задачу и продолжает обслуживать HTTP-запрос. Sidekiq-процесс обрабатывает задачу, когда готов — через миллисекунды, минуты или часы.

## Данные в Redis

Каждая роль работает с конкретными ключами в Redis:

| Структура | Ключ | Назначение |
|-----------|------|-----------|
| List | `queue:<name>` | Рабочие очереди. Client делает `LPUSH`, server — `BRPOP` |
| Sorted Set | `schedule` | Отложенные задачи. Score = Unix timestamp выполнения |
| Sorted Set | `retry` | Задачи на повтор. Score = время следующей попытки |
| Sorted Set | `dead` | Задачи, исчерпавшие все попытки (max 10 000, хранятся 6 месяцев) |
| Set | `queues` | Индекс имён всех очередей |
| Set | `processes` | ID активных Sidekiq-процессов |
| Hash | `<identity>` | Метаданные процесса: hostname, pid, concurrency, busy, beat |

`schedule` и `retry` — это [delayed queue на Sorted Set](../../databases/redis/patterns/03-queues.md#отложенные-задачи-delayed-queue): score задаёт момент, когда задача должна переместиться в рабочую очередь. `dead` — это [Dead Letter Queue](../../system-design/09-message-queues.md#dead-letter-queue): задачи, которые не удалось обработать после всех попыток.

Redis для Sidekiq настраивается с политикой `noeviction` (при исчерпании памяти Redis возвращает ошибку на запись вместо удаления ключей). Если бы политика была `allkeys-lru` (удаление наименее используемых ключей для освобождения памяти), Redis мог бы удалить ключ очереди с тысячами задач, чтобы освободить место для нового.

## Устройство серверного процесса

Внутри серверного процесса — несколько компонентов, каждый со своей задачей:

```
Sidekiq Process
├── Launcher           -- управляет жизненным циклом процесса
│   ├── Manager        -- управляет набором Processor-потоков
│   │   ├── Processor  -- поток: BRPOP → deserialize → perform
│   │   ├── Processor
│   │   └── ...        -- количество = настройка concurrency (default 5)
│   ├── Poller         -- поток: проверяет schedule и retry sorted sets
│   └── Heartbeat      -- поток: обновляет метаданные процесса в Redis (~10 сек)
```

**Processor** — рабочий поток. Выполняет цикл: забрать задачу из Redis (`BRPOP`), десериализовать JSON, выполнить `perform`. Количество Processor-ов определяется настройкой `concurrency` (по умолчанию 5 начиная с Sidekiq 7).

**Poller** — фоновый поток, который периодически проверяет sorted sets `schedule` и `retry`. Если score задачи ≤ текущему времени, Poller перемещает её в рабочую очередь (`LPUSH`). Это тот же паттерн [отложенной очереди](../../databases/redis/patterns/03-queues.md#отложенные-задачи-delayed-queue), но реализованный как отдельный поток внутри процесса.

**Heartbeat** — поток, который каждые ~10 секунд обновляет метаданные процесса в Redis (hostname, pid, количество занятых потоков). По этим данным Web UI показывает состояние системы, а Pro-версия определяет мёртвые процессы для восстановления задач.

## Три способа поставить задачу

```ruby
# Выполнить как можно скорее: LPUSH в queue:<name>
SendEmailJob.perform_async(user_id)

# Выполнить через 5 минут: ZADD в schedule (score = Time.now + 300)
SendEmailJob.perform_in(5.minutes, user_id)

# Выполнить в конкретное время: ZADD в schedule (score = timestamp)
SendEmailJob.perform_at(2.hours.from_now, user_id)
```

`perform_async` кладёт задачу напрямую в рабочую очередь — Processor заберёт её при следующем `BRPOP`. `perform_in` и `perform_at` кладут задачу в sorted set `schedule` с нужным timestamp. Когда время наступит, Poller переместит задачу в рабочую очередь.

---

Архитектура — карта системы: три роли, шесть структур данных в Redis, несколько компонентов внутри процесса. Но как конкретно задача проходит путь от `perform_async` до завершения `perform`?

---

[Следующая тема: жизненный цикл job](01-job-lifecycle.md) ->

## Sources

- Mike Perham, [How does Sidekiq work?](https://www.mikeperham.com/how-sidekiq-works/)
- [Sidekiq Wiki](https://github.com/sidekiq/sidekiq/wiki)
- [Sidekiq Redis Data Model](https://hype08.github.io/gradual-notes/thoughts/Sidekiq-Redis-Data-Model)
