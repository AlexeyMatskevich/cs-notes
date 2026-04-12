---
tags:
  - domain/ruby
  - theme/concurrency
  - type/concept
aliases:
  - GVL
  - Fiber
  - Ractor
order: 1
---

# Конкурентность и параллелизм в Ruby

> [!info]- Предпосылки
> Базовое знание Ruby (потоки, блоки); [потоки ОС](../../linux/foundations/threads.md) — создание, контекстные переключения, pthread; [синхронизация](../../linux/concurrency/synchronization.md) — mutex, condition variable, futex; [модель памяти](../../linux/concurrency/memory-ordering.md) — барьеры, видимость, happens-before.

## Один поток — сто запросов

Типичное Rails-приложение: запрос приходит, контроллер вызывает ActiveRecord, тот отправляет SQL в PostgreSQL. Ответ от БД — 100 мс. Парсинг результата и рендеринг — ещё 5 мс CPU. Один поток обработал один запрос за 105 мс. Пока ждал БД, CPU был свободен 95% времени.

При 100 одновременных клиентах последний в очереди ждёт 10.5 секунд — и это при одном запросе на клиента. На практике каждый запрос делает 3-5 обращений к БД и Redis. Время растёт линейно с числом клиентов, но CPU загружен на 5%.

Проблема не в вычислениях — проблема в ожидании. Пока поток спит на `read()` от [[linux/programming/sockets|сокета]] PostgreSQL, другие запросы стоят в очереди. Нужен способ обрабатывать второй запрос, пока первый ждёт I/O.

## Конкурентность и параллелизм

Два способа занять CPU полезной работой вместо ожидания.

**Конкурентность (concurrency)** — чередование задач: пока одна ждёт I/O, другая выполняет код. На одном ядре задачи по очереди получают CPU; настоящей одновременности нет, но прогресс идёт по нескольким задачам.

**Параллелизм (parallelism)** — одновременное выполнение на разных ядрах. Два потока буквально исполняют инструкции в один и тот же момент.

```text
Конкурентно (1 core):   A A A A A
                        B B B B B
                        ^--- чередуются во времени

Параллельно (2 cores):  core0: A A A A A
                        core1: B B B B B
```

Чередование требует прерывания выполнения. **Вытесняющая (preemptive) многозадачность** — [планировщик ОС](../../linux/foundations/scheduler.md) останавливает поток по таймеру и отдаёт CPU другому. Программист не контролирует точку переключения, поэтому доступ к общим данным нужно [синхронизировать](../../linux/concurrency/synchronization.md). **Кооперативная (cooperative) многозадачность** — задача сама отдаёт управление в известных точках (yield/await). Точки переключения видны в коде, но задача, которая никогда не уступает, блокирует остальные.

Ruby использует оба подхода: Thread — вытесняемый (через ОС), Fiber — кооперативный (через yield).

## Thread: нативные потоки Ruby

Ruby Thread — это pthread ([подробнее о потоках ОС](../../linux/foundations/threads.md)). При создании четырёх Thread MRI вызывает `pthread_create` четыре раза, плюс один внутренний timer thread:

```text
Ruby процесс
+-- pthread #1 (main thread)     -> Ruby Thread.main
+-- pthread #2                   -> Ruby Thread #2
+-- pthread #3                   -> Ruby Thread #3
+-- pthread #4                   -> Ruby Thread #4
+-- pthread #5 (timer thread)    -> внутренний, ставит флаг "пора отдать GVL"
```

Создание потоков и ожидание результата:

```ruby
threads = 4.times.map do |i|
  Thread.new(i) do |n|
    sleep(0.1)          # имитация I/O
    n * 10
  end
end

results = threads.map(&:value) # блокирует до завершения, возвращает результат
p results #=> [0, 10, 20, 30]
```

`Thread#value` блокирует вызывающий поток и возвращает результат блока. Если внутри возникло исключение, `value` бросит его повторно.

### I/O overlap: потоки полезны даже с GVL

Когда поток вызывает blocking I/O (`socket.read`, `File.read`, `sleep`), MRI отпускает GVL (Global VM Lock — о нём ниже). Другие потоки могут выполнять Ruby-код, пока первый ждёт завершения системного вызова и спит в [режиме ядра](../../linux/foundations/cpu-modes-and-syscalls.md):

