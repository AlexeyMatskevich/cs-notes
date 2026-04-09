---
tags:
  - domain/messaging
  - theme/distribution
  - theme/queues
  - type/concept
aliases:
  - Kafka Broker
  - Kafka Partition
  - Kafka Topic
order: 0
---

# Broker, topic, partition, offset

**Предпосылки:** [Message Queues](../../../system-design/message-queues.md) (log-based брокер, партиции, consumer groups), [Event-driven Architecture](../../../system-design/event-driven-architecture.md) (CQRS, проекции), [Redis Stream](../../../databases/redis/data-structures/stream.md) (append-only лог, consumer groups, PEL).

CQRS-архитектура из [event-driven architecture](../../../system-design/event-driven-architecture.md): Orders-сервис пишет заказы в PostgreSQL, после commit публикует событие в поток, пять независимых consumer groups обновляют свои read-модели — панель продавца, Elasticsearch (поиск), ClickHouse (аналитика), рекомендации, fraud detection. Транспорт событий — [Redis Stream](../../../databases/redis/data-structures/stream.md): append-only лог с consumer groups и подтверждением обработки через PEL и XACK.

При 50 заказах в минуту система работает. Магазин растёт — и упирается в ограничения Redis Streams.

## Пределы Redis Streams

Магазин растёт до 3 000 заказов в минуту. Каждый заказ порождает в среднем 3 события (created, paid, shipped) — 9 000 событий/мин, ~150 events/sec. Среднее событие ~2 KB (JSON с данными заказа, товарами, адресом). Бизнес требует хранить все события 30 дней для аудита, пересборки проекций при баге и replay для новых consumer'ов.

150 events/sec × 2 KB = 300 KB/sec ≈ 25 GB/день. За 30 дней — **750 GB**.

Redis Stream хранит данные в оперативной памяти. Типичный production-сервер — 64–256 GB RAM, из которых Redis получает часть. Чтобы удержать 750 GB, нужен сервер с терабайтом оперативной памяти — стоимость на порядок выше обычного. На диске того же сервера лежат терабайты за малую долю этой цены.

Может, распределить данные по нескольким серверам? [Redis Cluster](../../../databases/redis/distribution/cluster.md) шардирует данные по ключам, но один Stream — это один ключ. Ключ `order_events` целиком живёт на одном шарде. Разбить один Stream по нескольким нодам средствами Redis Cluster нельзя. Можно вручную создать `order_events:0`, `order_events:1`, ... и маршрутизировать на уровне приложения — но тогда логика партицирования, балансировки consumer'ов и ordering ложится на разработчика, Redis в этом не помогает.

Остаётся вопрос надёжности. Redis с [AOF](../../../databases/redis/persistence/aof.md) в режиме `everysec` теряет максимум ~1 секунду данных при падении. [Sentinel](../../../databases/redis/distribution/sentinel.md) обеспечивает failover за секунды — реплика подхватывает, pipeline не останавливается. Но репликация асинхронная: при failover часть последних событий может быть потеряна. Это проблема durability, не availability — система продолжает работать, но несколько событий могут исчезнуть. Для потока платежей, где каждое событие критично, это значимый риск.

Нужна система, которая хранит лог на диске (не в RAM), распределяет его по нескольким серверам (не одна нода на весь поток) и реплицирует для надёжности. Apache Kafka построена именно для этого.

## Sequential I/O

Данные на диске — но не будет ли это медленнее, чем in-memory Redis? Скорость зависит не от типа носителя, а от паттерна доступа.

**Random I/O** — чтение/запись в случайных местах. На HDD каждая такая операция требует физического перемещения считывающей головки и ожидания поворота диска (seek time 5–10 ms). **Sequential I/O** — последовательное чтение/запись: головка встаёт один раз и читает непрерывно. Разница — примерно 100x.

