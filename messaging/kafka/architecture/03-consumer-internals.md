# Consumer internals: poll loop, offset commit, rebalancing

**Предпосылки:** [Producer reliability](02-producer-reliability.md) (idempotent producer, exactly-once per partition), [Broker, topic, partition, offset](00-what-is-kafka.md) (партиции, offset, consumer groups), [Гарантии доставки](../../../system-design/08-delivery-guarantees.md) (at-most-once, at-least-once), [Reliability patterns](../../../system-design/06-reliability-patterns.md) (idempotency), [Message Queues](../../../system-design/09-message-queues.md) (push vs pull, backpressure), [Redis Stream](../../../databases/redis/data-structures/05-stream.md) (XACK, PEL).

[Idempotent producer](02-producer-reliability.md) гарантирует exactly-once на стороне записи: дубликаты и переупорядочивание невозможны благодаря PID и sequence number. Но в границах idempotent producer'а осталась открытая проблема: consumer прочитал событие, обработал, упал до фиксации позиции чтения — рестартнул и прочитал то же событие снова. Гарантия на стороне записи не защищает от дубликатов на стороне чтения.

Группа `seller_read_db` читает `order_events` (6 партиций, 3 broker'а): Consumer A — партиции 0 и 1, Consumer B — 2 и 3, Consumer C — 4 и 5. 150 events/sec суммарно, ~50 на каждого. Как именно consumer забирает данные, как фиксирует прогресс, и что происходит, когда один из consumer'ов падает?

## Pull-модель: consumer забирает данные сам

Есть два способа доставить данные consumer'у. При [push-модели](../../../system-design/09-message-queues.md) broker сам отправляет события по мере поступления. Проблема — в скорости: broker отправляет с темпом producer'а. Если producer пишет 5 000 events/sec, а consumer способен обработать 500, broker заваливает consumer'а. Нужен механизм [backpressure](../../../system-design/09-message-queues.md) — consumer должен сообщить «притормози». Это усложняет протокол: broker отслеживает скорость каждого consumer'а, буферизирует, управляет потоком. [Redis Pub/Sub](../../../databases/redis/data-structures/08-pub-sub.md) работает по push-модели — если подписчик не успевает читать, Redis накапливает данные в output buffer'е и при превышении лимита отключает клиента.

При pull-модели consumer сам решает, когда и сколько забрать. Обработал предыдущий батч — запросил следующий. Медленный consumer реже запрашивает, быстрый — чаще. Backpressure бесплатен: consumer не запрашивает больше, чем может обработать.

Kafka использует pull. Consumer'ы в Kafka очень разные по скорости — `seller_read_db` обрабатывает быстро, ClickHouse может батчить записи раз в минуту — и при pull каждый работает в своём темпе без координации с broker'ом.

Обратная сторона pull — когда новых событий нет, consumer впустую опрашивает broker. Это busy polling: трата CPU и сети на пустые ответы. Kafka решает это **long polling**: если у broker'а нет новых записей, он **не отвечает сразу**, а держит запрос открытым до появления данных или до истечения таймаута. Параметр `fetch.max.wait.ms` (дефолт 500 ms) — сколько broker ждёт перед пустым ответом. Парный параметр `fetch.min.bytes` (дефолт 1 байт) — минимальный объём данных, который broker накапливает перед ответом. При `fetch.min.bytes=64KB` broker подождёт 64 KB новых записей (или `fetch.max.wait.ms`), и отправит большой батч. Это trade-off: больше `fetch.min.bytes` — выше throughput (меньше round-trip'ов), но выше latency (consumer ждёт, пока накопится).

## Poll loop

Pull-модель означает, что consumer сам инициирует чтение. В Kafka это реализовано через **poll loop** — бесконечный цикл вызовов `consumer.poll()`. Каждый `poll()` отправляет broker'у fetch-запрос: «дай записи из партиции X, начиная с offset Y». Broker находит позицию в логе, вычитывает батч и возвращает. Протокол тот же, что использует follower для [репликации](01-replication.md) — fetch с указанием offset'а.

```
while true
  records = consumer.poll(timeout: 500ms)

  for record in records
    update_seller_database(record)
  end
end
```

