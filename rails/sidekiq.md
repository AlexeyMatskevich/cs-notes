# Sidekiq: Глубокое погружение для собеседования

## Содержание
1. [Архитектура и принципы работы](#1-архитектура-и-принципы-работы)
2. [Гарантии доставки и надёжность](#2-гарантии-доставки-и-надёжность)
3. [Жизненный цикл Job'а](#3-жизненный-цикл-jobа)
4. [Error Handling и Retries](#4-error-handling-и-retries)
5. [Сигналы и Graceful Shutdown](#5-сигналы-и-graceful-shutdown)
6. [Best Practices](#6-best-practices)
7. [Batches (Pro)](#7-batches-pro)
8. [Middleware](#8-middleware)
9. [Масштабирование и производительность](#9-масштабирование-и-производительность)
10. [Типичные вопросы на собеседовании](#10-типичные-вопросы-на-собеседовании)

---

## 1. Архитектура и принципы работы

### Как Sidekiq устроен внутри

Sidekiq использует **многопоточную модель** (не форки, как Resque), что делает его значительно более эффективным по памяти. Основные компоненты:

```
┌─────────────────────────────────────────────────────────────┐
│                    Sidekiq Process                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    Launcher                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  Manager 1  │  │  Manager 2  │  │  Heartbeat  │  │   │
│  │  │  (Capsule)  │  │  (Capsule)  │  │   Thread    │  │   │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  └─────────────┘  │   │
│  │  │ │Processor│ │  │ │Processor│ │                    │   │
│  │  │ │Processor│ │  │ │Processor│ │  ┌─────────────┐  │   │
│  │  │ │Processor│ │  │ └─────────┘ │  │   Poller    │  │   │
│  │  │ └─────────┘ │  └─────────────┘  │   Thread    │  │   │
│  │  └─────────────┘                    └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │      Redis      │
                    │  ┌───────────┐  │
                    │  │  queues   │  │  (Lists)
                    │  │  retry    │  │  (Sorted Set)
                    │  │  schedule │  │  (Sorted Set)
                    │  │  dead     │  │  (Sorted Set)
                    │  └───────────┘  │
                    └─────────────────┘
```

**Launcher** — главный объект, управляющий жизненным циклом процесса.

**Manager** — управляет набором Processor'ов в рамках одной "капсулы" (Capsule). Capsule — это изолированная группа с собственными настройками concurrency и queues.

**Processor** — один поток, который забирает job из очереди и выполняет его. Количество Processor'ов = настройка `concurrency` (по умолчанию 10).

**Poller** — отдельный поток, который проверяет `schedule` и `retry` sorted sets и перемещает "созревшие" job'ы в рабочие очереди.

**Heartbeat** — поток, обновляющий статус процесса в Redis. Данные ProcessSet/WorkSet обновляются каждые ~5 секунд, lifecycle event `:beat` вызывается каждые ~10 секунд.

### Как job попадает в очередь

```ruby
# Клиентская сторона (Rails app)
MyJob.perform_async(user_id, "some_data")

# Под капотом:
# 1. Создаётся JSON payload
job_hash = {
  "class" => "MyJob",
  "args" => [user_id, "some_data"],
  "jid" => "b4a577edbccf1d805744efa9",  # 12 байт → 24 символа hex
  "created_at" => 1234567890123,
  "queue" => "default",
  "retry" => true
}

# 2. Проходит через client middleware chain
# 3. Сериализуется в JSON
# 4. Отправляется в Redis: LPUSH queue:default <json>
```

### Как Sidekiq забирает job

```ruby
# Серверная сторона (Sidekiq process)
# Processor вызывает BasicFetch#retrieve_work

# Используется BRPOP — блокирующий pop с конца списка
# BRPOP queue:critical queue:default queue:low 2
# 
# Возвращает (queue_name, job_json) или nil после timeout

# ВАЖНО: BRPOP УДАЛЯЕТ job из Redis!
# Это ключевой момент для понимания reliability
```

### Терминология (важно для собеседования!)

Слово "worker" в экосистеме Sidekiq **неоднозначно и не рекомендуется**. Используй точные термины:

| Неточно | Точно |
|---------|-------|
| "10 workers" | 10 **threads** (Processor'ов) |
| "start a worker" | start a **process** |
| "worker class" | **job class** |
| "10 workers in queue" | 10 **jobs** |

---

## 2. Гарантии доставки и надёжность

### ⚠️ КРИТИЧЕСКИ ВАЖНО: "At least once" с оговорками

**Sidekiq (OSS) не гарантирует exactly-once выполнение!**

```
Sidekiq гарантирует: job будет выполнен AT LEAST ONCE
                     (по крайней мере один раз)

НО:
- Job может быть выполнен НЕСКОЛЬКО раз (при retry)
- Job может быть ПОТЕРЯН (в edge cases)
```

### Когда job может быть потерян (OSS версия)

**Сценарий 1: Crash процесса во время выполнения**
```
1. BRPOP забрал job из Redis (job удалён из очереди!)
2. Processor начал выполнять job
3. SIGKILL / segfault / OOM kill
4. Job потерян навсегда
```

**Сценарий 2: Redis недоступен при requeue**
```
1. Получен SIGTERM
2. Sidekiq пытается вернуть in-progress jobs в очередь
3. Redis down или out of memory
4. Jobs потеряны
```

**Сценарий 3: Некорректная конфигурация Redis**
```
# Если eviction policy НЕ noeviction, Redis может удалить jobs!
maxmemory-policy noeviction  # ОБЯЗАТЕЛЬНО для Sidekiq
```

### Как Sidekiq пытается минимизировать потери

При graceful shutdown (SIGTERM/SIGINT):

```ruby
# Manager#hard_shutdown
def hard_shutdown
  # 1. Собираем все in-progress jobs
  jobs = @workers.map { |p| p.job }.compact
  
  # 2. Возвращаем их в очередь (RPUSH)
  capsule.fetcher.bulk_requeue(jobs)
  
  # 3. Убиваем потоки
  cleanup.each { |processor| processor.kill }
end
```

**Но это работает только если:**
- Процесс получил SIGTERM/SIGINT (не SIGKILL!)
- У процесса есть время на shutdown (timeout, по умолчанию 25 сек)
- Redis доступен и имеет память

### Sidekiq Pro: super_fetch

Pro версия использует другой механизм:

```ruby
# Вместо BRPOP используется:
# 1. LMOVE source_queue private_queue (раньше RPOPLPUSH, который deprecated)
# Job атомарно перемещается в приватную очередь, но НЕ удаляется из Redis

# 2. После успешного выполнения: LREM private_queue job

# Если процесс упал — job остаётся в private_queue
# При старте нового процесса: orphan recovery
```

### Когда job выполняется несколько раз

```ruby
def perform(order_id)
  order = Order.find(order_id)
  order.charge_customer!    # ← Выполнилось
  order.send_email!         # ← Упало с ошибкой
end

# Job пойдёт в retry и выполнится снова
# charge_customer! выполнится ВТОРОЙ раз!
```

**Ещё сценарий (только Sidekiq Pro с super_fetch):**
```
1. Job выполнился успешно
2. Sidekiq Pro пытается удалить job из приватной очереди (acknowledge)
3. Сеть упала / Redis down
4. Job остаётся в приватной очереди как "orphan"
5. При восстановлении — job выполнится снова
```

**Примечание:** В OSS версии такого сценария нет! Там `acknowledge()` — пустой метод, ничего не делает. Job удаляется из Redis ещё при `BRPOP` (до начала выполнения), поэтому после успешного выполнения никакого обращения к Redis не происходит.

---

## 3. Жизненный цикл Job'а

```
┌──────────────────────────────────────────────────────────────────┐
│                         Job Lifecycle                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  perform_async() ──► [Enqueued] ──► [Busy] ──► [Processed] ✓     │
│                          │            │                           │
│                          │            ▼                           │
│                          │      (raises error)                    │
│                          │            │                           │
│                          │            ▼                           │
│                          │       [Failed] ──► [Retries]           │
│                          │                        │               │
│                          │                        ▼               │
│                          │                   (retrying...)        │
│                          │                        │               │
│                          │            ┌───────────┴───────────┐   │
│                          │            ▼                       ▼   │
│                          │      [Processed] ✓            [Dead]   │
│                          │                                        │
│  perform_at/in() ──► [Scheduled] ──► [Enqueued] ──► ...         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Состояния в Web UI

**Processed** — успешно завершено (финальное состояние)

**Failed** — счётчик ВСЕХ ошибок. Один job с 25 retry может дать +25 к Failed. Это транзитивное состояние, job никогда не "застрянет" в Failed.

**Busy** — сейчас выполняется

**Enqueued** — ждёт в очереди

**Retries** — упал, будет повторён позже (sorted set по времени retry)

**Scheduled** — запланирован на будущее (perform_at/perform_in)

**Dead** — исчерпал все retry, требует ручного вмешательства

### Изменение поведения через sidekiq_options

```ruby
class SomeJob
  include Sidekiq::Job
  
  # Полностью отключить retry — job просто исчезнет при ошибке
  sidekiq_options retry: false
  
  # 0 retry — сразу в Dead при первой ошибке
  sidekiq_options retry: 0
  
  # Кастомное количество retry
  sidekiq_options retry: 5
  
  # Использовать другую очередь для retry
  sidekiq_options retry_queue: 'low_priority'
end
```

---

## 4. Error Handling и Retries

### Формула retry delay

```ruby
# Экспоненциальный backoff + jitter
delay = (retry_count ** 4) + 15 + (rand(10) * (retry_count + 1))

# Примерные значения:
# Retry 0: ~15-25 секунд
# Retry 1: ~16-36 секунд  
# Retry 2: ~31-60 секунд
# Retry 3: ~96-140 секунд
# ...
# Retry 24: ~19-20 дней от первой попытки
```

**25 retry = ~20 дней** — достаточно времени, чтобы задеплоить фикс.

### Dead Set (морг)

```ruby
# Ограничения Dead set:
# - Максимум 10,000 jobs
# - Хранятся 6 месяцев
# - Потом автоматически удаляются
```

### Кастомизация retry поведения

```ruby
class MyJob
  include Sidekiq::Job
  
  # Кастомный интервал между retry
  sidekiq_retry_in do |count, exception, job_hash|
    case exception
    when RateLimitError
      60 * 60  # Подождать час
    when NetworkError
      10 * (count + 1)  # Линейный backoff
    else
      :default  # Использовать стандартную формулу
    end
  end
  
  # Что делать когда retry исчерпаны
  sidekiq_retries_exhausted do |job, exception|
    # Можно отправить в Slack, записать в БД, etc.
    Notifier.alert("Job #{job['jid']} died: #{exception.message}")
    
    # Можно вернуть :discard — job не попадёт в Dead set
    # :discard
  end
end
```

### Death Handlers (глобальные)

```ruby
Sidekiq.configure_server do |config|
  config.death_handlers << ->(job, exception) do
    # Вызывается для КАЖДОГО job, который умер
    puts "Job #{job['class']} died with #{exception.message}"
  end
end
```

### Важно: Retries vs Errors

```ruby
# Sidekiq retry — для НЕОЖИДАННЫХ ошибок:
# - Баги
# - Временная недоступность сервисов
# - Network issues

# НЕ используй retry для бизнес-логики:
# ❌ Плохо
def perform(order_id)
  order = Order.find(order_id)
  raise "Order not paid" unless order.paid?  # НЕ НАДО ТАК
end

# ✅ Хорошо — используй state machine
def perform(order_id)
  order = Order.find(order_id)
  return unless order.paid?  # Просто выйди
  order.process!
end
```

---

## 5. Сигналы и Graceful Shutdown

### Сигналы, которые понимает Sidekiq

| Сигнал | Действие |
|--------|----------|
| **TSTP** | "Тихий режим" — перестать брать новые jobs, дорабатывать текущие |
| **TERM** | Начать shutdown с timeout (по умолчанию 25 сек) |
| **INT** | То же, что TERM |
| **TTIN** | Вывести backtrace всех потоков (для отладки) |

### Правильный deploy

```bash
# 1. В НАЧАЛЕ деплоя — отправить TSTP
kill -TSTP <sidekiq_pid>
# Sidekiq перестаёт брать новые jobs

# 2. ...деплой происходит...

# 3. В КОНЦЕ деплоя — отправить TERM
kill -TERM <sidekiq_pid>
# Sidekiq начинает shutdown

# ВАЖНО: Дать Sidekiq достаточно времени!
# Если timeout = 25 сек, дай 30+ секунд до kill -9
```

### ⚠️ Никогда не делай

```bash
# ❌ ПЛОХО — потеря jobs
kill -9 <sidekiq_pid>

# ❌ ПЛОХО — kill сразу после TERM
kill -TERM <pid> && sleep 5 && kill -9 <pid>
# 5 секунд недостаточно!
```

### Конфигурация timeout

```yaml
# config/sidekiq.yml
:timeout: 25  # секунд на завершение после TERM

# Или через CLI
bundle exec sidekiq -t 30
```

### Lifecycle Events

```ruby
Sidekiq.configure_server do |config|
  config.on(:startup) do
    # После загрузки, до начала обработки jobs
    puts "Sidekiq is starting up"
  end
  
  config.on(:quiet) do
    # Получен TSTP
    puts "Got TSTP, stopping new work"
  end
  
  config.on(:shutdown) do
    # Получен TERM, начинается shutdown
    puts "Shutting down..."
  end
end
```

### Long-running jobs и Iteration (7.3+)

Если job выполняется дольше timeout — он будет прерван принудительно.

**Решение 1: `interrupted?` метод**
```ruby
class LongJob
  include Sidekiq::Job
  
  def perform
    huge_list.each do |item|
      process(item)
      
      # Проверяем, не пора ли остановиться
      if interrupted?
        # Sidekiq сохранит наш прогресс и перезапустит job
        raise Sidekiq::Shutdown
      end
    end
  end
end
```

**Решение 2: IterableJob (7.3+)**
```ruby
class LongJob
  include Sidekiq::IterableJob  # Не Sidekiq::Job!
  
  def build_enumerator(user_id, cursor:)
    # Возвращаем enumerator с поддержкой cursor
    active_record_records_enumerator(
      User.find(user_id).posts,
      cursor: cursor
    )
  end
  
  def each_iteration(post)
    # Обработка одного элемента
    post.reindex!
  end
  
  def on_complete
    # Когда всё обработано
    puts "Done!"
  end
end

# При TSTP/TERM:
# 1. Текущая итерация завершается
# 2. Cursor сохраняется в Redis
# 3. Job перезапускается с сохранённого места
```

---

## 6. Best Practices

### 1. Аргументы должны быть простыми

```ruby
# ❌ ПЛОХО — объект не сериализуется в JSON
user = User.find(1)
MyJob.perform_async(user)  # => "#<User:0x000055f>"

# ❌ ПЛОХО — Symbol не переживёт JSON round-trip
MyJob.perform_async(status: :active)  # symbols станут strings!

# ❌ ПЛОХО — Time/Date не сериализуются корректно
MyJob.perform_async(Time.now)  # => строка "2024-..."

# ✅ ХОРОШО — простые типы
MyJob.perform_async(user.id)
MyJob.perform_async("active")  # строка вместо символа
MyJob.perform_async(Time.now.to_i)  # timestamp
```

**Разрешённые типы:** String, Integer, Float, Boolean, nil, Array, Hash (с string keys!)

**Почему так происходит?**

Sidekiq хранит jobs в Redis как JSON-строки. При вызове `perform_async` происходит `JSON.dump`, при выполнении — `JSON.parse`. JSON — текстовый формат, который знает только примитивные типы.

Когда `JSON.dump` встречает объект (например, `User`), он не знает как его сериализовать и вызывает `.to_s`:

```ruby
user = User.find(1)
user.to_s                    # => "#<User:0x000055f1a2b3c4d5>"
JSON.dump({ args: [user] })  # => '{"args":["#<User:0x000055f1a2b3c4d5>"]}'
```

На стороне Sidekiq сервера `JSON.parse` вернёт просто строку:

```ruby
# perform получит бесполезную строку, не объект!
def perform(user)
  user.email  # NoMethodError: undefined method `email' for "#<User:0x...>":String
end
```

**Символы превращаются в строки:**

```ruby
MyJob.perform_async(status: :active)

# В Redis: {"args":[{"status":"active"}]}  — символ стал строкой!

def perform(options)
  options[:status]   # => nil (ключ тоже стал строкой!)
  options["status"]  # => "active" (строка, не символ)
  
  # Этот код сломается:
  if options[:status] == :active  # nil == :active → false
    # никогда не выполнится!
  end
end
```

**Time/Date превращаются в строки:**

```ruby
MyJob.perform_async(Time.now)

# В Redis: {"args":["2024-01-15 10:30:00 +0300"]}

def perform(time)
  time.hour  # NoMethodError — это строка, не Time!
end
```

**Бонус правильного подхода:** если между `perform_async` и выполнением прошло время (очередь была забита), ты получишь актуальное состояние объекта из БД, а не устаревший снимок.

### 2. Jobs должны быть идемпотентными

```ruby
# ❌ ПЛОХО — не идемпотентно
def perform(user_id, amount)
  user = User.find(user_id)
  user.balance += amount  # При retry добавится ещё раз!
  user.save!
end

# ✅ ХОРОШО — идемпотентно
def perform(transaction_id)
  transaction = Transaction.find(transaction_id)
  return if transaction.processed?  # Уже обработано
  
  transaction.process!
end

# ✅ ХОРОШО — с использованием unique constraint
def perform(order_id)
  order = Order.find(order_id)
  # DB constraint не даст создать дубликат
  Payment.create!(order: order, idempotency_key: "order-#{order_id}")
rescue ActiveRecord::RecordNotUnique
  # Уже создано, всё ок
end
```

### 3. Обрабатывай транзакции правильно

```ruby
# ❌ ПЛОХО — job создаётся до commit, может потеряться
def create_order
  ActiveRecord::Base.transaction do
    order = Order.create!(...)
    ProcessOrderJob.perform_async(order.id)  # Job уже в Redis!
    
    raise "Something failed"  # Order откатится, но job останется
  end
end

# ✅ ХОРОШО — after_commit
class Order < ApplicationRecord
  after_commit :enqueue_processing, on: :create
  
  def enqueue_processing
    ProcessOrderJob.perform_async(id)
  end
end

# ✅ ХОРОШО — transactional push (Sidekiq 7.2+)
def create_order
  Sidekiq::Client.via(Sidekiq.redis_pool) do
    ActiveRecord::Base.transaction do
      order = Order.create!(...)
      ProcessOrderJob.perform_async(order.id)
      # Job отправится в Redis только после commit!
    end
  end
end
```

### 4. Не храни состояние в job

```ruby
# ❌ ПЛОХО — состояние не сохранится между retry
def perform(user_id)
  @retry_count ||= 0
  @retry_count += 1  # Всегда будет 1!
end

# ✅ ХОРОШО — используй job payload
def perform(user_id)
  # Информация о retry доступна через sidekiq_options или job hash
  retry_count = Thread.current[:sidekiq_context]["retry_count"] || 0
end
```

### 5. Bulk Queueing для массовых операций

```ruby
# ❌ ПЛОХО — 1000 round-trips к Redis
1000.times do |i|
  MyJob.perform_async(i)
end

# ✅ ХОРОШО — 1 round-trip
Sidekiq::Client.push_bulk(
  'class' => MyJob,
  'args' => (0...1000).map { |i| [i] }
)

# ✅ ХОРОШО — удобный helper (6.3+)
MyJob.perform_bulk([[1], [2], [3], ...])
```

---

## 7. Batches (Pro)

### Что такое Batch

Batch — это группа jobs, которую можно отслеживать как единое целое и получать callback'и при завершении.

```ruby
batch = Sidekiq::Batch.new
batch.description = "Import users from CSV"
batch.on(:success, ImportCallbacks, email: 'admin@example.com')
batch.on(:complete, ImportCallbacks)
batch.on(:death, ImportCallbacks)

batch.jobs do
  csv_rows.each do |row|
    ImportRowJob.perform_async(row)
  end
end

puts "Started batch #{batch.bid}"
```

### Callbacks

```ruby
class ImportCallbacks
  # Все jobs успешно завершились
  def on_success(status, options)
    Mailer.import_complete(options['email']).deliver_now
  end
  
  # Все jobs выполнились (успешно или нет)
  def on_complete(status, options)
    if status.failures > 0
      Mailer.import_failed(status.failures).deliver_now
    end
  end
  
  # Первый job умер (после всех retry)
  def on_death(status, options)
    Mailer.import_died(status).deliver_now
  end
end
```

### ⚠️ Важные ограничения Batches

```ruby
# ❌ НЕ вызывай batch.jobs несколько раз при создании!
batch = Sidekiq::Batch.new
10.times do
  batch.jobs do  # Race condition!
    MyJob.perform_async
  end
end

# ✅ Один вызов batch.jobs
batch = Sidekiq::Batch.new
batch.jobs do
  10.times { MyJob.perform_async }
end

# ✅ Добавлять jobs изнутри job'а в этом же batch — МОЖНО
class MyJob
  include Sidekiq::Job
  
  def perform
    batch.jobs do  # Текущий batch
      ChildJob.perform_async
    end
  end
end
```

### Batches НЕ работают с ActiveJob

```ruby
# ❌ ActiveJob retry выглядит как success для Sidekiq
# Batch может завершиться "успешно" пока job ещё retry'ится

# ✅ Используй native Sidekiq::Job для batch jobs
```

### Stuck Batches

Batch может "застрять" (pending jobs, которых нет):

1. **Job потерян при crash** — включи super_fetch!
2. **Job потерян при deploy** — используй TSTP + правильный timeout
3. **Transactional push race condition** — обновись до 7.2.2+

---

## 8. Middleware

### Два типа middleware

Оба типа работают по принципу "вокруг" (wrap around) с `yield`:

**Client middleware** — оборачивает отправку job в Redis
**Server middleware** — оборачивает выполнение job

```
Client:  [MW1 до] -> [MW2 до] -> [MW3 до] -> PUSH -> [MW3 после] -> [MW2 после] -> [MW1 после]

Server:  FETCH -> [MW1 до] -> [MW2 до] -> perform -> [MW2 после] -> [MW1 после]
```

Это классический middleware паттерн — каждый middleware вызывает `yield`, который передаёт управление следующему в цепочке (или основному действию), а потом может выполнить код после.

### Пример Client Middleware

```ruby
class ClientMiddleware
  include Sidekiq::ClientMiddleware
  
  def call(job_class, job, queue, redis_pool)
    # ДО отправки в Redis
    job['enqueued_by'] = Current.user&.id
    job['request_id'] = Current.request_id
    puts "Отправляем #{job_class} в очередь #{queue}"
    
    result = yield  # ← Тут job уходит в Redis (или в следующий middleware)
    
    # ПОСЛЕ отправки в Redis
    puts "Job отправлен, JID: #{result}"
    
    result  # Вернуть результат (JID) или false/nil чтобы отменить
  end
end

Sidekiq.configure_client do |config|
  config.client_middleware do |chain|
    chain.add ClientMiddleware
  end
end
```

### Пример Server Middleware

```ruby
class ServerMiddleware
  include Sidekiq::ServerMiddleware
  
  def call(job_instance, job_payload, queue)
    # ДО выполнения job
    Current.request_id = job_payload['request_id']
    start = Time.now
    
    yield  # ← Тут выполняется job.perform (или следующий middleware)
    
    # ПОСЛЕ успешного выполнения (если было исключение — сюда не дойдём)
    duration = Time.now - start
    Metrics.record(job_payload['class'], duration)
  rescue => e
    # Можно залогировать, модифицировать, или просто пробросить дальше
    Metrics.record_error(job_payload['class'], e)
    raise  # Пробрасываем, чтобы Sidekiq сделал retry
  ensure
    # Выполнится ВСЕГДА — и при успехе, и при ошибке
    Current.reset
  end
end

Sidekiq.configure_server do |config|
  config.server_middleware do |chain|
    chain.add ServerMiddleware
  end
end
```

### ⚠️ Важно: client middleware в server

```ruby
# Jobs могут создавать другие jobs!
# Поэтому client middleware нужно настроить и в server:

Sidekiq.configure_server do |config|
  config.client_middleware do |chain|
    chain.add ClientMiddleware
  end
  config.server_middleware do |chain|
    chain.add ServerMiddleware
  end
end
```

### CurrentAttributes (Rails 6.3+)

```ruby
# Автоматически сохраняет и восстанавливает Current атрибуты
Sidekiq.configure_server do |config|
  config.server_middleware do |chain|
    chain.add Sidekiq::CurrentAttributes::Middleware, Current
  end
end

Sidekiq.configure_client do |config|
  config.client_middleware do |chain|
    chain.add Sidekiq::CurrentAttributes::Client, Current
  end
end
```

---

## 9. Масштабирование и производительность

### Concurrency

```yaml
# config/sidekiq.yml
:concurrency: 25  # 25 потоков на процесс
```

**Как выбрать concurrency:**

**I/O-bound jobs** (API calls, DB queries, отправка email): можно 20-50+. Пока один поток ждёт ответа от сети — другие работают. GIL освобождается при I/O.

**CPU-bound jobs** (обработка изображений, парсинг, вычисления): concurrency почти не важен! Из-за GIL потоки всё равно выполняются по очереди. Хоть 1 поток, хоть 10 — скорость одинаковая. Для параллелизма нужны отдельные процессы, а не потоки.

**Ограничение:** database connection pool! Каждый поток может держать соединение с БД.

```ruby
# database.yml
# pool должен быть >= concurrency
production:
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 25 } %>
```

### Несколько процессов vs Несколько потоков

```bash
# I/O-bound: один процесс с большим concurrency — ОК
bundle exec sidekiq -c 50

# CPU-bound: несколько процессов с маленьким concurrency
bundle exec sidekiq -c 2  # Процесс 1
bundle exec sidekiq -c 2  # Процесс 2
bundle exec sidekiq -c 2  # Процесс 3
bundle exec sidekiq -c 2  # Процесс 4
# 4 процесса = 4 GIL = реальный параллелизм на 4 ядрах
```

Несколько процессов также лучше для изоляции: если один упадёт (OOM, segfault), остальные продолжат работать.

### Queue Priority

```yaml
# config/sidekiq.yml

# Strict priority — bulk будет обрабатываться только когда default пуст
:queues:
  - critical
  - default
  - bulk

# Weighted — случайный выбор с весами
:queues:
  - [critical, 10]  # 10x вероятнее
  - [default, 5]    # 5x
  - [bulk, 1]       # baseline
```

### Queues и Processes

```bash
# Разные процессы для разных очередей
bundle exec sidekiq -q critical -q default  # Process 1
bundle exec sidekiq -q bulk                  # Process 2
```

### Redis Considerations

```ruby
# Отдельный Redis для jobs!
# НЕ используй один Redis для cache + jobs

# В jobs: Redis может быть полностью заполнен job'ами
# В cache: Eviction policy удалит "неважные" ключи (включая jobs!)

Sidekiq.configure_server do |config|
  config.redis = { 
    url: "redis://jobs-redis.example.com:6379/0",
    # Используй connection pool
    size: 25  # >= concurrency
  }
end
```

### Latency и Monitoring

```ruby
# Sidekiq::Stats
stats = Sidekiq::Stats.new
stats.processed  # Всего обработано
stats.failed     # Всего ошибок
stats.enqueued   # Сейчас в очередях

# Latency очереди (время ожидания самого старого job)
queue = Sidekiq::Queue.new("default")
queue.latency  # секунды
```

---

## 10. Типичные вопросы на собеседовании

### Q: Чем Sidekiq отличается от Resque?

**A:** Sidekiq использует потоки (threads), Resque — процессы (forks). Sidekiq значительно эффективнее по памяти (один процесс с 10 потоками vs 10 процессов) и быстрее из-за меньшего overhead на создание потоков vs fork.

### Q: Гарантирует ли Sidekiq exactly-once выполнение?

**A:** Нет! Sidekiq гарантирует "at least once" — job выполнится минимум один раз, но может выполниться несколько раз (при retry) или потеряться (при crash). Для критичных операций нужна идемпотентность на уровне приложения.

### Q: Что случится, если job выполняется дольше timeout при shutdown?

**A:** 
1. При получении SIGTERM Sidekiq ждёт timeout секунд (default 25)
2. Если job не завершился — Sidekiq делает bulk_requeue всех in-progress jobs
3. Job будет перезапущен (возможно дублирование!)
4. Для long-running jobs используй `interrupted?` или IterableJob

### Q: Как обеспечить, что job не выполнится дважды?

**A:** Идемпотентность! Варианты:
- Unique constraints в БД
- Check-and-set паттерн (проверить состояние перед действием)
- Idempotency keys (сохранять ключ операции, проверять наличие)
- Unique Jobs (Enterprise) или sidekiq-unique-jobs gem

### Q: Когда использовать perform_async vs perform_in vs perform_at?

```ruby
# perform_async — выполнить как можно скорее
MyJob.perform_async(args)

# perform_in — выполнить через X секунд/минут/часов
MyJob.perform_in(5.minutes, args)  # Rails
MyJob.perform_in(300, args)        # Plain Ruby

# perform_at — выполнить в конкретное время
MyJob.perform_at(2.hours.from_now, args)
```

### Q: Как отладить "застрявший" job?

```ruby
# 1. Проверить Retry set
Sidekiq::RetrySet.new.each do |job|
  puts "#{job.klass}: #{job.args}, retry_count: #{job['retry_count']}"
end

# 2. Проверить Dead set
Sidekiq::DeadSet.new.each do |job|
  puts "#{job.klass}: #{job['error_message']}"
end

# 3. Проверить scheduled
Sidekiq::ScheduledSet.new.each do |job|
  puts "#{job.klass} scheduled for #{Time.at(job.at)}"
end

# 4. Проверить in-progress
Sidekiq::WorkSet.new.each do |process_id, thread_id, work|
  puts "#{work.payload['class']} running for #{Time.now - Time.at(work.run_at)} sec"
end
```

### Q: Как правильно тестировать Sidekiq jobs?

```ruby
# spec_helper.rb
require 'sidekiq/testing'

# Вариант 1: Fake — jobs накапливаются в массиве
Sidekiq::Testing.fake!

it "enqueues a job" do
  expect {
    MyJob.perform_async(1)
  }.to change(MyJob.jobs, :size).by(1)
end

# Вариант 2: Inline — jobs выполняются сразу
Sidekiq::Testing.inline!

it "processes immediately" do
  expect { MyJob.perform_async(1) }
    .to change { User.count }.by(1)
end

# Вариант 3: Disable — как в production
Sidekiq::Testing.disable!
# Jobs реально отправляются в Redis
```

### Q: Что такое Capsule и зачем он нужен?

**A:** Capsule (капсула) — это изолированная группа настроек внутри одного Sidekiq процесса. Каждая капсула имеет свой набор очередей и свой concurrency. Это позволяет, например, выделить 5 потоков для критичных jobs и 20 для обычных в рамках одного процесса.

```ruby
Sidekiq.configure_server do |config|
  config.capsule("critical") do |cap|
    cap.concurrency = 5
    cap.queues = %w[critical]
  end
end
```

### Q: Как Redis падение влияет на Sidekiq?

**A:**
- **Push:** perform_async вызовет exception, нужно обрабатывать в приложении
- **Fetch:** Sidekiq будет retry подключение с backoff, jobs не потеряются (они в Redis)
- **In-progress jobs:** Продолжат выполняться, но requeue при shutdown не сработает
- **Pro: reliable_push** — буферизует jobs локально при Redis downtime

### Q: Разница между ActiveJob и Sidekiq::Job?

```ruby
# ActiveJob — стандартный Rails интерфейс
class MyJob < ApplicationJob
  queue_as :default
  
  retry_on SomeError, wait: 5.minutes, attempts: 3
  
  def perform(args)
    # ...
  end
end

# Sidekiq::Job — native Sidekiq API
class MyJob
  include Sidekiq::Job
  sidekiq_options queue: 'default', retry: 25
  
  def perform(args)
    # ...
  end
end
```

**Sidekiq::Job лучше когда:**
- Нужен полный контроль над retry логикой
- Используешь Batches (Pro)
- Важна производительность (~30% overhead у ActiveJob)
- Не планируешь менять backend

**ActiveJob лучше когда:**
- Нужна переносимость между backends
- Хочешь использовать Rails conventions
- Не используешь Pro/Enterprise features
