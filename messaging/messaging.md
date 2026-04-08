# Messaging

**Предпосылки:** [Гарантии доставки](../system-design/delivery-guarantees.md) (at-most-once, at-least-once, exactly-once), [Message Queues](../system-design/message-queues.md) (temporal decoupling, broker, log vs queue, партиции, consumer groups).

Распределённые системы обмениваются данными не только через синхронные HTTP/gRPC-вызовы. Когда нужна развязка во времени, надёжная доставка или replay событий, появляются специализированные брокеры сообщений. Абстрактные паттерны — очередь vs лог, партиции, backpressure — описаны в [Message Queues](../system-design/message-queues.md), [гарантии доставки](../system-design/delivery-guarantees.md) — в отдельной заметке. Здесь — конкретные реализации: как каждая технология воплощает эти паттерны, какие trade-offs выбирает и чем отличается от альтернатив.

## Порядок изучения

### Kafka

Распределённый лог событий: хранение на диске, горизонтальное масштабирование через партиции, репликация для durability. Подходит для высоконагруженных event pipeline, CQRS-проекций, интеграции между сервисами.

- [Kafka](./kafka/kafka.md) — архитектура, producer, consumer, storage, паттерны

## Как всё связано

**RAM vs диск:** Redis Streams хранит лог в памяти — микросекундные задержки, но объём ограничен RAM. Kafka хранит на диске с sequential I/O — throughput сопоставим, а retention может составлять терабайты и недели.

**Простота vs масштаб:** Redis Streams — один процесс, один Stream, встроенный в уже работающий Redis. Kafka — кластер broker'ов, ZooKeeper/KRaft, отдельная инфраструктура. Если объём помещается в RAM и пять consumer groups справляются с одним потоком — Redis Streams проще. Если нужны сотни гигабайт retention и горизонтальное масштабирование записи — Kafka.

## Sources

- Narkhede, Shapira, Palino, 2017, *Kafka: The Definitive Guide*. O'Reilly
- Apache Kafka Documentation. <https://kafka.apache.org/documentation/>
