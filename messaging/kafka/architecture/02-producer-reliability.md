# Producer reliability: retries, ordering, idempotent producer

**Предпосылки:** [Репликация](01-replication.md) (acks, ISR, high watermark), [Broker, topic, partition, offset](00-what-is-kafka.md) (партиции, offset, partition key), [Reliability patterns](../../../system-design/06-reliability-patterns.md) (idempotency, retry), [Гарантии доставки](../../../system-design/08-delivery-guarantees.md) (at-most-once, at-least-once, exactly-once), [Message Queues](../../../system-design/09-message-queues.md) (ACK, log-based брокер).

Кластер из трёх broker'ов с `replication.factor=3`, `acks=all`, `min.insync.replicas=2` обеспечивает durability для `order_events`. Producer отправляет событие, leader ждёт подтверждения от всех ISR-реплик и только тогда отвечает «ok». Данные переживают смерть одного broker'а.

Но мы смотрели на это со стороны кластера. Теперь — со стороны producer'а.

## Потерянный ответ

Orders-сервис обработал платёж за заказ #42 и публикует `order_paid` в `order_events`. Producer отправляет событие с `acks=all`. Leader на Broker 0 записывает, follower'ы на Broker 1 и Broker 2 забирают через fetch, все ISR-реплики подтвердили. Leader формирует ответ «ok» — и в этот момент сетевое соединение между producer'ом и Broker 0 обрывается. Ответ не доходит. Producer ждёт — timeout.

```
Producer                          Leader (Broker 0)
   │                                   │
   │── event: order_paid #42 ────────> │
   │                                   │ записал в лог
   │                                   │ follower'ы скопировали
   │                                   │ готов ответить "ok"
   │          ╳ сеть оборвалась ╳      │
   │                                   │── "ok" ──╳ потерялось
   │  ... timeout ...                  │
   │                                   │
   │  Что делать?                      │
```

Событие **записано** — на трёх broker'ах, committed, consumer'ы его увидят. Но producer об этом не знает. С его точки зрения запись могла не пройти: timeout мог случиться до того, как leader получил событие, или после получения, но до репликации. Producer не может отличить «записано, ответ потерялся» от «не записано вообще».

Два варианта. Не повторять отправку — событие `order_paid` потенциально потеряно. Seller read DB не обновится, fraud detection не увидит платёж. Это [at-most-once](../../../system-design/08-delivery-guarantees.md): максимум одна доставка, но без гарантии, что она произошла. Повторить отправку — событие `order_paid` может оказаться в партиции дважды. Consumer обработает оплату два раза: двойное списание, дублирование в ClickHouse, ложный сигнал fraud detection. Это [at-least-once](../../../system-design/08-delivery-guarantees.md): хотя бы одна доставка, но возможны дубликаты.

Для `order_events` с платёжными данными потеря неприемлема — значит, retry. Но retry создаёт дубликаты. И не только дубликаты.

## Retry в Kafka producer

Producer не отправляет событие и ждёт вечно. Три параметра управляют повторами:

**`retries`** — сколько раз повторить отправку при ошибке. В старых версиях Kafka (до 2.1) дефолт был 0 — ни одного повтора. С Kafka 2.1 дефолт — `Integer.MAX_VALUE` (~2 миллиарда), фактически бесконечно.

**`delivery.timeout.ms`** — общий бюджет времени на отправку, включая все retry. Дефолт — 120 000 ms (2 минуты). Producer повторяет попытки в пределах этих двух минут, после чего возвращает ошибку приложению.

**`retry.backoff.ms`** — пауза между повторами (дефолт 100 ms), чтобы не забивать сеть.

В нашем сценарии: timeout на первую попытку — producer автоматически шлёт `order_paid #42` повторно. Если Broker 0 снова недоступен — ещё раз. И ещё. До «ok» или до истечения `delivery.timeout.ms`.

Но producer не отправляет события по одному, дожидаясь ответа на каждое. Он работает **асинхронно**: отправил событие A, не дожидаясь ответа — отправляет B, потом C. Это контролирует параметр **`max.in.flight.requests.per.connection`** — сколько неподтверждённых запросов producer держит одновременно на одном соединении с broker'ом. Дефолт — 5.

