# Сигналы и deploy

**Предпосылки:** [Sidekiq: retry и обработка ошибок](03-retry-and-errors.md), [сигналы](../../linux/programming/00-signals.md).

<- [Retry и обработка ошибок](03-retry-and-errors.md) | [Дизайн задач](05-job-design.md) ->

Retry обрабатывает ошибки: email-сервис вернул 500 → подождать → попробовать снова. Но причина ошибки может быть не во внешнем сервисе, а в самом коде — баг, который нужно исправить и задеплоить. Deploy означает перезапуск Sidekiq-процесса. В этот момент несколько потоков могут выполнять задачи. Как остановить процесс, не потеряв их?

## Сигналы Sidekiq

Sidekiq обрабатывает четыре сигнала, каждый с конкретной ролью:

**TSTP** — «тихий режим» (quiet). Процесс перестаёт забирать новые задачи из Redis, но дорабатывает текущие. Это первый шаг [graceful shutdown](../../linux/programming/00-signals.md#практические-паттерны): прекратить приём, завершить начатое.

**TERM** и **INT** — начать shutdown. Sidekiq ждёт завершения текущих задач в течение timeout (по умолчанию 25 секунд). Если задачи не завершились за это время — принудительная остановка потоков и `bulk_requeue`: незавершённые задачи возвращаются в Redis. Задача, прерванная на середине, выполнится заново — нужна идемпотентность.

**TTIN** — вывести backtrace всех потоков в лог. Полезно для отладки: какой поток завис, на каком вызове.

В многопоточном процессе обработка сигналов требует осторожности: [обработчик сигнала ограничен async-signal-safe операциями](../../linux/programming/00-signals.md#async-signal-safety-почему-printf-в-обработчике--deadlock) — нельзя захватывать мьютексы, выделять память, писать в лог. Sidekiq решает это через self-pipe trick: обработчик записывает байт в pipe (единственная операция — `write`, которая async-signal-safe), а основной поток читает из pipe в event loop и выполняет всю логику без ограничений.

## Последовательность deploy

Правильный deploy — два шага:

```
1. TSTP → процесс перестаёт забирать задачи
2. Deploy нового кода (занимает время)
3. TERM → старый процесс начинает shutdown
4. Новый процесс запускается с новым кодом
```

Зачем два шага вместо одного `TERM`? Между `TERM` и фактической остановкой есть только timeout (25 секунд). Если deploy занимает 30 секунд, а задача — 20, одного `TERM` недостаточно: задача не завершится до timeout. `TSTP` в начале deploy даёт задачам время на завершение, пока код ещё компилируется и копируется.

```bash
# Начало deploy
kill -TSTP $(cat tmp/pids/sidekiq.pid)

# ... deploy происходит ...

# Конец deploy
kill -TERM $(cat tmp/pids/sidekiq.pid)
# Подождать timeout + запас
sleep 30
# Запустить новый процесс
bundle exec sidekiq -d
```

## Настройка timeout

```yaml
# config/sidekiq.yml
:timeout: 25  # секунд на завершение после TERM
```

Timeout — компромисс. Слишком короткий — задачи прерываются и возвращаются в очередь (дубликаты). Слишком длинный — deploy затягивается. 25 секунд — разумный default для большинства задач.

## Lifecycle events

Sidekiq предоставляет хуки на ключевые моменты жизненного цикла процесса:

```ruby
Sidekiq.configure_server do |config|
  config.on(:startup)  { puts "Process ready" }
  config.on(:quiet)    { puts "TSTP received, finishing current jobs" }
  config.on(:shutdown) { puts "TERM received, shutting down" }
end
```

## SIGKILL: когда graceful shutdown невозможен

`SIGKILL` (`kill -9`) нельзя перехватить — процесс убивается мгновенно. Никакого `bulk_requeue`, никакого graceful shutdown. В OSS: задачи, забранные через `BRPOP`, потеряны. В Pro с SuperFetch: задачи остаются в приватных очередях и будут восстановлены другими процессами (orphan recovery).

OOM-killer ядра Linux отправляет `SIGKILL` — то есть ведёт себя как `kill -9`. Для Sidekiq это означает: если процесс потребляет слишком много памяти, задачи пропадут без предупреждения.

<details>
<summary>IterableJob: безопасная остановка длинных задач (Sidekiq 7.3+)</summary>

Обычная задача при получении `TSTP`/`TERM` продолжает выполняться до завершения или до timeout. Если задача обрабатывает 100 000 записей и дошла до 50 000-й — при shutdown прогресс теряется, задача начнёт сначала.

`IterableJob` решает это через cursor-based итерацию:

```ruby
class ReindexJob
  include Sidekiq::IterableJob

  def build_enumerator(user_id, cursor:)
    active_record_records_enumerator(
      User.find(user_id).posts,
      cursor: cursor  # начать с сохранённой позиции
    )
  end

  def each_iteration(post)
    post.reindex!
  end

  def on_complete
    Rails.logger.info "Reindexing finished"
  end
end
```

При получении сигнала текущая итерация завершается, cursor сохраняется. При перезапуске задача продолжает с сохранённого места — не с начала.

Ограничение важно проговорить явно: каждая отдельная итерация всё равно должна укладываться в shutdown timeout. Если одна итерация сама работает дольше `-t` секунд, supervisor может добить процесс `SIGKILL`, и прогресс откатится к последнему сохранённому cursor.

</details>

---

Один job работает корректно: retry, shutdown, deploy — покрыто. Теперь представим задачу крупнее: обработка заказа включает резервирование товара, списание оплаты, email и аналитику. Четыре действия в одном `perform`. Аналитика падает — retry перезапускает весь job, включая списание оплаты. Двойное списание.

---

<- [Retry и обработка ошибок](03-retry-and-errors.md) | [Дизайн задач](05-job-design.md) ->

## Sources

- [Sidekiq Wiki — Signals](https://github.com/sidekiq/sidekiq/wiki/Signals)
- [Sidekiq Wiki — Deployment](https://github.com/sidekiq/sidekiq/wiki/Deployment)
- [Sidekiq Wiki — Iteration](https://github.com/sidekiq/sidekiq/wiki/Iteration)
- Mike Perham, [Iteration and Sidekiq 7.3.0](https://www.mikeperham.com/2024/07/03/iteration-and-sidekiq-7.3.0/)