На SSD нет движущихся частей, но sequential I/O всё равно быстрее в 4–10x. Причины: SSD читает и пишет блоками (обычно 4 KB страницы), а стирает целыми блоками (128–512 KB). Random write по разным страницам вызывает циклы read-modify-write и усиливает внутренний garbage collection контроллера SSD. Sequential write заполняет блоки последовательно, без этого overhead. Вдобавок ОС и контроллер агрессивно делают prefetch (предзагрузку) при sequential-паттерне — при random доступе предсказать следующий запрос невозможно.

Sequential I/O быстрее на любом носителе. Kafka использует это как фундаментальный архитектурный принцип: producer добавляет записи в конец файла (append), consumer читает последовательно с определённой позиции. Основные операции Kafka — sequential I/O, random доступ к диску не используется.

## Broker: сервер в кластере

Kafka хранит данные на обычных серверах с локальными дисками. Каждый такой сервер называется **broker** (брокер) — процесс Kafka, запущенный на машине. В [терминологии message brokers](../../../system-design/message-queues.md) — посредник между [producer](producer-reliability.md) и [consumer](consumer-internals.md): принимает сообщения, хранит, отдаёт. Отличие от Redis — данные на диске, не в оперативной памяти.

Кластер — несколько broker'ов. Для нашего сценария — три: Broker 0, Broker 1, Broker 2, каждый на отдельном сервере с локальным диском.

## Topic и partition

Три broker'а готовы хранить данные — но как именно поток `order_events` раскладывается по ним?

**Topic** (топик) — логическое имя потока событий, аналог Stream в Redis. Producer публикует события в topic, consumer'ы подписываются на topic. В нашем сценарии — topic `order_events`, куда Orders-сервис публикует все события заказов. Но в отличие от Redis Stream, topic — только логическое имя. Физически данные хранятся в **partition'ах**.

**Partition** (партиция) — физический append-only лог на диске конкретного broker'а. Один topic состоит из одной или нескольких partition, каждая — отдельный файл (точнее, директория с файлами-сегментами — их внутреннюю структуру разберём отдельно).

В Redis: один Stream = один ключ = один сервер = один append-only лог в памяти. В Kafka: один topic = N partition = данные распределены по нескольким broker'ам = N независимых append-only логов на диске.

Для `order_events` с 6 партициями на 3 broker'ах:

```
Broker 0                 Broker 1                 Broker 2
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  order_events-0  │     │  order_events-1  │     │  order_events-2  │
│  [msg][msg][msg] │     │  [msg][msg]      │     │  [msg][msg][msg] │
│                  │     │                  │     │                  │
│  order_events-3  │     │  order_events-4  │     │  order_events-5  │
│  [msg][msg]      │     │  [msg][msg][msg] │     │  [msg]           │
└──────────────────┘     └──────────────────┘     └──────────────────┘
      (диск)                   (диск)                   (диск)
```

`order_events-0` ... `order_events-5` — физические директории на дисках broker'ов. 750 GB распределяются по трём серверам, по ~250 GB на каждом. Обычные диски, не терабайт RAM.

Partition в Kafka играет тройную роль. Это единица **распределения** ([шардирования](../../../system-design/message-queues.md)): разные [партиции](../../../system-design/message-queues.md) живут на разных broker'ах, данные и нагрузка распределяются по кластеру. Это единица **порядка**: внутри одной [партиции](../../../system-design/message-queues.md) записи строго упорядочены по времени добавления. И это единица **параллелизма**: каждую [партицию](../../../system-design/message-queues.md) в [consumer group](../../../system-design/message-queues.md) читает один [consumer](consumer-internals.md).

## Partition key и порядок событий

Когда producer отправляет событие, оно попадает в одну конкретную партицию. Выбор определяет partition key: `hash(partition_key) % число_партиций`.

Для `order_events` partition key — `order_id`. Событие для заказа #42: `hash(42) % 6 = 3` — попадает в `order_events-3` на Broker 0. Через минуту заказ #42 меняет статус — ещё одно событие с тем же `order_id`. Хеш-функция детерминирована: `hash(42) % 6` всегда даёт 3. Все события одного заказа попадают в одну партицию и хранятся в порядке записи — consumer обработает `created` до `paid`, `paid` до `shipped`.

