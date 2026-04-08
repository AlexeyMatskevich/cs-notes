# Event-driven Architecture

**Предпосылки:** [Профили нагрузки](read-write-profiles.md) (индексы замедляют запись, read-heavy vs write-heavy), [Модели консистентности](consistency-models.md) (eventual consistency, read-your-writes), [Паттерны надёжности](reliability-patterns.md) (idempotency), [Message Queues](message-queues.md) (temporal decoupling, pub/sub, log-based vs queue-based брокер), [Микросервисы](microservices.md) (текущая архитектура магазина: Orders, события, подписчики).

Архитектура из предыдущей заметки работает: Orders пишет в PostgreSQL, checkout координируется через saga, событие `order.completed` уходит в очередь, Notification, Loyalty и Analytics подписываются самостоятельно. Но Orders-сервис обслуживает не только checkout. Бизнес хочет панель продавца: список заказов с фильтрацией по статусу, дате, городу, полнотекстовый поиск по товарам, выручка за период, топ продаж. Все эти данные лежат в той же PostgreSQL, куда пишутся заказы. Одна модель данных — два конфликтующих паттерна доступа.

## Конфликт паттернов доступа

Таблица `orders` оптимизирована под запись: нормализованная схема ([3НФ](../databases/sql/foundations/normalization.md)), три индекса — по `user_id` (мои заказы), `created_at` (сортировка), `status` (фильтрация). Три индекса — терпимо для checkout, который делает INSERT, UPDATE в inventory и внешний вызов Payment.

Панель продавца требует другого. Фильтрация по продавцу и дате — индекс по `(seller_id, created_at)`. Фильтрация по городу — JOIN с `addresses`, индекс по `city`. Топ товаров — JOIN `orders` + `order_items` + `products`, GROUP BY, ORDER BY count. Полнотекстовый поиск по названиям товаров — GIN-индекс на `tsvector`. Итого: было 3 индекса, стало 7. Каждый checkout INSERT теперь обновляет 7 индексов вместо 3. При 500 заказах в секунду разница ощутима — каждый дополнительный индекс это запись в ещё одну структуру данных на диске.

Но проблема глубже индексов. Аналитический запрос «выручка за месяц по дням» — sequential scan или index scan по сотням тысяч строк с агрегацией. Он держит соединение из пула секунды, а не миллисекунды. Пока десять продавцов смотрят дашборд одновременно — checkout начинает ждать свободного соединения.

Read replica? Частично помогает — аналитику можно отправить на реплику. Но схема на реплике та же, нормализованная. Тяжёлые JOIN с GROUP BY всё равно дорогие. И добавить индекс только на реплику нельзя — реплика воспроизводит WAL с primary, включая структуру индексов.

Корень проблемы: одна модель данных обслуживает два принципиально разных паттерна доступа. Запись хочет минимум индексов, нормализованную схему, быстрые точечные INSERT/UPDATE. Чтение хочет много индексов, денормализованные данные (pre-joined, pre-aggregated), сложные выборки.

## Materialized view и триггеры

Первая идея — materialized view. Денормализованное представление с заранее подтянутыми JOIN-ами:

```sql
CREATE MATERIALIZED VIEW seller_orders_view AS
SELECT o.id, o.status, o.total, o.created_at,
       p.name AS product_name, a.city
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id
JOIN addresses a ON a.id = o.shipping_address_id
WHERE o.seller_id IS NOT NULL;

CREATE INDEX idx_seller_view_seller ON seller_orders_view(seller_id, created_at);
CREATE INDEX idx_seller_view_city ON seller_orders_view(city);
```

Данные денормализованы, индексы свои — запись в основную таблицу `orders` не затрагивает эти индексы. Идея правильная: хранить данные для чтения в отдельной, заранее подготовленной форме.