```
Producer                              Leader (Broker 0)
   │                                       │
   │── request 1: order_paid #42 ────────> │
   │── request 2: order_shipped #77 ─────> │
   │── request 3: order_created #99 ─────> │
   │                                       │
   │   (3 in-flight, ждём ответов)         │
```

Три запроса в полёте одновременно. Все идут в одну партицию (хеши ключей совпали). Request 1 **падает с ошибкой** — timeout, leader temporarily unavailable. Requests 2 и 3 **успешно записаны**. Producer ставит request 1 на retry.

```
Партиция 3 после записи requests 2 и 3:

offset:  ... 10       11
             [#77     [#99
              ship]    crtd]

Producer retries request 1:

offset:  ... 10       11       12
             [#77     [#99     [#42     ← retry
              ship]    crtd]    paid]
```

Producer отправил события в порядке: #42 paid → #77 shipped → #99 created. В партиции порядок стал: #77 shipped → #99 created → #42 paid. Retry переупорядочил записи.

Для разных заказов (#42, #77, #99) это не страшно — они независимы. Но при двух событиях одного заказа подряд — `order_created #42` (request 1) и `order_paid #42` (request 2) — request 1 упал, request 2 записан, retry request 1 записан после. В партиции: `paid` раньше `created`. Consumer обработает оплату раньше создания заказа.

Retry порождает две проблемы: дубликаты и нарушение порядка.

## max.in.flight=1: наивное решение

`max.in.flight.requests.per.connection=1` — один запрос за раз. Отправил — жди ответа — только потом следующий. Retry не может обогнать ничего, потому что ничего другого в полёте нет. Порядок гарантирован.

Цена — throughput. Вместо 5 запросов в полёте — один. Producer простаивает, ожидая каждый round-trip (~5–30 ms при `acks=all`). Для наших 150 events/sec это может быть терпимо, но при тысячах events/sec — bottleneck.

## Idempotent producer

Kafka решает обе проблемы — дубликаты и переупорядочивание — одним механизмом. Включается параметром `enable.idempotence=true` (дефолт с Kafka 3.0).

При первом подключении к кластеру producer получает от broker'а уникальный числовой идентификатор — **Producer ID (PID)**. PID назначается кластером, не приложением (это не partition key и не client.id).

Далее producer для каждой партиции, в которую пишет, ведёт **sequence number** — монотонно возрастающий счётчик, начиная с 0. Каждый запрос к партиции содержит PID, sequence number и данные.

```
Producer (PID=7)
   │
   │── request: PID=7, seq=0, event: order_created #42 ──> Broker
   │── request: PID=7, seq=1, event: order_paid #42    ──> Broker
   │── request: PID=7, seq=2, event: order_shipped #42 ──> Broker
```

Broker хранит для каждой комбинации (PID, partition) **последний принятый sequence number** и проверяет каждый входящий запрос:

**seq == last + 1** — нормальный ход. Запись принята.

**seq ≤ last** — дубликат. Broker уже видел этот sequence number от этого producer'а в эту партицию. Запись **отклоняется без ошибки**: broker возвращает «ok», но ничего не записывает. Producer думает, что retry удался, а запись уже была на месте.

**seq > last + 1** — пропуск. Запросы пришли не по порядку: seq=3 пришёл раньше seq=2. Broker возвращает **OutOfOrderSequenceException** и **не производит запись**.

```
Broker (partition 3), хранит: PID=7 → last_seq=1

Приходит: PID=7, seq=2 → last+1=2 ✓ → записал, last_seq=2
Приходит: PID=7, seq=2 → дубликат    → "ok", не записал
Приходит: PID=7, seq=4 → пропуск     → OutOfOrderSequenceException
```

### Сохранение порядка при max.in.flight > 1

Вернёмся к сценарию с переупорядочиванием. Три запроса в полёте (`max.in.flight=5`): request 1 (seq=0), request 2 (seq=1), request 3 (seq=2). Request 1 упал. Broker получает request 2 (seq=1), но last_seq = -1. seq=1 ≠ last+1=0 — пропуск. Broker не примет request 2, пока не получит seq=0.

Producer-клиент (библиотека) получает `OutOfOrderSequenceException` и переотправляет батчи в правильном порядке. Когда retry request 1 приходит с seq=0 — broker записывает его первым, затем seq=1, затем seq=2. Порядок сохранён.

```
С idempotent producer, max.in.flight=5:

Producer отправил:  seq=0 (fail), seq=1, seq=2
Broker видит seq=1, но last=-1 → ждёт seq=0
Retry seq=0 приходит → записал seq=0, затем seq=1, затем seq=2

Результат в партиции:
offset: ... 10      11      12
            [#42    [#42    [#99
             crtd]   paid]   crtd]
            seq=0   seq=1   seq=2

Порядок = порядок отправки producer'ом ✓
```

Один механизм — sequence number на стороне broker'а — решает обе проблемы. Дубликаты отклоняются (seq уже видели), переупорядочивание невозможно (пропуски не принимаются). При этом `max.in.flight` может быть до 5 — throughput не страдает.

### Почему max.in.flight ограничен пятью

При пропуске в sequence number'ах broker буферизирует запросы с более высоким seq в памяти, ожидая пропущенный. При `max.in.flight=5` — максимум 4 запроса в буфере на каждую комбинацию (PID, partition). При `max.in.flight=100` — до 99 запросов. Умножить на тысячи producer'ов и десятки партиций — серьёзный расход памяти broker'а. Пять — эмпирический компромисс: достаточно для высокого throughput (5 запросов в полёте покрывают latency pipeline'а), и буфер на broker'е остаётся маленьким.