`consumer.poll()` — единственная точка взаимодействия с broker'ом. Consumer A читает партиции 0 и 1 — один `poll()` может вернуть записи из обеих.

```
Consumer A                              Broker 0 (leader p0, p1)
   │                                         │
   │── poll() ─── fetch(p0, offset=15) ────> │
   │              fetch(p1, offset=8)  ────> │
   │                                         │  нет новых данных
   │                                         │  ждёт до 500ms...
   │                                         │  ...появились записи в p0
   │<──────────── p0: records 15..22 ────────│
   │              p1: пусто                  │
   │                                         │
   │  обрабатывает records 15..22            │
   │                                         │
   │── poll() ─── fetch(p0, offset=23) ────> │
   │              fetch(p1, offset=8)  ────> │
```

## Offset commit

Consumer получил записи 15–22 из партиции 0, обработал, запрашивает следующие с offset 23. Но сам факт запроса `fetch(offset=23)` **не означает** подтверждение обработки. Fetch — это про чтение, а подтверждение — про обработку. Клиентская библиотека может делать prefetch: пока код обрабатывает текущий батч, библиотека уже запрашивает следующий. Если fetch = подтверждение, то записи 15–22 «подтверждены», хотя обработка не завершена.

Подтверждение в Kafka — отдельная операция, **offset commit** (фиксация смещения). Consumer отправляет broker'у запрос: «для группы `seller_read_db`, партиция 0, зафиксируй offset 23» — все записи до 22 включительно обработаны, следующее чтение начинать с 23. Слово «commit» здесь означает то же, что в транзакциях БД — зафиксировать результат, но фиксируется позиция чтения, а не запись данных.

Закоммиченные offset'ы записываются в **`__consumer_offsets`** — внутренний topic Kafka с 50 партициями по умолчанию, реплицируемый как любой другой. Запись в этом topic'е: (consumer group, partition) → offset. При перезапуске consumer спрашивает: «какой последний закоммиченный offset для `seller_read_db`, партиция 0?» — и получает ответ из `__consumer_offsets`.

Контраст с [Redis Streams](../../../databases/redis/data-structures/05-stream.md): XACK подтверждает конкретное сообщение по ID, PEL хранит список каждого неподтверждённого сообщения. В Kafka offset commit — одно число на партицию: «всё до этой позиции обработано». Нельзя подтвердить offset 20, пропустив 18. Это проще и дешевле: одно число вместо списка ID.

### Момент commit'а определяет семантику доставки

Consumer A получил записи 15–22, обработал до 19, упал. Что произойдёт — зависит от того, когда был commit.

**Commit до обработки** (сразу после получения записей). Закоммичен offset 23. Consumer перезапустился, прочитал из `__consumer_offsets`: 23. Начинает с 23. Записи 20–22 никогда не будут обработаны — seller read DB не узнает об этих заказах. Это [at-most-once](../../../system-design/08-delivery-guarantees.md): максимум одна обработка, но возможна потеря.

**Commit после обработки** (consumer собирался закоммитить после всего батча). В `__consumer_offsets` последний commit — 15. Consumer перезапустился, начинает с 15. Записи 15–19 обработаны повторно, но 20–22 не потеряны. Это [at-least-once](../../../system-design/08-delivery-guarantees.md): ни одна запись не потеряна, но возможны дубликаты.

Kafka поддерживает оба варианта — broker не знает и не контролирует, когда consumer коммитит offset. Commit отделён от fetch, и семантику доставки определяет сам consumer через момент вызова commit. Для сценариев, где потеря допустима (метрики, логи), at-most-once с commit до обработки — осознанный выбор: проще, без дубликатов, ценой возможной потери.

```
Батч: записи 15─16─17─18─19─20─21─22

Commit до обработки:
  commit(23) → обработал 15..19 → CRASH
  restart → читает с 23 → записи 20,21,22 потеряны
  = at-most-once

Commit после обработки:
  обработал 15..19 → CRASH → commit не случился
  restart → читает с 15 → записи 15..19 обработаны дважды
  = at-least-once
```