```text
Время    Thread #1          Thread #2              Thread #3
-----    ---------          ---------              ---------
t1       держит GVL,        ждёт GVL               ждёт GVL
         выполняет код

t2       вызывает socket.read
         |
         v
         ОТПУСКАЕТ GVL --> Thread #2 захватывает GVL
         |                 выполняет Ruby-код
         v
         read() syscall
         спит в ядре
         (ждёт данные)

t3       спит в ядре        выполняет код          ждёт GVL

t4       данные пришли!
         ждёт GVL

t5       <-- захватил GVL   ждёт GVL               ждёт GVL
         продолжает
```

Для I/O-bound задач (веб-приложения, запросы к БД, HTTP-клиенты) потоки эффективно перекрывают ожидание. Пять потоков, каждый из которых 80% времени ждёт I/O, утилизируют CPU в четыре раза лучше, чем один.

Но если задача CPU-bound — чистые вычисления без I/O — потоки не помогут:

```ruby
Thread.new do
  # Этот код держит GVL ~100ms, потом отдаёт на несколько ms
  result = 0
  100_000_000.times { |i| result += i }
end

Thread.new do
  # Этот поток получает CPU только в короткие окна
  puts "Выполняюсь урывками!"
end
```

Второй поток фактически простаивает, пока первый считает. Причина — GVL.

## GVL: почему потоки не ускоряют CPU-код

### Что GVL делает

GVL (Global VM Lock) — это mutex на уровне интерпретатора MRI. В каждый момент времени только один поток выполняет Ruby-байткод. Все остальные потоки, желающие исполнять Ruby-код, блокируются на этом mutex и спят в ядре ([через futex](../../linux/concurrency/synchronization.md)), пока GVL не освободится.

GVL защищает внутренние структуры [[ruby/internal/vm/execution|VM]]: таблицы [[ruby/internal/methods/method-dispatch|методов]], constant tables, аллокатор [[ruby/internal/object-model/objects-and-classes|объектов]]. Без глобальной блокировки каждую из этих структур пришлось бы защищать отдельным локом (как делают JRuby и TruffleRuby). Исторически MRI выбрал простоту: один лок на всё, потому что Ruby ориентирован на I/O-bound задачи, а C-расширения напрямую манипулируют Ruby-объектами без синхронизации.

GVL реализован через `pthread_mutex_t` + `pthread_cond_t`. При освобождении GVL Ruby будит одного ожидающего потока через `pthread_cond_signal`. Вход/выход из GVL включает барьеры памяти ([модель памяти](../../linux/concurrency/memory-ordering.md)), поэтому записи одного потока видны потоку, который следующим захватил GVL. В MRI проблем с visibility нет.

Timer thread периодически ставит флаг прерывания. Поток, держащий GVL, проверяет этот флаг между [[ruby/internal/vm/compilation|байткод]]-инструкциями и при необходимости уступает GVL другому потоку. С Ruby 3.4 квант можно настраивать через `RUBY_THREAD_TIMESLICE` (в миллисекундах).

```text
GVL (контролируемые точки): Thread A выполняет Ruby --(timer interrupt)--> флаг проверяется
                                                                           между инструкциями
                                                                                |
                                                            (нужно уступить) --> отдаёт GVL -> Thread B
```

### Когда GVL отпускается

GVL отпускается в трёх ситуациях: при blocking I/O (сеть, диск, `sleep`), при вызове C-расширений через `rb_thread_call_without_gvl`, и при `Thread.pass`. Во всех случаях другие потоки получают возможность выполнять Ruby-код.

Два эксперимента, демонстрирующих ожидание:

```ruby
# Blocking I/O = поток спит в ядре
r, w = IO.pipe
t = Thread.new { r.read(1) }  # blocking read
sleep 0.05
p t.status   # "sleep" — поток в ядре, GVL отпущен

w.write("x") # данные пришли -> ядро будит поток
t.join

# Ожидание лока = поток спит, не крутится
mutex = Mutex.new
mutex.lock
t = Thread.new { mutex.synchronize { :ok } }
sleep 0.05
p t.status   # "sleep" — поток ждёт mutex через futex

mutex.unlock
t.join
```

В обоих случаях `status` возвращает "sleep" — поток не потребляет CPU, он ждёт в ядре.

### GVL не равно thread-safety