При 3 000 заказов в минуту Orders-сервис работает не одним процессом — за балансировщиком стоят три инстанса, каждый из которых является отдельным Kafka producer. Инстанс A создаёт заказ #42, инстанс B через минуту обрабатывает его оплату. Оба отправляют события в topic `order_events` с partition key = `order_id`. Хеш-функция детерминирована: `hash(42) % 6 = 3` даёт одинаковый результат вне зависимости от того, какой инстанс вычислил хеш. Оба события попадают в партицию 3.

Внутри партиции порядок определяет broker: он принимает записи от разных producer'ов и назначает каждой следующий offset. Consumer видит `created #42` раньше `paid #42` — порядок корректен, хотя события отправлены разными процессами. Кроме инстансов одного сервиса, в тот же topic могут писать и другие сервисы. Topic — логическое имя потока, не привязанное к конкретному publisher. Broker не различает, от какого сервиса пришла запись — он назначает offset и записывает в лог.

Без partition key события одного заказа могли бы разлететься по разным партициям. Между партициями порядок не гарантирован — consumer мог бы обработать `shipped` раньше `created`. Partition key — механизм, который связывает [ordering из message queues](../../../system-design/message-queues.md) с физическим распределением данных.

Partition key определяет и распределение нагрузки: 150 events/sec расходятся по 6 партициям — в среднем ~25 events/sec на партицию. Запись идёт параллельно на трёх broker'ах.

## Offset: позиция в логе

События маршрутизированы в партиции. Каждая партиция — append-only лог, записи добавляются в конец. Consumer'у нужно знать, до какого места он дочитал.

Каждая запись в партиции получает порядковый номер — **offset** (смещение). Нумерация начинается с 0 и монотонно растёт. Offset — целое число, не timestamp и не составной ID (в отличие от Redis Stream, где ID = `<millisecondsTime>-<sequenceNumber>`).

```
order_events-3 (партиция 3):

offset:  0        1        2        3        4
       ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐
       │#42 │  │#78 │  │#42 │  │#15 │  │#42 │
       │crtd│  │crtd│  │paid│  │crtd│  │ship│
       └────┘  └────┘  └────┘  └────┘  └────┘
```

Заказ \#42 — на offset'ах 0 (created), 2 (paid), 4 (shipped). Между ними события других заказов, попавших в ту же партицию по хешу. Порядок записи = порядок offset'ов = порядок чтения.

Offset не глобален для topic'а — у каждой партиции свой независимый счётчик. Offset 3 в партиции 0 и offset 3 в партиции 3 — два разных сообщения. Consumer запоминает одно число — «обработал до offset 3 в партиции 3» — и при следующем чтении просит «дай с offset 4». Дешёвая операция: сравнение и инкремент целого числа.

## Consumer groups: независимые указатели

Пять [consumer group](../../../system-design/message-queues.md) хотят получить каждое событие: seller read DB, Elasticsearch, ClickHouse, рекомендации, fraud detection. Все читают одни и те же данные — Kafka не копирует сообщения для каждой группы и не удаляет их при чтении.

Каждая [consumer group](../../../system-design/message-queues.md) хранит **свой набор offset'ов** — по одному на каждую [партицию](../../../system-design/message-queues.md). Seller read DB может быть на offset 4 в [партиции](../../../system-design/message-queues.md) 3, а ClickHouse — на offset 2 в той же [партиции](../../../system-design/message-queues.md) (обрабатывает медленнее, отстаёт). Данные в [партиции](../../../system-design/message-queues.md) одни, указатели разные:

```
partition 3:  [0] [1] [2] [3] [4]

seller_read_db   ──────────────────> offset = 4
elasticsearch    ─────────────>      offset = 3
clickhouse       ────────>          offset = 2
recommendations  ─────────────>      offset = 3
fraud_detection  ──────────────────> offset = 4
```