## Границы idempotent producer

Idempotent producer гарантирует **exactly-once на уровне транспорта** — retry одного и того же `send()` не создаст дубликат. Scope: одна партиция, один экземпляр producer'а. Sequence number привязан к паре (PID, partition). За этими рамками — четыре класса проблем, которые idempotent producer не решает.

**Дубликаты на уровне приложения.** Broker дедуплицирует по (PID, partition, sequence number), а не по содержимому. Каждый вызов `send()` получает новый sequence number — два вызова `send()` для одного бизнес-события становятся двумя валидными запросами с разными seq, и broker запишет оба.

Перезапуск — один из сценариев, где это проявляется. Orders-сервис использует outbox-таблицу в PostgreSQL: записал событие `order_paid #42` в outbox, вызвал `send()`, Kafka записала, но сервис упал до `UPDATE outbox SET sent = true`. Рестартнул, прочитал outbox — запись не помечена. Создал нового producer'а (PID=12), вызвал `send()` для того же события. Broker видит PID=12, seq=0 — новый producer, новый sequence number, записывает. Дубликат. Но и без рестарта: если приложение по какой-то логике вызывает `send()` дважды для одного бизнес-события в рамках одного процесса — оба вызова получат разные seq и оба будут записаны. Idempotent producer защищает от дубликатов транспорта (retry), а не от дубликатов приложения (повторный `send()`).

**Потеря буфера при crash'е.** Между вызовом `send()` и получением подтверждения от broker'а данные живут только в памяти процесса — в буфере producer'а. Crash процесса = потеря всех неподтверждённых событий. Это не проблема дубликатов, а проблема durability неотправленных данных. Outbox-таблица или write-ahead log на стороне приложения решают её, но порождают сценарий с дубликатами из предыдущего пункта.

**Атомарность записи в несколько партиций.** Orders-сервис хочет записать два события в один topic, но partition key'и разные — события попадают в разные партиции. Sequence number'ы ведутся per partition. Первое событие записано, второе нет (broker упал) — частичная запись. Idempotent producer не обеспечивает «всё или ничего» для нескольких партиций.

**Дубликаты на стороне consumer'а.** Consumer прочитал событие, обработал, упал до commit'а offset'а. Рестартнул — прочитал то же событие снова. Producer ничего не знает о consumer'е и никак не влияет на его гарантии — idempotent producer работает на стороне записи, не на стороне чтения.

Для защиты от дубликатов приложения и для атомарной записи в несколько партиций существует **transactional producer**, использующий стабильный `transactional.id`, который переживает рестарты.

## Sources

- Narkhede, Shapira, Palino, 2017, *Kafka: The Definitive Guide*. O'Reilly
- Apache Kafka Documentation. <https://kafka.apache.org/documentation/>