GVL гарантирует: в каждый момент только один поток исполняет [[ruby/internal/vm/compilation|байткод]]. Переключение между потоками происходит между [[ruby/internal/vm/compilation|байткод]]-инструкциями, а не между Ruby-выражениями. Одна строка Ruby — несколько инструкций:

```ruby
# Выглядит как одна операция:
counter += 1

# Но это несколько байткод-инструкций:
# 1. getlocal counter    (read)
# 2. putobject 1
# 3. opt_plus            (add)
# 4. setlocal counter    (write)
# GVL может переключиться между любыми из них!

# Thread 1:                    # Thread 2:
# getlocal counter (= 5)
#    --- GVL переключился ---
#                              # getlocal counter (= 5)
#                              # opt_plus (= 6)
#                              # setlocal counter (= 6)
#    --- GVL вернулся ---
# opt_plus (= 6)
# setlocal counter (= 6)       # Результат: 6, а не 7!
```

Race condition проявляется так же, как в любой многопоточной среде: check-then-act последовательности не атомарны. Защита — `Mutex#synchronize`:

```ruby
mutex = Mutex.new

# Это НЕ атомарно, даже с GVL:
if @hash[:key].nil?
  @hash[:key] = expensive_computation
end

# Корректный вариант:
mutex.synchronize do
  if @hash[:key].nil?
    @hash[:key] = expensive_computation
  end
end
```

### M:N threading (Ruby 3.3+)

[Модели потоков](../../linux/foundations/threads.md): Ruby 1.8 использовал M:1 (green threads), с 1.9 перешёл на 1:1 (pthread на каждый Thread). Ruby 3.3 добавил M:N планировщик — M Ruby-потоков на N нативных потоков. На main ractor M:N отключён по умолчанию, включается через `RUBY_MN_THREADS=1`. На non-main ractors M:N включён. Число нативных потоков ограничивается `RUBY_MAX_CPU=n` (по умолчанию 8).

GVL ограничивает CPU-параллелизм. Потоки полезны для I/O-конкурентности: [Sidekiq](../../rails/sidekiq/concurrency-and-scaling.md) использует пул потоков именно по этой причине — задачи большую часть времени ждут I/O (БД, HTTP, Redis), и GVL не мешает. Но когда соединений тысячи, потоки становятся слишком тяжёлыми — нужен более дешёвый примитив.

## Fiber: дешёвая конкурентность для I/O

### Почему потоки дорогие для массовой конкурентности

Каждый pthread резервирует под стек заметный объём [виртуальной памяти](../../linux/foundations/virtual-memory.md) (на Linux это часто мегабайты на поток). Для 10 000 одновременных соединений — 10 000 потоков — это десятки гигабайт виртуального адресного пространства и заметная нагрузка на [планировщик](../../linux/foundations/scheduler.md): переключение контекста стоит микросекунды, а при большом числе потоков ядро тратит CPU на выбор следующего кандидата.

Fiber — корутина с собственным стеком, но значительно дешевле потока. В 64-bit CRuby дефолтные stack budgets для `Thread` составляют 256 KiB VM stack и 1024 KiB machine stack, а для `Fiber` — 128 KiB и 512 KiB. Переключение между fiber происходит внутри runtime в [пользовательском режиме](../../linux/foundations/cpu-modes-and-syscalls.md), без отдельного системного вызова на сам факт переключения.

> [!info]- Подробности: настройка размеров стека
> Размеры thread/fiber stack в CRuby можно менять через переменные окружения `RUBY_THREAD_VM_STACK_SIZE`, `RUBY_THREAD_MACHINE_STACK_SIZE`, `RUBY_FIBER_VM_STACK_SIZE` и `RUBY_FIBER_MACHINE_STACK_SIZE`.

### Fiber: resume, yield, обмен значениями

```ruby
f = Fiber.new do
  puts "A"
  Fiber.yield
  puts "B"
end

f.resume  # печатает A, останавливается на yield
f.resume  # печатает B, завершается
```

Аргументы `Fiber.yield(...)` возвращаются из `resume`, а аргументы следующего `resume(...)` становятся результатом выражения `Fiber.yield` внутри fiber. Это позволяет строить кооперативные протоколы без общей памяти.

### Blocking I/O блокирует весь thread

Fiber переключается только в точках yield/transfer. Если внутри fiber вызвать блокирующую операцию, весь thread заблокируется:

```ruby
f1 = Fiber.new { sleep(2); puts "fiber 1 done" }
f2 = Fiber.new { puts "fiber 2 done" }

f1.resume  # Программа зависает на 2 секунды!
           # f2 не может выполниться, пока f1 спит
f2.resume  # Выполнится только после пробуждения f1
```

Для 10 000 соединений на одном потоке это делает "наивные" Fiber бесполезными: каждый `sleep` или `socket.read` замораживает весь поток.

### Fiber::Scheduler: перехват блокирующих операций

Ruby 3.0 ввёл интерфейс `Fiber::Scheduler` — объект, который устанавливается на текущий поток и перехватывает блокирующие вызовы:

```ruby
Fiber.set_scheduler(MyScheduler.new)
```

Когда Fiber внутри этого потока вызывает `sleep`, `IO#read` или другую блокирующую операцию, Ruby вместо реальной блокировки вызывает hook планировщика. Планировщик регистрирует ожидание в event loop ([мультиплексирование I/O](../../linux/programming/io-multiplexing.md)), уступает управление другому fiber, и когда событие произошло — возобновляет ожидавший fiber.

Минимальный контракт планировщика: методы `io_wait`, `kernel_sleep`, `block`, `unblock`. Реализация `io-event` (используемая в Falcon) работает поверх epoll/kqueue.

Fiber даёт дешёвую конкурентность для I/O, но не даёт CPU-параллелизма — GVL по-прежнему ограничивает выполнение одним потоком. Для CPU-bound задач нужен другой механизм.

## Ractor: CPU-параллелизм через изоляцию

### Зачем Ractor

MRI исторически строился вокруг GVL: внутри одного VM-контекста Ruby-код выполняется последовательно, и многим C-расширениям не нужна тонкая блокировка. Четыре CPU-bound потока на четырёх ядрах не дают ускорения — GVL пропускает по одному.

Ractor (Ruby 3.0+, экспериментальный) меняет точку компромисса: вместо того чтобы делать весь мир thread-safe, Ruby вводит изоляцию. Каждый Ractor — независимая единица исполнения со своим GVL. Потоки из разных Ractor выполняются параллельно — это даёт CPU-параллелизм.

Потоки внутри одного Ractor делят ractor-wide GVL и не могут исполнять Ruby-код параллельно друг с другом. CPU-bound Ruby-код распараллеливается через Ractor или Process, не через Thread внутри одного Ractor.

### Shareable vs unshareable

Если Ractor изолированы, как обмениваться данными? Ruby делит объекты на две категории. **Shareable** — безопасны для совместного использования: числа, замороженные строки/структуры, объекты `Ractor`. **Unshareable** — большинство обычных объектов: массивы, хеши, экземпляры пользовательских классов.

```ruby
Ractor.shareable?(obj)        # проверка
Ractor.make_shareable(obj)    # deep-freeze объекта
```

`Class` и `Module` всегда считаются shareable — определения классов общие для всех Ractor. Но на глобальное состояние класса наложены ограничения: class variables (`@@cv`) доступны только в main Ractor; class instance variables (`@iv`) в non-main Ractor доступны только для чтения shareable значений; константы должны ссылаться на shareable объекты.

```ruby
class C
  @@cv = 1
  @iv = 1
  GOOD = "good".freeze
  BAD  = "bad".dup
end

r = Ractor.new do
  class C
    begin
      p @iv
      p GOOD
      p @@cv
    rescue => e
      p [e.class, e.message]
    end

    begin
      @iv = 42
    rescue => e
      p [e.class, e.message]
    end

    begin
      p BAD
    rescue => e
      p [e.class, e.message]
    end
  end

  :done
end

if r.respond_to?(:value) # Ruby 4.0+
  r.value
else
  r.take                 # Ruby 3.0-3.4
end
```

### Порты и сообщения

> **Версии Ruby:** в Ruby 3.0-3.4 у Ractor два канала: входящий (`Ractor#send`/`Ractor.receive`) и исходящий (`Ractor.yield`/`Ractor#take`). В Ruby 4.0 `Ractor.yield`/`Ractor#take` удалены, добавлены `Ractor::Port`, `Ractor#default_port`, `Ractor#join` и `Ractor#value`.

У Ractor есть mailbox — очередь входящих сообщений. `send` кладёт сообщение в mailbox получателя, `Ractor.receive` читает из mailbox текущего Ractor.

