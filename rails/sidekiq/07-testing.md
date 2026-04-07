# Тестирование и практики

**Предпосылки:** [Sidekiq: concurrency и масштабирование](06-concurrency-and-scaling.md), базовое знание RSpec и ActiveJob.

<- [Concurrency и масштабирование](06-concurrency-and-scaling.md)

RSpec-тест вызывает `SendEmailJob.perform_async(42)`. Задача уходит в Redis. Тест проходит — но что он проверил? Факт постановки, не результат. Чтобы проверить результат, нужен запущенный Sidekiq-процесс, Redis, ожидание выполнения. Для unit-теста это слишком медленно и хрупко.

## Три режима тестирования

Sidekiq предоставляет тестовую обвязку, которая подменяет поведение `perform_async`. В новых версиях Sidekiq её можно включать новым API:

```ruby
Sidekiq.testing!(:fake)
```

Во многих приложениях и старом коде всё ещё используется старый API через `sidekiq/testing`:

```ruby
require 'sidekiq/testing'
```

При таком `require` автоматически включается fake-режим.

**Fake** (`Sidekiq::Testing.fake!`) — задачи не отправляются в Redis. Вместо этого `perform_async` складывает JSON-хеш в массив класса: `SendEmailJob.jobs`. Самый частый режим для unit-тестов.

```ruby
Sidekiq::Testing.fake!

it "ставит задачу в очередь" do
  expect {
    SendEmailJob.perform_async(42)
  }.to change(SendEmailJob.jobs, :size).by(1)
end

it "отправляет email при выполнении" do
  SendEmailJob.perform_async(42)
  SendEmailJob.drain  # выполнить все накопленные задачи синхронно

  expect(ActionMailer::Base.deliveries.size).to eq(1)
end
```

`drain` выполняет все накопленные задачи синхронно, в текущем потоке. Это позволяет проверить и факт постановки, и результат выполнения.

**Inline** (`Sidekiq::Testing.inline!`) — `perform_async` немедленно выполняет задачу в текущем потоке. Без очереди, без задержки, без Redis. Полезно для integration-тестов, где важен конечный результат, а не механика очереди.

```ruby
Sidekiq::Testing.inline!

it "обрабатывает заказ полностью" do
  ProcessOrderJob.perform_async(order.id)
  # К этому моменту задача уже выполнена
  expect(order.reload).to be_processed
end
```

**Disable** (`Sidekiq::Testing.disable!`) — никакой подмены, задачи уходят в реальный Redis. Для end-to-end тестов с запущенным Sidekiq-процессом.

Выбор режима:

| Тест | Режим | Почему |
|------|-------|--------|
| Unit: проверить, что задача поставлена | fake | Не нужен Redis, быстро |
| Unit: проверить логику perform | direct call `job.perform(args)` | Ещё проще, не нужен даже fake |
| Integration: конечный результат цепочки | inline | Задачи выполняются синхронно |
| E2E: реальная обработка | disable | Полная цепочка с Redis |

## ActiveJob vs Sidekiq::Job

Тестовый режим отвечает на вопрос «как исполнять jobs в тестах». Следующий практический вопрос — каким API эти jobs вообще описывать, потому что от этого зависят сериализация аргументов, retry-семантика и совместимость с Pro-фичами.

Rails предоставляет ActiveJob — единый интерфейс для фоновых задач с возможностью переключения backend (Sidekiq, Resque, Delayed Job). Sidekiq поддерживает оба API:

```ruby
# ActiveJob
class SendEmailJob < ApplicationJob
  queue_as :default
  retry_on NetworkError, wait: 5.minutes, attempts: 3

  def perform(user_id)
    # ...
  end
end

# Sidekiq::Job (native API)
class SendEmailJob
  include Sidekiq::Job
  sidekiq_options queue: 'default', retry: 25

  def perform(user_id)
    # ...
  end
end
```

Trade-offs:

**ActiveJob** даёт абстракцию (переключение backend без изменения кода), GlobalID (передача ActiveRecord-объектов вместо ID), Rails-конвенции (`retry_on`, `discard_on`). Цена: ~30% overhead на сериализацию/десериализацию, несовместимость с Pro-фичами (Batches, rate limiting), ограниченный контроль над retry-логикой.

**Sidekiq::Job** даёт прямой доступ ко всем возможностям Sidekiq, лучшую производительность, полный контроль над retry (формула, per-job настройки, death handlers). Цена: привязка к Sidekiq.

Для большинства Rails-приложений, которые не планируют менять backend, `Sidekiq::Job` — более практичный выбор: меньше overhead, больше контроля, совместимость с Pro/Enterprise.

## Валидация аргументов

Одна из частых ошибок — передача неподдерживаемых типов в `perform_async`. Symbol, Time, ActiveRecord-объект — всё это тихо сериализуется в строку и ломается на стороне server. Ошибка проявляется при выполнении, а не при постановке — сложно отлаживать.

В актуальных версиях Sidekiq строгая проверка совместимых с JSON аргументов включена по умолчанию: попытка передать Symbol, Time или ActiveRecord-объект в `perform_async` вызывает исключение сразу на стороне client, в момент постановки задачи. Ошибка обнаруживается немедленно, а не через минуты в логах Sidekiq-процесса.

Если нужно ослабить проверку (например, в переходный период миграции старого кода):

```ruby
# config/initializers/sidekiq.rb
Sidekiq.strict_args!(:warn)  # предупреждение вместо исключения
Sidekiq.strict_args!(false)  # отключить проверку
```

## Частые ловушки

**Time.now в тестах.** Если job использует `Time.now`, результат зависит от момента выполнения. В fake-режиме задача выполняется позже через `drain` — время отличается. Решение: `freeze_time` или `travel_to` в тестах.

**Redis-состояние между тестами.** В disable-режиме задачи попадают в реальный Redis. Если тесты не чистят Redis — задачи накапливаются и влияют на следующие тесты. Решение: `Sidekiq::Testing.fake!` по умолчанию, disable — только для отдельных E2E тестов с явной очисткой.

**Не тестируй retry-логику через Sidekiq.** Retry — ответственность фреймворка, она покрыта тестами самого Sidekiq. Тестируй бизнес-логику внутри `perform`: вызови `job.perform(args)` напрямую и проверь результат. Исключение — кастомная `sidekiq_retry_in` или `sidekiq_retries_exhausted`, где поведение специфично для приложения.

---

<- [Concurrency и масштабирование](06-concurrency-and-scaling.md)

## Sources

- [Sidekiq Wiki — Testing](https://github.com/sidekiq/sidekiq/wiki/Testing)
- [Sidekiq Wiki — Active Job](https://github.com/sidekiq/sidekiq/wiki/Active-Job)
- [Sidekiq Wiki — Best Practices](https://github.com/sidekiq/sidekiq/wiki/Best-Practices)
- [Sidekiq source — `lib/sidekiq/config.rb`](https://github.com/sidekiq/sidekiq/blob/main/lib/sidekiq/config.rb)
- [Sidekiq source — `lib/sidekiq/job_util.rb`](https://github.com/sidekiq/sidekiq/blob/main/lib/sidekiq/job_util.rb)