Для `order_events` с платёжными данными потеря неприемлема — значит, commit после обработки и at-least-once. Но при at-least-once записи 15–19 будут обработаны повторно. Если обработчик [идемпотентен](../../../system-design/06-reliability-patterns.md) — `UPDATE orders SET status = 'paid' WHERE id = 42` выполни хоть десять раз, результат один — дубликаты безвредны. Комбинация at-least-once доставки и идемпотентной обработки — это [exactly-once обработка](../../../system-design/08-delivery-guarantees.md): ни одно событие не потеряно и ни одно не вызывает побочный эффект дважды. [Idempotent producer](02-producer-reliability.md) даёт exactly-once на стороне записи, идемпотентный обработчик — на стороне чтения.

## Auto-commit и manual commit

Итак, commit после обработки — единственный безопасный вариант для `order_events`. Но кто вызывает commit и когда?

**Auto-commit** — дефолтное поведение (`enable.auto.commit=true`). Клиентская библиотека автоматически коммитит offset'ы в фоне каждые `auto.commit.interval.ms` (дефолт 5 секунд). Каждый вызов `poll()` проверяет, прошло ли 5 секунд с последнего commit'а, и если да — коммитит offset'ы предыдущего батча перед запросом новых данных.

Это просто, но контроль над моментом commit'а отсутствует. Если обработка одного батча занимает больше 5 секунд, auto-commit может сработать до завершения обработки — записи «подтверждены», но не обработаны. При crash'е они потеряны: at-most-once.

**Manual commit** — `enable.auto.commit=false`. Consumer сам решает, когда коммитить. Два варианта: **`commitSync()`** отправляет commit и блокирует до подтверждения от broker'а — надёжно, но каждый commit добавляет round-trip (~5–10 ms). **`commitAsync()`** отправляет commit и продолжает работу без ожидания — быстрее, но при ошибке commit'а (сеть, timeout) consumer узнает об этом не сразу.

```
while true
  records = consumer.poll(timeout: 500ms)

  records.each { |record| update_seller_database(record) }

  consumer.commit_sync   # commit только после полной обработки
end
```

Частота commit'ов — trade-off между overhead'ом и размером окна повторов при crash'е. Commit после каждого батча: при crash'е перечитается максимум один батч. Commit после каждой записи: перечитается максимум одна запись, но при 150 events/sec это 150 commit'ов в секунду, каждый ~5–10 ms. Commit раз в N записей — компромисс.

При жёстком crash'е (OOM kill, `kill -9`) ни один вариант не даёт ноль повторов: процесс мёртв мгновенно, никакой cleanup. Окно повторов = всё, что обработано с момента последнего commit'а. При auto-commit с `auto.commit.interval.ms=5000` — до 5 секунд данных. При 150 events/sec на этого consumer'а — до 750 записей.

## Liveness detection: heartbeat и max.poll.interval