`Ractor::Port` (Ruby 4.0+) — отдельный объект-очередь. Ключевое правило: получать (`port.receive`) и закрывать (`port.close`) может только Ractor-создатель; отправлять (`port.send`) может любой Ractor со ссылкой. Это паттерн MPSC (multi-producer / single-consumer). `Port#send` не блокирует отправителя, а `Port#receive` блокирует, если сообщений нет — backpressure нужно реализовывать протоколом.

Пример двусторонней связи через mailbox:

```ruby
main = Ractor.current

worker = Ractor.new(main) do |main|
  req = Ractor.receive        # читаем из mailbox worker
  main.send([:ok, req])       # пишем в mailbox main
  :done
end

worker.send("ping")
p Ractor.receive              # читаем из mailbox main

if worker.respond_to?(:value) # Ruby 4.0+
  worker.value
else
  worker.take                 # Ruby 3.0-3.4
end
```

Пример MPSC — много воркеров, один потребитель:

```ruby
results = Ractor.const_defined?(:Port) ? Ractor::Port.new : nil
main = Ractor.current

workers = 4.times.map do |i|
  if results
    Ractor.new(results, i) do |results, i|
      results << [:done, i, Process.pid]
      :done
    end
  else
    Ractor.new(main, i) do |main, i|
      main.send([:done, i, Process.pid])
      :done
    end
  end
end

4.times do
  msg = results ? results.receive : Ractor.receive
  p msg
end

workers.each do |w|
  if w.respond_to?(:value)
    w.value
  else
    w.take
  end
end
```

### Copy vs move

При отправке shareable объекта передаётся ссылка (дёшево). При отправке unshareable объекта Ruby сохраняет гарантию «в один момент доступен только в одном Ractor»: **copy** (по умолчанию) — глубокое копирование, может быть дорого для больших графов объектов; **move** — передача владения, отправитель теряет доступ к объекту.

Стоимость сообщений определяется типом данных: immutable/shareable передаются как ссылка, unshareable — копируются или перемещаются. Для горячих путей стоит проектировать протокол так, чтобы передавались shareable объекты.

Ractor даёт CPU-параллелизм, но API экспериментальный и требует дисциплины в проектировании обмена данными. На практике серверные приложения чаще используют комбинацию процессов, потоков и Fiber — через веб-серверы.

## Серверы и background jobs

### Puma: reactor + thread pool

Puma использует гибридную архитектуру в clustered mode — три уровня конкурентности:

```text
                    +------------------------------------------+
                    |            Master Process                |
                    |  - не обрабатывает запросы               |
                    |  - roles: spawn workers, reap dead       |
                    +-------------------+----------------------+
                                        | fork()
              +-------------------------+-------------------------+
              v                         v                         v
    +-----------------+       +-----------------+       +-----------------+
    |    Worker 0     |       |    Worker 1     |       |    Worker 2     |
    |   (процесс)     |       |   (процесс)     |       |   (процесс)     |
    |                 |       |                 |       |                 |
    |  +--Reactor--+  |       |  +--Reactor--+  |       |  +--Reactor--+  |
    |  |  Thread   |  |       |  |  Thread   |  |       |  |  Thread   |  |
    |  +-----+-----+  |       |  +-----+-----+  |       |  +-----+-----+  |
    |        |        |       |        |        |       |        |        |
    |        v        |       |        v        |       |        v        |
    |  +--Thread---+  |       |  +--Thread---+  |       |  +--Thread---+  |
    |  |   Pool    |  |       |  |   Pool    |  |       |  |   Pool    |  |
    |  | 5 threads |  |       |  | 5 threads |  |       |  | 5 threads |  |
    |  +-----------+  |       |  +-----------+  |       |  +-----------+  |
    |                 |       |                 |       |                 |
    |  свой GVL       |       |  свой GVL       |       |  свой GVL       |
    +-----------------+       +-----------------+       +-----------------+
```

**Workers (процессы)** дают настоящий CPU-параллелизм — каждый со своим GVL. **Reactor thread** использует nio4r (обёртка над epoll/kqueue) для [мультиплексирования I/O](../../linux/programming/io-multiplexing.md): принимает TCP-соединения, читает HTTP-запросы (включая медленных клиентов на 3G), парсит заголовки. **Thread pool** выполняет Ruby-код приложения — `app.call(env)`.