Принцип тот же, что в [Redis Streams consumer groups](../../../databases/redis/data-structures/stream.md): каждая группа видит весь поток, внутри группы сообщения распределяются между обработчиками. Разница — в Redis Streams распределение идёт на уровне отдельных сообщений (каждое следующее уходит свободному [consumer'у](consumer-internals.md)), в Kafka — на уровне [партиций](../../../system-design/message-queues.md).

Внутри одной группы [consumer'ы](consumer-internals.md) конкурируют за [партиции](../../../system-design/message-queues.md): если в группе `seller_read_db` три [consumer'а](consumer-internals.md), каждый получает свою часть из 6 [партиций](../../../system-design/message-queues.md) (например, [consumer](consumer-internals.md) A читает [партиции](../../../system-design/message-queues.md) 0 и 1, [consumer](consumer-internals.md) B — 2 и 3, [consumer](consumer-internals.md) C — 4 и 5). Одна [партиция](../../../system-design/message-queues.md) читается одним [consumer'ом](consumer-internals.md) — это гарантирует порядок обработки внутри [партиции](../../../system-design/message-queues.md) без координации между [consumer'ами](consumer-internals.md).

Следствие: число [consumer'ов](consumer-internals.md) в группе ограничено числом [партиций](../../../system-design/message-queues.md). Если [партиций](../../../system-design/message-queues.md) 6 и [consumer'ов](consumer-internals.md) 6 — каждый читает одну [партицию](../../../system-design/message-queues.md), максимальный параллелизм. Если [consumer'ов](consumer-internals.md) 8 — два из них простаивают, им не достанется ни одной [партиции](../../../system-design/message-queues.md). Число [партиций](../../../system-design/message-queues.md) определяет потолок параллелизма для каждой [consumer group](../../../system-design/message-queues.md).

## Путь события: от producer'ов до consumer groups

```
Orders-сервис (3 инстанса)
Producer A    Producer B    Producer C
    │              │              │
    │  event: {order_id: 42, type: "paid", ...}
    │  partition_key = order_id
    │  hash(42) % 6 = 3
    │              │              │
    v              v              v
┌─ Kafka Cluster ──────────────────────────────────────────────┐
│                                                               │
│  Broker 0              Broker 1              Broker 2         │
│  ┌────────────────┐    ┌────────────────┐    ┌──────────────┐ │
│  │ partition 0    │    │ partition 1    │    │ partition 2  │ │
│  │ offsets: 0..N  │    │ offsets: 0..M  │    │ offsets: 0..K│ │
│  │                │    │                │    │              │ │
│  │ partition 3  <─┼────┼── event #42 ───┼────┼──            │ │
│  │ offsets: 0..4  │    │ partition 4    │    │ partition 5  │ │
│  │                │    │ offsets: 0..P  │    │ offsets: 0..Q│ │
│  └────────────────┘    └────────────────┘    └──────────────┘ │
│       (диск)                (диск)               (диск)       │
└───────────────────────────────────────────────────────────────┘
    │         │         │         │         │
    v         v         v         v         v
 seller    elastic   click     recom     fraud
 read DB   search    house     mend.     detect.
 (offset   (offset   (offset   (offset   (offset
  set A)    set B)    set C)    set D)    set E)
```

Topic `order_events` с 6 [партициями](../../../system-design/message-queues.md) на 3 broker'ах решает две из трёх проблем Redis Streams: данные на диске (750 GB за доступную цену), нагрузка распределена по кластеру (каждый broker хранит ~250 GB и обрабатывает ~50 events/sec записи).

Третья проблема — durability — пока открыта. Broker 0 вышел из строя: [партиции](../../../system-design/message-queues.md) 0 и 3 недоступны, события заказов, попавших в эти [партиции](../../../system-design/message-queues.md), потеряны. Для решения нужна [репликация](replication.md) — копирование каждой [партиции](../../../system-design/message-queues.md) на несколько broker'ов. Там появятся leader, follower, ISR (in-sync replicas) — механизмы, которые превращают кластер из трёх независимых дисков в надёжное хранилище.

## Sources

- Narkhede, Shapira, Palino, 2017, *Kafka: The Definitive Guide*. O'Reilly
- Kreps, 2013, *The Log: What every software engineer should know about real-time data's unifying abstraction*. <https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying>
- Apache Kafka Documentation. <https://kafka.apache.org/documentation/>