Проблема в механизме обновления. `REFRESH MATERIALIZED VIEW` — полный пересчёт: PostgreSQL выполняет весь SELECT заново и перезаписывает таблицу. При 10 миллионах заказов — минуты. `CONCURRENTLY` не блокирует чтение, но сам рефреш по-прежнему тяжёлый. Рефреш каждые 5 минут означает, что продавец не видит свежий заказ 5 минут. Рефреш каждые 30 секунд — та же нагрузка на primary, от которой уходили, только теперь по расписанию. Нативного инкрементального обновления materialized views в PostgreSQL нет (по состоянию на PostgreSQL 17); расширение pg_ivm существует, но не в ядре.

Есть более простой механизм: триггер. `AFTER INSERT ON orders` вставляет денормализованную строку в отдельную read-таблицу `seller_orders_read`. Инкрементально, без full scan, без расширений. Триггер выполняется в той же транзакции, что и INSERT — не бывает ситуации «записали заказ, но не обновили read-таблицу». Данные согласованы транзакционно.

```
BEGIN (checkout transaction)
  INSERT INTO orders (...)
  UPDATE inventory SET reserved = reserved + 1 WHERE sku = ?
  TRIGGER: INSERT INTO seller_orders_read (
    SELECT o.id, o.total, p.name, a.city ...
    FROM orders o JOIN ... WHERE order_id = NEW.id
  )
COMMIT
```

Для одной read-модели внутри одного PostgreSQL этого достаточно. Это уже разделение моделей чтения и записи в минимальном виде — запись идёт в нормализованную `orders`, чтение продавца — из денормализованной `seller_orders_read`.

## От одной read-модели к нескольким

Триггер решает проблему для панели продавца. Но бизнес растёт, и потребителей данных становится три.

Панель продавца — денормализованные заказы в PostgreSQL read-таблице. Поиск — продавец ищет заказ по имени покупателя, адресу, SKU товара; при миллионах заказов полнотекстовый поиск с ранжированием и фасетами выходит за пределы того, для чего PostgreSQL оптимизирован, — здесь нужен Elasticsearch. Аналитика — выручка по дням, воронка конверсии, когортный анализ — ClickHouse, который уже есть в архитектуре.

Триггер живёт внутри PostgreSQL-транзакции. Он не может надёжно записать в Elasticsearch или ClickHouse — это внешние системы, транзакция PostgreSQL их не покрывает. Если Elasticsearch недоступен в момент триггера — транзакция checkout откатывается. Покупатель не может оплатить заказ из-за того, что поисковый индекс для продавца лежит.

Нужно [temporal decoupling](message-queues.md) — развязка записи заказа и обновления read-моделей по времени. Запись фиксирует факт и завершается; read-модели обновляются позже, асинхронно.

Background job через [Sidekiq](../rails/sidekiq/architecture.md) — первый вариант. `after_commit` callback в Rails ставит задачу: `SyncOrderToElasticsearchJob.perform_async(order_id)`. Retry с backoff из коробки, обновление per-event (секунды, не минуты). Работает для трёх потребителей — три джоба на каждый заказ:

```ruby
after_commit :enqueue_sync_jobs

def enqueue_sync_jobs
  UpdateSellerReadTableJob.perform_async(id)
  SyncToElasticsearchJob.perform_async(id)
  SyncToClickHouseJob.perform_async(id)
end
```

Проблема — coupling. Orders знает обо всех потребителях. Появился четвёртый consumer (рекомендательная система) — ещё один джоб. Пятый (fraud detection) — ещё один. Каждый новый потребитель данных требует изменения кода Orders-сервиса: добавить callback, добавить джоб. Orders отправляет команды («синхронизируй в Elasticsearch»), а не факты. Это зависимость от внешних модулей (efferent coupling).

Решение — [pub/sub](message-queues.md). Orders публикует событие — факт о том, что произошло — в message queue: `order.completed`, `order.shipped`, `order.cancelled`. Потребители подписываются сами. Добавление нового consumer — ноль изменений в коде Orders.

