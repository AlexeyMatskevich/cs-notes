---
tags:
  - domain/messaging
  - theme/queues
  - theme/distribution
  - type/overview
aliases:
  - Apache Kafka
  - Kafka
order: 0
---

# Apache Kafka

**Предпосылки:** [Гарантии доставки](../../system-design/delivery-guarantees.md) (at-most-once, at-least-once, exactly-once), [Message Queues](../../system-design/message-queues.md) (log-based брокер, партиции, consumer groups), [Event-driven Architecture](../../system-design/event-driven-architecture.md) (CQRS, проекции, event sourcing), [Redis Stream](../../databases/redis/data-structures/stream.md) (append-only лог, consumer groups, PEL).

Kafka — распределённая платформа потоковой обработки событий. В основе — append-only лог на диске, разбитый на партиции и распределённый по кластеру broker'ов. Партиции обеспечивают горизонтальное масштабирование записи и чтения, репликация — durability и availability. Consumer groups с независимыми offset'ами позволяют нескольким подсистемам читать один поток событий параллельно, каждая в своём темпе.

## Порядок изучения

Заметки выстроены по зависимостям: сначала фундаментальная модель данных (broker, topic, partition, offset), затем механизмы надёжности (репликация), потом producer и consumer как клиенты этой модели, и наконец — внутреннее устройство хранения.

### Архитектура

Как устроен кластер Kafka: из каких сущностей состоит, как данные распределяются и реплицируются.

- [[messaging/kafka/architecture/what-is-kafka|Broker, topic, partition, offset]] — фундаментальная модель: почему Redis Streams не справляется при росте, как Kafka распределяет лог по серверам, тройная роль партиции, несколько producer'ов в одну партицию, consumer groups с независимыми offset'ами
- [[messaging/kafka/architecture/replication|Репликация]] — per-partition leader/follower, ISR, high watermark, acks, min.insync.replicas, controller и partition leader election, KRaft
- [[messaging/kafka/architecture/producer-reliability|Producer reliability]] — retries, ordering, idempotent producer: PID, sequence number, exactly-once per partition
- [[messaging/kafka/architecture/consumer-internals|Consumer internals]] — poll loop, offset commit, heartbeat, rebalancing: eager vs cooperative protocol, assignment strategies
- [[messaging/kafka/architecture/transactions|Transactions]] — transactional producer, exactly-once для consume-transform-produce, LSO, read_committed isolation

## Как всё связано

**Throughput vs Latency:** Kafka оптимизирован под throughput — батчинг записей, sequential I/O, zero-copy. Цена — latency отдельного сообщения выше, чем у in-memory брокера (Redis Streams: микросекунды, Kafka: единицы миллисекунд). Для event pipeline и CQRS-проекций это допустимо; для real-time чата — нет.

**Durability vs Performance:** синхронная репликация (`acks=all`) гарантирует, что сообщение записано на несколько broker'ов до подтверждения producer'у. Цена — дополнительная латентность на каждую запись. `acks=1` (только leader) быстрее, но при смерти leader'а до репликации — потеря данных.

**Ordering vs Parallelism:** порядок гарантирован только внутри одной партиции. Больше партиций = больше параллелизма (больше consumer'ов в группе), но корреляция между событиями из разных партиций теряется. Partition key определяет, какие события обязаны идти в одну партицию для сохранения порядка.

## Sources

- Narkhede, Shapira, Palino, 2017, *Kafka: The Definitive Guide*. O'Reilly
- Apache Kafka Documentation. <https://kafka.apache.org/documentation/>
- Kreps, 2013, *The Log: What every software engineer should know about real-time data's unifying abstraction*. <https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying>