Reactor защищает thread pool от slow clients. Без reactor каждый поток был бы занят 10 секунд на медленного клиента (5 сек чтение + 50 мс Rails + 5 сек запись). С reactor поток занят только на время обработки:

```text
Без Reactor:
Thread: [accept]--[read 5 sec]--[Rails 50ms]--[write 5 sec]
        ^------- thread занят ~10 секунд ----------------^

С Reactor:
Reactor: [accept]--[ждём в epoll]--[read готов]--> Thread Pool
Thread:  --------------------------------[Rails 50ms]--[write]
                                         ^--- thread свободен --^
```

Конфигурация Puma:

```ruby
# config/puma.rb
workers ENV.fetch("WEB_CONCURRENCY") { 2 }  # процессы ~ CPU cores

threads_count = ENV.fetch("RAILS_MAX_THREADS") { 5 }
threads threads_count, threads_count          # потоки для I/O конкурентности

preload_app!  # загрузить приложение ДО fork -> экономия памяти через CoW

on_worker_boot do
  ActiveRecord::Base.establish_connection     # свежий connection pool
end
```

Workers примерно равны количеству ядер — больше приводит к переключениям контекста, меньше оставляет ядра простаивающими. Threads — не про CPU-параллелизм (GVL не даёт), а про I/O-конкурентность: пока один поток ждёт PostgreSQL, другой выполняет код. `pool` в `database.yml` должен быть >= `threads per worker`, иначе потоки будут ждать соединений.

Puma подходит для стандартных Rails-приложений с blocking I/O гемами. Ограничение: потоки всё ещё потребляют память (стек), а GVL не даёт параллелить Ruby-код внутри одного worker.

### Falcon: fiber scheduler

Falcon использует принципиально другой подход — один event loop с тысячами Fiber:

```text
+-------------------------------------------------------------------------+
|                             Falcon Process                              |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |                    Event Loop Thread                              |  |
|  |                                                                   |  |
|  |   +-------------------------------------------------------+       |  |
|  |   |              Fiber Scheduler                          |       |  |
|  |   |         (io-event: epoll/kqueue/select)               |       |  |
|  |   |                                                       |       |  |
|  |   |  Fiber 1: [Rails code]--yield--[Rails code]           |       |  |
|  |   |  Fiber 2: ------[waiting I/O]------[Rails code]       |       |  |
|  |   |  Fiber 3: [Rails code]--[waiting I/O]-------          |       |  |
|  |   |  ...                                                  |       |  |
|  |   |  Fiber N: --------[waiting I/O]-----------            |       |  |
|  |   +-------------------------------------------------------+       |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

Стек Falcon:

```text
+--------------------------------------+
|              Falcon                  |  <-- HTTP-сервер
+--------------------------------------+
|         async / async-http           |  <-- async runtime
+--------------------------------------+
|            io-event                  |  <-- Fiber Scheduler implementation
+--------------------------------------+
|  epoll (Linux) / kqueue (macOS/BSD)  |  <-- системный механизм
|  select (fallback)                   |
+--------------------------------------+
```

Когда Fiber вызывает `socket.read`, Fiber Scheduler перехватывает вызов, регистрирует сокет в epoll/kqueue, уступает управление другому Fiber, и когда данные готовы — возобновляет ожидавший. Код приложения не меняется — тот же `socket.read`, но без блокировки потока.

| Аспект | Puma | Falcon |
|--------|------|--------|
| Модель конкурентности | Процессы + Threads | Fibers на одном потоке |
| I/O мультиплексирование | nio4r (Reactor thread) | io-event (Fiber Scheduler) |
| Память на соединение | выше (threads) | ниже (fibers) |
| CPU параллелизм | Workers (процессы) | Несколько процессов (опционально) |
| GVL impact | Thread pool ограничен GVL | Один поток, GVL не мешает |
| Совместимость с гемами | Высокая (blocking I/O OK) | Требует async-совместимых гемов |
| Зрелость | Production-ready, широко используется | Менее распространён |

Falcon выигрывает при массе одновременных соединений (WebSockets, SSE, long polling) и I/O-intensive нагрузке. Ограничение — нужна async-совместимая экосистема гемов.

### Sidekiq: фоновые задачи

[Sidekiq](../../rails/sidekiq/architecture.md) использует процессы и потоки: каждый Sidekiq-процесс забирает задачи из Redis и выполняет их в thread pool. CPU-параллелизм достигается запуском нескольких процессов (каждый со своим GVL). Потоки внутри процесса перекрывают I/O-ожидание — та же модель, что в Puma, но для background jobs вместо HTTP-запросов. Подробнее о concurrency-модели — [concurrency и масштабирование Sidekiq](../../rails/sidekiq/concurrency-and-scaling.md).

## JRuby и TruffleRuby: мир без GVL

JRuby и TruffleRuby не имеют глобальной блокировки — потоки выполняют Ruby-код параллельно на разных ядрах.

**JRuby** компилирует Ruby в байткод JVM. Ruby Thread — это Java thread. Внутренние структуры интерпретатора (method tables, constant tables, require/autoload) защищены отдельными локами, а не одним глобальным. Пользовательские `Array` и `Hash` не защищены — это осознанный выбор: блокировка на каждый контейнер замедлила бы однопоточный код.

**TruffleRuby** тоже выполняет Ruby-код параллельно. Есть native- и JVM-режимы запуска: native обычно стартует быстрее, JVM чаще выигрывает на длинных прогретых нагрузках. Но отсутствие GVL не делает обычные `Array` и `Hash` автоматически безопасными для общего мутируемого состояния: как и в JRuby, здесь нужно явно проектировать синхронизацию.

Отсутствие GVL означает: race conditions — не теоретическая, а практическая проблема. Код, который "работает" в MRI из-за сериализации через GVL, может ломаться в JRuby/TruffleRuby:

```ruby
# "Работает" в MRI, гонка в JRuby/TruffleRuby
array = []
10.times.map do
  Thread.new { 1000.times { array << 1 } }