```
БЫЛО (Sidekiq, Orders знает всех):

  Orders ──> SyncElasticsearchJob
         ──> SyncClickHouseJob
         ──> UpdateSellerReadJob
         ──> каждый новый consumer = изменение Orders

СТАЛО (pub/sub, Orders знает только событие):

  Orders ──> publish("order.completed", {order_id, seller_id, total, ...})
                          │
                    ┌─────┼──────┬──────────┬──────────┐
                    ▼     ▼      ▼          ▼          ▼
                  ReadDB   ES   ClickH   Recommend   Fraud
                (подписались сами, Orders не знает о них)
```

Ключевое различие: команда подразумевает знание получателя и ожидаемого действия; событие — нет. Команда — «сделай вот это». Событие — «вот что произошло». В Sidekiq-варианте Orders отправлял команды ([command vs event в Sidekiq](../rails/sidekiq/job-design.md#command-vs-event-модель-интеграции)). В pub/sub — публикует события.

## CQRS

Отдельная модель для записи (нормализованная, мало индексов), отдельные модели для чтения (денормализованные, в подходящих хранилищах), синхронизация через события — всё, что мы построили за последние три шага, имеет название.

Command Query Responsibility Segregation — разделение ответственности между командами и запросами. Command — операция, которая меняет состояние (создать заказ, сменить статус). Query — операция, которая читает состояние (список заказов продавца, аналитика). Они обрабатываются разными моделями.

Термин ввёл Грег Янг (Greg Young) в ~2010, развив идею Бертрана Мейера — CQS (Command Query Separation). CQS — принцип уровня кода: метод либо возвращает результат и не меняет состояние, либо меняет состояние и ничего не возвращает. CQRS — архитектурный паттерн: разные модели данных для записи и чтения.

В нашем сценарии:

**Write model (command side):** нормализованная схема в PostgreSQL, оптимизированная под checkout. Минимум индексов. Транзакция: `INSERT order` → `UPDATE inventory` → вызов Payment. После commit — публикация события в message queue.

**Read models (query side):** отдельные хранилища, каждое оптимизировано под свой паттерн чтения.

```
                    COMMAND SIDE                     QUERY SIDE
                ┌─────────────────┐
                │  Orders Service │
 CreateOrder ──>│                 │──> event: "order.completed"
 ChangeStatus──>│  Normalized DB  │         │
 CancelOrder───>│  (PostgreSQL)   │    ┌────┴──────────────────┐
                │  3 индекса      │    │    Message Queue      │
                └─────────────────┘    └────┬────┬────┬────────┘
                                            │    │    │
                                            v    v    v
                                ┌────────┐ ┌──┐ ┌───────────┐
                                │Seller  │ │ES│ │ ClickHouse│
                                │ReadDB  │ │  │ │           │
                                │(PG)    │ │  │ │           │
                                └────────┘ └──┘ └───────────┘
                                 список    поиск  аналитика
                                 заказов
```

Каждый consumer на query side — **проекция** (projection). Проекция — процесс, который слушает поток событий и строит из них read-модель. Название по аналогии с геометрической проекцией: трёхмерный объект (полное состояние системы) проецируется на плоскость (конкретное представление для конкретного потребителя). Разные плоскости — разные проекции одних и тех же данных.

```ruby
class SellerOrdersProjection
  def handle(event)
    case event.type
    when "order.completed"
      SellerOrderRead.create!(
        order_id: event.data[:order_id],
        seller_id: event.data[:seller_id],
        product_name: event.data[:product_name],
        city: event.data[:city],
        total: event.data[:total],
        status: "completed"
      )
    when "order.cancelled"
      SellerOrderRead.where(order_id: event.data[:order_id])
                     .update!(status: "cancelled")
    end
  end
end
```

Событие несёт все данные, нужные проекции. Проекция не ходит в write-базу за дополнительной информацией — иначе снова coupling между read и write сторонами.

### Цена: eventual consistency

Write-модель и read-модели синхронизируются через очередь. Между моментом создания заказа в write-базе и его появлением в seller read table проходит время — 100ms, секунда, при проблемах с очередью — минуты. Это [eventual consistency](consistency-models.md).

Для панели продавца секундная задержка допустима. Для покупателя, который только что оплатил и хочет увидеть свой заказ, — нет. Поэтому покупатель читает из write-модели (его запрос простой: `WHERE user_id = ? ORDER BY created_at DESC`), а продавец — из read-модели. CQRS не означает «всё чтение идёт через read-модель». Это выбор, откуда читать, в зависимости от требований к consistency и паттерна запроса.

### Когда CQRS не нужен

CQRS — не замена обычной архитектуре. Если чтение и запись работают с одними и теми же данными в одной форме (типичный CRUD), CQRS добавляет сложность без выгоды. Сигналы, что CQRS не нужен: одна команда разработчиков, один-два клиента с похожими паттернами чтения, нагрузка помещается в один PostgreSQL с индексами, нет аналитики или она решается простым `SELECT ... GROUP BY`.

Сигналы, что пора: read и write хотят разные индексы, разные формы данных (нормализованная vs денормализованная), разные хранилища (PostgreSQL vs Elasticsearch vs ClickHouse), или чтение нагружает write-базу до деградации основных операций.

CQRS не требует distributed log, Kafka или отдельных баз данных. В простейшей форме — триггер, заполняющий read-таблицу в той же PostgreSQL. Спектр решений: триггер (синхронный, в транзакции) → background job (асинхронный, coupling) → pub/sub (асинхронный, decoupled). Каждый шаг добавляет сложность и убирает ограничение.

## Потеря истории в мутабельном состоянии

В текущей CQRS-архитектуре write-модель — обычная PostgreSQL с мутабельным состоянием. `UPDATE orders SET status = 'shipped' WHERE id = 42` перезаписывает старое значение. Событие `order.shipped` публикуется и уходит в проекции, но write-база хранит только текущий снимок.

Менеджер спрашивает: «Заказ #42 — когда он перешёл из `paid` в `shipped`?» Ответить нельзя — в базе только `status = 'shipped'` и `updated_at`. Прагматичное решение: добавить `paid_at`, `shipped_at`, `delivered_at` — отдельный timestamp на каждый переход. Или JSONB-поле `status_history`:

```json
[
  {"status": "created",  "at": "2025-06-01T12:00:01Z"},
  {"status": "paid",     "at": "2025-06-01T12:00:05Z"},
  {"status": "shipped",  "at": "2025-06-03T09:15:00Z"}
]
```

Работает. Но через месяц менеджер спрашивает: «Заказ #42 — клиент говорит, сумма была 7000, а списали 8500. Что произошло?» В базе `total = 8500`, предыдущее значение перезаписано. Ещё через месяц: «Почему товар X оказался в заказе?» Таблица `order_items` мутабельна — INSERT/DELETE не оставляют следа.

Каждый раз, когда бизнес хочет знать «как мы пришли в текущее состояние», нужно ещё одно поле истории: `status_history`, `total_history`, `items_history`. По сути — ручная достройка лога изменений рядом с мутабельным состоянием.

### Audit log vs domain events

Audit log решает часть этой проблемы. Logidze (расширение для Rails) автоматически записывает дифы через триггер и поддерживает мета-информацию: кто сделал изменение, из какого контекста, с какой целью. PaperTrail работает аналогично. Для большинства Rails-приложений audit log с метой — достаточно для ответа на вопрос «кто и когда это сделал».

Различие между audit log и domain events — в том, что каждый из них записывает. Audit log фиксирует диф данных: `{changes: {total: [8500, 10500]}, at: "..."}`. Что произошло — непонятно без сопоставления дифов разных полей и таблиц. Domain event фиксирует бизнес-факт: `ItemAdded {sku: "B", price: 2000, qty: 1, added_by: "support_agent_5", reason: "customer_request", ticket: "SUP-1234"}`. Причина изменения — в самом событии.

Вторая разница — в гарантиях. Audit log — побочный продукт записи. Если триггер Logidze не сработал (баг, прямой SQL в консоли, миграция данных), данные изменились, а лог нет. В event sourcing событие — единственный способ изменить состояние. Нет события — нет изменения.

## Event Sourcing

Вместо хранения текущего состояния и дописывания истории — хранить только историю, а текущее состояние вычислять из неё.

Последовательность событий заказа #42:

```
Event 1: OrderCreated     {user: 7, items: [{sku: "A", price: 7000, qty: 1}]}
Event 2: DeliveryChosen   {method: "express", cost: 1500}
Event 3: PaymentCharged   {amount: 8500, charge_id: "ch_abc"}
Event 4: ItemAdded        {sku: "B", price: 2000, qty: 1, added_by: "support"}
Event 5: TotalRecalculated {old: 8500, new: 10500}
Event 6: OrderShipped     {tracking: "SF123456"}
```

Текущее состояние: `status = shipped`, `total = 10500`, `items = [A, B]`. Но теперь можно ответить на любой вопрос: товар B добавлен саппортом (Event 4), total изменился из-за этого (Event 5), изначальная сумма 8500 включала экспресс-доставку (Event 2).

Источником истины становится не текущее состояние, а последовательность событий. Состояние — производная величина, вычисляемая применением событий одного за другим:

```ruby
class Order
  def apply(event)
    case event.type
    when "OrderCreated"
      @status = :created
      @items = event.data[:items]
      @total = event.data[:total]
    when "ItemAdded"
      @items << event.data[:item]
      @total += event.data[:item][:price]
    when "PaymentCharged"
      @status = :paid
    when "OrderShipped"
      @status = :shipped
      @tracking = event.data[:tracking]
    end
  end
end
```

### Snapshot: оптимизация replay

Чтобы получить текущее состояние заказа, нужно воспроизвести (replay) всю цепочку событий с начала. Для заказа с 5–10 событиями — микросекунды. Для сущности с тысячами событий (банковский счёт за 10 лет) — проблема.

**Snapshot** (снимок) решает это: периодически сохраняется вычисленное состояние на определённый момент. Чтобы получить текущее состояние — загрузить последний snapshot и воспроизвести только события после него.

```
Events:    [1] [2] [3] ... [500] [501] [502] [503]
                             ↑
                        Snapshot: {balance: 45000, status: active, ...}

Чтение: загрузить snapshot + replay 501-503
        вместо replay 1-503
```

Если snapshot обновляется каждые 10 событий, replay — максимум 10 событий. Каждое событие просто применяет функцию к объекту в памяти — наносекунды. Загрузка: один SELECT snapshot + один SELECT последних N событий по `stream_id`. Два запроса — сопоставимо с обычным `SELECT * FROM orders WHERE id = 42`.

Дорогой replay — восстановление проекции с нуля. Новый consumer хочет построить read-модель: нужно пройти все события всех заказов. Это одноразовая операция (или редкая — при исправлении бага в проекции), выполняется в фоне.

## Event Sourcing + CQRS

Два паттерна естественно сочетаются. Event sourcing порождает поток событий, CQRS его потребляет.

```
  WRITE SIDE                                READ SIDE

  ┌──────────┐       publish       ┌───────────────────────┐
  │ Command  │─────────────────>   │    Message Queue      │
  │ Handler  │                     └────┬────┬────┬────────┘
  └────┬─────┘                          │    │    │
       │                                v    v    v
       v                           ┌──────┐ ┌──┐ ┌───────────┐
  ┌──────────┐                     │Seller│ │ES│ │ ClickHouse│
  │  Event   │                     │ReadDB│ │  │ │           │
  │  Store   │                     └──────┘ └──┘ └───────────┘
  │(append-  │
  │  only)   │                    Проекция  Проекция  Проекция
  └──────────┘                    списка    поиска    аналитики
                                  заказов
```

Command приходит → command handler валидирует, загружает текущее состояние (snapshot + replay), применяет бизнес-логику, записывает новое событие в event store → событие публикуется → проекции обновляют read-модели.

Но CQRS и event sourcing — независимые паттерны. Можно CQRS без event sourcing: обычная PostgreSQL на write-стороне, проекции обновляются через события. Можно event sourcing без CQRS: все читают через replay, без отдельных read-моделей — работает, пока запросы ограничены одной сущностью (`SELECT ... WHERE order_id = 42`). Для запросов через множество сущностей (`WHERE seller_id = ? AND city = ?`) replay не поможет — нужны проекции.

Eventual consistency между write и read сторонами одинакова что с event sourcing, что без: задержка определяется очередью, а не источником данных на write-стороне.

## Event store

Event sourcing записывает события — но куда? Нужно хранилище, оптимизированное под append-only запись с гарантией порядка внутри потока.

Append-only таблица в PostgreSQL — самый распространённый вариант для команд, у которых PostgreSQL уже есть:

```sql
CREATE TABLE events (
  id          BIGSERIAL PRIMARY KEY,
  stream_id   UUID NOT NULL,
  version     INTEGER NOT NULL,
  event_type  VARCHAR NOT NULL,
  data        JSONB NOT NULL,
  metadata    JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (stream_id, version)
);
```

Constraint `UNIQUE (stream_id, version)` — ключевая гарантия. Это optimistic concurrency: два процесса одновременно читают заказ #42 на version 5, оба пытаются записать version 6. Один получает unique violation — и должен перечитать состояние и повторить. Защита от race condition без блокировок — тот же принцип, что optimistic locking в ActiveRecord (`lock_version`), но на уровне event stream.

Запись — `INSERT`. Чтение состояния — `SELECT * FROM events WHERE stream_id = ? AND version > ? ORDER BY version`. Snapshot — отдельная таблица.

### Специализированные event store

EventStoreDB (open source) — база, спроектированная только под event sourcing. Три преимущества над PostgreSQL:

Подписки на события (catch-up subscriptions). Проекция подписывается: «дай все события с позиции N и далее в реальном времени». EventStoreDB поддерживает это нативно. В PostgreSQL нужен polling (`SELECT ... WHERE id > last_seen`) или LISTEN/NOTIFY. Polling добавляет задержку, NOTIFY не гарантирует доставку при переподключении.

Глобальный порядок. Все события всех потоков имеют глобальную позицию. Проекция, которая строит read-модель по событиям из разных потоков (заказы + платежи + доставка), читает единый упорядоченный поток. В PostgreSQL `BIGSERIAL` даёт примерный порядок, но при конкурентных транзакциях — не строгий (транзакция с id=100 может закоммититься после id=101).

Проекции как first-class citizen. Встроенный механизм для определения проекций прямо в базе. На практике проекции обычно живут в коде приложения.

Для большинства систем PostgreSQL как event store достаточен. EventStoreDB оправдан, когда event sourcing — центральный паттерн всей системы (финтех, банкинг, букмекерские платформы).

## Подводные камни

Архитектура описана — но production добавляет проблемы, к которым нужно быть готовым.

### Idempotency проекций

Проекция читает событие из очереди и обновляет read-модель. Очередь доставила событие дважды — стандартное поведение при [at-least-once delivery](delivery-guarantees.md). Для `UPDATE status = 'shipped'` повторное применение безвредно — идемпотентная операция. Но если проекция считает агрегат:

```ruby
# Событие: OrderCompleted {seller_id: 7, total: 8500}
# Проекция:
SellerStats.increment(:revenue, event.data[:total])
# Дубль: revenue += 8500 ещё раз — выручка завышена
```

Решение — проекция хранит `last_processed_event_id`. Перед обработкой проверяет: событие уже обработано? Если да — пропускает. Тот же принцип [idempotency](reliability-patterns.md), но на стороне consumer-а.

```ruby
def handle(event)
  return if already_processed?(event.id)

  case event.type
  when "order.completed"
    SellerStats.increment(:revenue, event.data[:total])
  end

  mark_processed(event.id)
end
```

### Ordering между потоками

События одного потока (заказа) упорядочены: version 1, 2, 3. Но если проекция зависит от событий из разных потоков — порядок не гарантирован. `UserRenamed {user_id: 7}` может прийти раньше `OrderCreated {user_id: 7}` или позже. Проекция должна корректно обрабатывать события в любом порядке между потоками. На практике это означает: проекция обновляет данные по мере поступления, и eventual consistency приводит к корректному состоянию — `UserRenamed` обновит имя, когда придёт, независимо от порядка.

### Сломанная проекция

Баг в коде проекции. Три дня неправильно считала revenue. Данные в read-модели испорчены. В обычной системе — писать миграцию, вычислять правильные значения, проверять вручную. В event sourcing — replay: исправить код проекции, очистить read-модель, прогнать все события с начала. Read-модель восстановлена корректно.

Цена: replay миллионов событий занимает время. На это время read-модель недоступна или показывает частичные данные. На практике часто делают параллельный rebuild: строят новую read-модель рядом со старой и переключают трафик, когда новая догнала поток событий.

### Версионирование событий

Событие `OrderCreated` с полем `amount` опубликовано, consumer-ы от него зависят. Решили переименовать `amount` в `total` — старые события в логе записаны с `amount`. Нельзя просто мигрировать, как ALTER TABLE. Решение — upcasting: трансформер, который при чтении старого события приводит его к новой версии. Operational overhead, который нужно учитывать при проектировании событий как контрактов.

## Стоимость event sourcing поверх CQRS

Event sourcing добавляет стоимость не в виде eventual consistency (она определяется очередью, одинакова что с ES, что без), а в виде: версионирования событий (upcasting при изменении контракта), snapshot-ов (когда создавать, как хранить, когда инвалидировать), размера хранилища (10-20 событий на сущность vs одна мутабельная строка).

Взамен даёт возможность, которой CQRS без ES не имеет: replay. Сломалась проекция — пересобрал с нуля. Появился новый consumer через полгода — прогнал все исторические события. В CQRS без ES для этого нужен отдельный ETL (Extract-Transform-Load) — ручной пайплайн экспорта данных.

## Когда что выбирать

```
                     PG + replica       CQRS              CQRS + ES
────────────────────────────────────────────────────────────────────────
Write-модель         мутабельная        мутабельная        append-only
                     (UPDATE)           (UPDATE)           (events)

Read-модель          та же схема        отдельные          отдельные
                     (на реплике)       проекции           проекции

Consistency          replication lag    eventual           eventual
(read vs write)                        (очередь)          (очередь)

OLTP write           обычный            обычный            append + snapshot
OLTP read            обычный            из read-модели     snapshot + replay
                                       или write-модели   или read-модели

История              нет (или audit)    нет (или audit)    полная, из коробки
Replay               невозможен         невозможен         возможен
Новый consumer       нужен свой ETL     нужен свой ETL     replay с начала

Когда выбирать       один паттерн       разные паттерны    история = бизнес-
                     чтения,            чтения,            требование,
                     нагрузка в рамках  нагрузка на        аудит, replay,
                     одной БД           чтение >> запись    растущее число
                                                           потребителей
────────────────────────────────────────────────────────────────────────
```

## Sources

- Young, 2010, *CQRS Documents* — оригинальное описание паттерна CQRS
- Kleppmann, 2017, *Designing Data-Intensive Applications*, Chapters 11-12 — event sourcing, stream processing, derived data
- Fowler, 2011, *Event Sourcing* — описание паттерна и trade-offs
- Richardson, 2018, *Microservices Patterns* — CQRS и event sourcing в контексте микросервисов
- Meyer, 1988, *Object-Oriented Software Construction* — CQS (Command Query Separation)