Consumer B получил OOM kill. Партиции 2 и 3 осиротели — события пишутся (producer'у всё равно, кто читает), но никто не обрабатывает. Продавцы не видят 33% заказов. Kafka должна обнаружить, что Consumer B мёртв, и передать его партиции выжившим. Но сначала — как Kafka узнаёт, что consumer жив?

Consumer периодически отправляет **heartbeat** — короткое сообщение «я жив» — специальному broker'у, **group coordinator**. Group coordinator — это не то же, что [controller](01-replication.md). Controller — один на весь кластер, управляет метаданными: какие broker'ы живы, кто leader каждой партиции. Group coordinator — один на каждую consumer group, управляет consumer'ами: кто в группе, жив ли, кому какие партиции. Coordinator для группы `seller_read_db` определяется хешем имени группы по партициям `__consumer_offsets` — какой broker является leader'ом нужной партиции, тот и coordinator.

Два параметра liveness:

**`heartbeat.interval.ms`** (дефолт 3 секунды) — как часто consumer отправляет heartbeat. Heartbeat ходит в отдельном фоновом потоке.

**`session.timeout.ms`** (дефолт 45 секунд; до Kafka 3.0 было 10 секунд) — если coordinator не получил heartbeat за это время, считает consumer мёртвым и запускает перераспределение партиций. 45 секунд — долго, но heartbeat может задержаться по легитимным причинам: GC-пауза JVM, всплеск нагрузки, сетевой hiccup. Слишком короткий `session.timeout.ms` — ложные срабатывания: consumer жив, просто задержался, а Kafka уже запустила перераспределение.

Есть второй механизм: **`max.poll.interval.ms`** (дефолт 5 минут) — максимальное время между двумя вызовами `poll()`. Если consumer вызвал `poll()`, получил батч и ушёл обрабатывать его 6 минут — coordinator считает consumer зависшим. Зачем два таймаута? Heartbeat ходит в фоновом потоке, `poll()` — в основном. Consumer может зависнуть в бизнес-логике (deadlock, бесконечный цикл, медленный запрос к БД), heartbeat-поток продолжает работать — coordinator думает, что всё нормально. `max.poll.interval.ms` ловит именно этот случай.

```
Consumer B                         Group Coordinator
   │                                       │
   │── heartbeat (каждые 3 сек) ─────────> │  "Consumer B жив"
   │── heartbeat ────────────────────────> │
   │                                       │
   │   OOM kill                            │
   │                                       │
   │   (нет heartbeat 45 секунд)           │
   │                                       │  "Consumer B мёртв"
   │                                       │  → запускает rebalancing
```

## Rebalancing: перераспределение партиций

Coordinator решил, что Consumer B мёртв. Партиции 2 и 3 нужно передать выжившим. Процесс перераспределения партиций между consumer'ами в группе называется **rebalancing**.

Rebalancing запускается не только при смерти consumer'а. Полный список триггеров: consumer вышел из группы (crash, session timeout, превышение `max.poll.interval.ms`, graceful shutdown), новый consumer присоединился (deploy нового инстанса), добавлены партиции в topic (Kafka не позволяет *уменьшить* количество партиций — `hash(key) % N` сломал бы маршрутизацию), подписка изменилась (группа подписана на regex, появился новый topic).

### Eager protocol

Базовый протокол rebalancing (единственный до Kafka 2.4) работает как stop-the-world:

**Шаг 1.** Coordinator уведомляет всех живых consumer'ов — через ответ на очередной heartbeat.

**Шаг 2.** Все consumer'ы останавливают обработку и отдают **все** свои партиции. Не только партиции мёртвого B — живые A и C тоже. Consumer A прекращает читать партиции 0 и 1, Consumer C — 4 и 5. Перед отдачей каждый коммитит текущие offset'ы.

**Шаг 3.** Один из consumer'ов назначается **group leader** (не путать с partition leader — это роль внутри consumer group). Group leader получает список живых consumer'ов и список партиций, вычисляет assignment и отправляет результат coordinator'у. Почему assignment вычисляет consumer, а не coordinator (broker)? Стратегия распределения может зависеть от приложения. Если бы логику вынесли в broker — каждую новую стратегию пришлось бы деплоить на стороне кластера. Вместо этого стратегия живёт в клиентской библиотеке, broker остаётся простым координатором.

**Шаг 4.** Каждый consumer получает новое назначение и возобновляет работу.

```
До:    A → [p0, p1]    B → [p2, p3]    C → [p4, p5]
                              ↓
                        Consumer B мёртв
                              ↓
Шаг 2: A отдаёт [p0, p1], C отдаёт [p4, p5]
       ────── никто ничего не обрабатывает ──────
Шаг 3: group leader распределяет 6 партиций на 2 consumer'а
                              ↓
После: A → [p0, p1, p2]    C → [p3, p4, p5]
```

На время rebalancing **вся группа** `seller_read_db` не обрабатывает ни одного события. Для 6 партиций и 3 consumer'ов — несколько секунд. Для 200 партиций и 50 consumer'ов — до минуты.

Самый коварный триггер на практике — ненамеренный rebalancing при деплое. Rolling deploy: поднимаем новый инстанс → rebalancing. Гасим старый → ещё один rebalancing. Три инстанса, rolling deploy — три-четыре rebalancing'а подряд. Каждый — stop-the-world. Это **rebalancing storm**.

### onPartitionsRevoked: единственный шанс закоммитить

Сигнал о rebalancing приходит через heartbeat-поток, но фактическая реакция происходит при следующем вызове `poll()`. Внутри `poll()`, прежде чем запрашивать новые данные, библиотека вызывает callback **`onPartitionsRevoked`** — «у тебя отбирают партиции». Это единственный момент, когда consumer может закоммитить обработанные offset'ы, закрыть соединения и сбросить буферы. После возврата из callback'а партиции уже не его.

```
consumer.subscribe("order_events", listener: {
  on_partitions_revoked: -> (partitions) {
    consumer.commit_sync   # закоммитить всё обработанное
  },
  on_partitions_assigned: -> (partitions) {
    # инициализировать ресурсы для новых партиций
  }
})
```

Если consumer не реализует `onPartitionsRevoked` — библиотека сделает auto-commit (если включён). Если auto-commit выключен и callback не реализован — offset'ы не закоммичены, новый владелец партиции начнёт с последнего известного commit'а, перечитает больше. При жёстком crash'е (OOM kill) callback не вызывается — процесс мёртв, cleanup невозможен.

### Assignment strategies

Group leader вычисляет распределение партиций. Как именно — определяет стратегия (`partition.assignment.strategy`).

**RangeAssignor** (дефолт до Kafka 3.0) работает per topic: берёт партиции одного topic'а, сортирует consumer'ов по имени, делит поровну с остатком. Проблема — остаток всегда достаётся первому consumer'у по алфавиту. При 5 topic'ах с нечётным числом партиций перекос накапливается: один consumer перегружен.

**RoundRobinAssignor** берёт все партиции всех topic'ов, сортирует глобально, раздаёт по кругу. Распределение ровнее, потому что остатки от разных topic'ов не всегда попадают одному consumer'у.

**StickyAssignor** добавляет цель: минимизировать перемещения при rebalancing. Если Consumer A читал p0 и p1 до rebalancing — по возможности оставить их за ним. Меньше перемещений — меньше партиций, для которых нужно сбрасывать локальные кэши и переоткрывать соединения к БД. Но StickyAssignor по-прежнему работает внутри eager protocol — все consumer'ы отдают все партиции, потом получают обратно (большинство — те же). Stop-the-world сохраняется.

### Cooperative rebalancing

Eager protocol отбирает все партиции у всех consumer'ов. Кажется избыточным: Consumer B умер, его партиции нужно отдать — зачем отбирать p0 и p1 у Consumer A? Eager protocol разрабатывался как первая версия (Kafka 0.9, 2015) и решает задачу грубо, но безопасно: при любом изменении — пересчёт с нуля. Не нужно вычислять diff, не нужно координировать частичные передачи. Дополнительная защита: если coordinator считает consumer мёртвым, а тот на самом деле жив (GC-пауза) — при eager protocol все отдают всё, и «воскресший» consumer обнаружит свои партиции revoked.

**CooperativeStickyAssignor** (Kafka 2.4+, дефолт с Kafka 3.0) делает rebalancing в два шага:

**Шаг 1 — revoke only.** Group leader вычисляет, какие партиции нужно переместить. Consumer'ы, у которых отбирают партиции, отдают **только их**. Остальные — продолжают обрабатывать.

**Шаг 2 — assign.** Второй короткий rebalancing: перемещённые партиции назначаются новым владельцам.

```
Eager protocol:
  t=0   rebalancing
  t=0   ВСЕ consumer'ы остановились, отдали ВСЕ партиции
        ──── тишина: никто ничего не обрабатывает ────
  t=3s  новое назначение, все возобновили работу

Cooperative protocol:
  t=0     rebalancing
  t=0     Consumer A продолжает читать p0, p1
          Consumer C продолжает читать p4, p5
          p2, p3 — ничьи (Consumer B мёртв)
  t=0.5s  p2 → Consumer A, p3 → Consumer C
```

Consumer A и Consumer C ни на секунду не прекращают обработку своих партиций. Пауза — только для p2 и p3, пока они передаются от мёртвого B к новым владельцам. При rolling deploy с cooperative protocol каждый раз перемещаются только партиции уходящего/приходящего consumer'а — rebalancing storm исчезает.

## Sources

- Narkhede, Shapira, Palino, 2017, *Kafka: The Definitive Guide*. O'Reilly
- Apache Kafka Documentation. <https://kafka.apache.org/documentation/>