end.each(&:join)

array.size  # MRI часто 10000; на JRuby/TruffleRuby результат недетерминирован.
```

Видимость памяти — ещё одна реальная проблема без GVL. Паттерн "data + ready flag" без синхронизации не работает: один поток может записать `@data = 42` и `@ready = true`, а другой увидеть `@ready == true` с устаревшим `@data`. В MRI GVL обеспечивает happens-before через барьеры; в JRuby/TruffleRuby нужна явная синхронизация. Подробности о том, почему x86 часто "прощает" такие ошибки, а ARM — нет, в [модели памяти](../../linux/concurrency/memory-ordering.md).

**concurrent-ruby** — гем, дающий одинаковое поведение на всех реализациях:

```ruby
require 'concurrent'

map = Concurrent::Map.new                          # thread-safe коллекция
ref = Concurrent::AtomicReference.new(initial)     # атомарная ссылка
ref.compare_and_set(old_value, new_value)          # CAS
```

| Что | MRI (GVL) | JRuby | TruffleRuby |
|-----|-----------|-------|-------------|
| Интерпретатор защищён? | GVL | механизмы JVM | механизмы Truffle |
| Ruby-код в Thread параллелен? | нет (внутри ractor) | да | да |
| Shared mutable state без синхронизации | гонка | гонка | гонка |

Переносимое правило: shared mutable state между потоками без синхронизации — ошибка на любой реализации. В MRI она маскируется сериализацией через GVL, в JRuby/TruffleRuby — проявляется сразу.

## Когда что использовать

| Инструмент | Даёт | Цена |
| --- | --- | --- |
| `Process` | параллелизм + сильная изоляция | IPC, память, стоимость границ |
| `Ractor` | параллелизм Ruby-кода + изоляция объектов | протокол сообщений, shareable/copy/move, экспериментальный API |
| `Thread` | конкурентность в одном процессе | shared-state протоколы, GVL для Ruby CPU в MRI |
| `Fiber` | дешёвые кооперативные задачи | нужен scheduler для I/O, риск starvation |

Три правила выбора:

- В MRI `Thread` не даёт параллелизма Ruby-кода внутри одного Ractor: потоки по очереди держат GVL. Смысл потоков — в I/O-ожидании и блокирующих внешних вызовах, где GVL отпускается.
- `Fiber` перекрывает ожидание только там, где runtime/библиотека умеют отдавать управление scheduler. Блокирующий вызов без интеграции со scheduler блокирует весь thread.
- CPU-параллелизм для Ruby-кода в MRI достигается через `Process` или `Ractor` — между ними разница в изоляции и цене обмена данными.

## Sources

- Ruby 4.0.0 release announcement (2025-12-25): https://www.ruby-lang.org/en/news/2025/12/25/ruby-4-0-0-released/
- Ruby 4.0.0 NEWS (Ractor changes): https://docs.ruby-lang.org/en/4.0/NEWS/NEWS-4_0_0_md.html
- Ruby 3.3.0 NEWS (M:N thread scheduler, `RUBY_MN_THREADS`, `RUBY_MAX_CPU`): https://docs.ruby-lang.org/en/3.3/NEWS/NEWS-3_3_0_md.html
- Ruby feature #20861 (`RUBY_THREAD_TIMESLICE`): https://bugs.ruby-lang.org/issues/20861
- Ruby manpage env vars (`RUBY_THREAD_TIMESLICE`, `RUBY_MN_THREADS`, `RUBY_MAX_CPU`): https://github.com/ruby/ruby/blob/master/man/ruby.1
- Ruby internal concurrency (timer thread, interrupts): https://docs.ruby-lang.org/en/master/contributing/concurrency_guide_md.html
- Ruby docs: `Thread#native_thread_id`: https://docs.ruby-lang.org/en/4.0/Thread.html#method-i-native_thread_id
- Ruby docs: `Thread#status`: https://docs.ruby-lang.org/en/4.0/Thread.html#method-i-status
- Ruby docs: `Fiber` / `Fiber.schedule` / `Fiber::Scheduler`: https://docs.ruby-lang.org/en/master/Fiber.html, https://docs.ruby-lang.org/en/master/Fiber/Scheduler.html
- Ruby docs: default thread/fiber VM and machine stack sizes (`RUBY_THREAD_*_STACK_SIZE`, `RUBY_FIBER_*_STACK_SIZE`): https://docs.ruby-lang.org/en/3.3/NEWS/NEWS-2_0_0.html#label-RubyVM
- Ruby docs (Ruby 3.3): Ractor (legacy `yield`/`take`): https://docs.ruby-lang.org/en/3.3/ractor_md.html
- Ruby docs: `Ractor::Port`: https://docs.ruby-lang.org/en/4.0/Ractor/Port.html
- Ruby docs: Ractor (shareable objects, globals, class vars, constants): https://docs.ruby-lang.org/en/4.0/Ractor.html
- Ruby language: Ractor semantics (class vars, constants, class ivars): https://docs.ruby-lang.org/en/4.0/language/ractor_md.html
- CRuby source: `thread.c` (quantum, `RUBY_THREAD_TIMESLICE`, timer interrupts): https://github.com/ruby/ruby/blob/master/thread.c
- CRuby source: `thread_pthread_mn.c` / `thread_pthread.c` (timer thread polling, waking, `RUBY_VM_SET_TIMER_INTERRUPT`): https://github.com/ruby/ruby/blob/master/thread_pthread_mn.c, https://github.com/ruby/ruby/blob/master/thread_pthread.c
- concurrent-ruby (README, `concurrent-ruby-ext`): https://github.com/ruby-concurrency/concurrent-ruby
- TruffleRuby additions (`full_memory_barrier`, atomics): https://www.graalvm.org/22.0/reference-manual/ruby/TruffleRubyAdditions/index.html
- TruffleRuby runtime configurations (`--native`/`--jvm`): https://www.graalvm.org/22.0/reference-manual/ruby/
- io-event selectors (epoll/kqueue/select): https://github.com/socketry/io-event/blob/main/lib/io/event/selector/epoll.rb, https://github.com/socketry/io-event/blob/main/lib/io/event/selector/kqueue.rb, https://github.com/socketry/io-event/blob/main/lib/io/event/selector/select.rb
- Puma documentation: https://puma.io/
- Falcon documentation: https://socketry.github.io/falcon/
- Linux man-pages: `pthread_create(3)`: https://man7.org/linux/man-pages/man3/pthread_create.3.html
- Linux man-pages: `futex(2)`: https://man7.org/linux/man-pages/man2/futex.2.html
- Linux man-pages: `read(2)`: https://man7.org/linux/man-pages/man2/read.2.html
- Linux man-pages: `sched(7)` (runnable vs sleeping): https://man7.org/linux/man-pages/man7/sched.7.html
