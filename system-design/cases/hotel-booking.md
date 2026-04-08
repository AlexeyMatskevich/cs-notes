---
tags:
  - domain/system-design
  - theme/reliability
  - theme/transactions
  - type/case-study
aliases:
  - Hotel Booking System
order: 16
---

# Система бронирования отелей

**Предпосылки:** [HTTP](../../networking/application/http.md), background jobs (Sidekiq), [WebSocket](../../networking/application/websockets.md)/polling, [паттерны надёжности](../reliability-patterns.md) (timeout, retry, circuit breaker, idempotency), базовое понимание транзакций PostgreSQL ([`FOR UPDATE`](../../databases/postgresql/concurrency/patterns.md#пессимистичный-подход-for-update)).

## Сценарий

Пользователь выбрал номер в отеле и нажал «Забронировать». Система должна:

1. Заблокировать номер в Hotel Inventory API (внешний сервис отеля)
2. Списать деньги через Payment API (Stripe)
3. Подтвердить бронирование в Hotel Booking API (внешний сервис отеля)
4. Отправить email-подтверждение
5. Начислить бонусы в Loyalty API (внутренний сервис)

Характеристики внешних сервисов:

| Сервис | Latency (p99) | Надёжность | Idempotency key |
|--------|---------------|------------|-----------------|
| Hotel Inventory API | 2 сек | 99% | Нет |
| Payment API (Stripe) | 500ms | 99.9% | Да |
| Hotel Booking API | 3 сек | 98% | Да |
| Email Service | 200ms | 99.9% | Нет |
| Loyalty API | 100ms | 95% | Нет |

Бизнес-требования: ответ пользователю в течение 10 секунд, потеря email терпима, потеря бонусов терпима (но желательно начислить позже). Деньги нельзя списать без блокировки номера. Hotel Inventory API снимает блокировку автоматически через 15 минут, если не пришло подтверждение.

## Почему не синхронно

Worst case по p99: 2 + 0.5 + 3 + 0.2 + 0.1 = 5.8 секунд. Это только latency — без учёта retry при сбоях. При требовании в 10 секунд синхронная обработка в HTTP-запросе не оставляет запаса на ошибки. Один retry к Hotel Booking API (3 секунды) — и мы за пределами бюджета.

Решение — асинхронная обработка. Контроллер создаёт заказ, ставит задачу в очередь и сразу отвечает клиенту. Клиент отслеживает статус через WebSocket или polling. Ограничение в 10 секунд теперь относится к времени до первого обновления статуса, а не ко всей цепочке операций.

## Архитектура

```
┌──────────┐     POST /bookings      ┌────────────┐
│  Client  │ ───────────────────────>│ Controller │
└──────────┘                         └────────────┘
     │                                     │
     │                            создать Order (new)
     │                            поставить BookingJob
     │                            вернуть 202 Accepted
     │                                     │
     │<────────────── 202 + order_id ──────┘
     │
     │  WebSocket / polling
     v
┌──────────┐                         ┌────────────┐
│  Client  │<─────── статус ─────────│ BookingJob │
└──────────┘                         └────────────┘
                                           │
                           Hotel Inventory API (lock)
                           Payment API (charge)
                           Hotel Booking API (book)
                                           │
                                     ┌─────┴─────┐
                                     v           v
                              EmailJob      LoyaltyJob
```

Три уровня критичности:

- **Критично:** блокировка, оплата, подтверждение — в основном job, при ошибке откатываем
- **Желательно:** email — отдельный job, retry до успеха
- **Опционально:** бонусы — отдельный job, если Loyalty API нестабилен — не блокируем основной флоу

Email и Loyalty в отдельных jobs — bulkhead: сбой некритичного сервиса не влияет на критичный путь.

## State machine заказа

```
     ┌─────────────────────────────────────┐
     │                                     │
     v                                     │
   [new] ──────> [progress] ──────> [completed]
     │                │
     │                │ (booking failed after charge)
     │                v
     └──────────> [cancelled] <──── [refund_pending]
                                          │
                                          │ (refund succeeded)
                                          v
                                    [cancelled]
```

- `new` — заказ создан, ждёт обработки
- `progress` — блокировка получена, идёт оплата/подтверждение
- `completed` — бронирование подтверждено
- `cancelled` — отменён (не удалось заблокировать, не прошла оплата, или refund завершён)
- `refund_pending` — оплата прошла, но бронирование не удалось; возврат в процессе

Статус `refund_pending` — ключевой. Деньги списаны, брони нет. Система знает о проблеме и будет пытаться вернуть деньги.

## Таймауты

Правило: 2–3× от p99 для большинства сервисов, 3–4× для платежей (критичная операция, лучше подождать).

| Сервис | p99 | Таймаут | Обоснование |
|--------|-----|---------|-------------|
| Hotel Inventory API | 2 сек | 5 сек | 2.5× p99 |
| Payment API | 500ms | 2 сек | 4× p99, критичная операция |
| Hotel Booking API | 3 сек | 7 сек | 2.3× p99, есть idempotency key для retry |
| Email Service | 200ms | 1 сек | 5× p99, некритично |
| Loyalty API | 100ms | 500ms | 5× p99, fail fast для нестабильного сервиса |

## Обработка отказов

### Блокировка не удалась

Номер уже занят или сервис недоступен. Помечаем заказ как `cancelled`, уведомляем пользователя. Деньги не списывали — откатывать нечего.

### Оплата не прошла

Блокировка есть, но Stripe вернул ошибку. Помечаем заказ как `cancelled`. Блокировка снимется автоматически через 15 минут (TTL на стороне Hotel Inventory API).

### Бронирование не удалось после оплаты

Самый сложный случай. Деньги списаны, но Hotel Booking API вернул ошибку (например 15 минут прошло, lock отменен). Пользователь без номера, но с минусом на карте.

```ruby
book = HotelBookingAPI.book(order.room_id, idempotency_key: "book-#{order.id}")

if book.success?
  order.update!(status: :completed)
  broadcast_status(order, "Бронирование подтверждено")
else
  # Бронирование не удалось — возвращаем деньги
  begin
    refund = Stripe::Refund.create(payment_intent: order.payment_id)
    order.update!(status: :cancelled, refund_id: refund.id)
    broadcast_status(order, "Бронирование не удалось, деньги возвращены")
  rescue Stripe::StripeError => e
    # Refund тоже не прошёл
    order.update!(status: :refund_pending)
    RefundRetryJob.perform_async(order.id)
    broadcast_status(order, "Бронирование не удалось, возврат в обработке")
  end
end
```

`RefundRetryJob` — отдельный job с агрессивным retry (больше попыток, дольше пытаться). Цена неуспеха высокая: деньги зависли у пользователя. Если после N попыток refund не прошёл — логируем, алертим, разбираемся вручную.

## Idempotency

Stripe и Hotel Booking API поддерживают idempotency key. Один и тот же `idempotency_key` гарантирует, что операция выполнится не более одного раза, даже если клиент отправит запрос повторно.

```ruby
Stripe::PaymentIntent.create(
  amount: order.amount_cents,
  currency: 'usd',
  idempotency_key: "payment-order-#{order.id}"
)

HotelBookingAPI.book(
  room_id: order.room_id,
  idempotency_key: "book-order-#{order.id}"
)
```

Hotel Inventory API не поддерживает idempotency key. Повторная блокировка того же номера — undefined behavior. Защита на нашей стороне: проверять статус заказа перед вызовом.

## Типичные ошибки

### HTTP-вызов внутри транзакции

```ruby
# ❌ Плохо: HTTP-запрос внутри транзакции
Order.transaction do
  order = Order.lock("FOR UPDATE NOWAIT").find(order_id)
  lock = HotelInventoryAPI.lock(order.room_id)  # 2 секунды
  order.update!(status: :progress) if lock.success?
end
```

Транзакция держит соединение из пула PostgreSQL на время HTTP-вызова. При 10 workers с 2-секундными вызовами — 10 соединений заняты ожиданием сети. При типичном лимите в 20–50 соединений это существенная доля пула. Если HTTP-вызов упадёт — транзакция откатится, но ресурсы уже потрачены.

```ruby
# ✅ Правильно: HTTP-вызов вне транзакции
order = Order.find(order_id)
return if order.completed? || order.cancelled?

lock = HotelInventoryAPI.lock(order.room_id)  # вне транзакции

Order.transaction do
  order.lock!
  return if order.completed? || order.cancelled?  # перепроверка ведь за 2 секунды, состояние order могла изменить соседняя job

  if lock.success?
    order.update!(status: :progress, lock_id: lock.id)
  else
    order.update!(status: :cancelled)
  end
end
```

### Отсутствие перепроверки после блокировки

Между первой проверкой (`order.completed?`) и взятием блокировки (`order.lock!`) проходит время — до 2 секунд на HTTP-вызов. За это время другой процесс мог изменить статус заказа.

```ruby
order = Order.find(order_id)
return if order.completed?  # статус: progress

# ... 2 секунды HTTP-вызова ...
# за это время другой процесс завершил заказ: status = completed

Order.transaction do
  order.lock!
  # без перепроверки: перезапишем completed обратно на progress
  order.update!(status: :progress)  # ❌ потеряли финальный статус
end
```

Перепроверка после `lock!` защищает от этого race condition.

## Применённые паттерны

| Паттерн | Где применён |
|---------|--------------|
| Timeout | Все внешние вызовы, значения 2–4× от p99 |
| Retry with backoff | RefundRetryJob, EmailJob, LoyaltyJob |
| Bulkhead | Email и Loyalty в отдельных jobs |
| Idempotency | Stripe (payment + refund), Hotel Booking API |
| State machine | Order со статусами для отслеживания прогресса и обработки частичных сбоев |

Circuit breaker явно не применён в этом примере, но был бы уместен для Loyalty API (95% надёжность) — чтобы не замедлять обработку при массовых сбоях.
