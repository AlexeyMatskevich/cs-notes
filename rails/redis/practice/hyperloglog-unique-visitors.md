---
tags:
  - domain/rails
  - theme/performance
  - type/pattern
aliases:
  - HyperLogLog
  - PFCOUNT
  - PFMERGE
order: 3
---

# Подсчёт уникальных посетителей при 100 000 страниц

**Предпосылки:** [Клиенты и соединения](../clients-and-connections.md), [HyperLogLog](../../../databases/redis/data-structures/hyperloglog.md).

Аналитическая система считает уникальных посетителей по каждой странице сайта за каждый день. Сайт имеет 100 000 страниц и миллионы пользователей. Нужны дневные, недельные и месячные агрегаты.

SET хранит каждый элемент как строку. Миллион user_id в SET — порядка 50 МБ. При 100 000 страниц × 30 дней = 3 миллиона SET'ов — это сотни гигабайт RAM. Bitmap требует числовые ID и отвечает на вопрос «был ли конкретный пользователь?», но не позволяет объединять дневные счётчики в недельные без дублирования. HyperLogLog расходует фиксированные 12 КБ на счётчик независимо от кардинальности, и `PFMERGE` объединяет дневные HLL в недельные с сохранением уникальности:

```ruby
class UniqueVisitorTracker
  def initialize(redis_pool)
    @redis = redis_pool
  end

  def track(page_slug, visitor_id)
    key = "uv:#{page_slug}:#{Date.today.iso8601}"
    @redis.with { |r| r.pfadd(key, visitor_id) }
  end

  def daily_count(page_slug, date)
    key = "uv:#{page_slug}:#{date.iso8601}"
    @redis.with { |r| r.pfcount(key) }
  end

  def count_for_period(page_slug, dates)
    keys = dates.map { |d| "uv:#{page_slug}:#{d.iso8601}" }
    @redis.with do |r|
      # PFCOUNT на нескольких ключах выполняет внутренний merge
      r.pfcount(*keys)
    end
  end

  def site_wide_uniques(date)
    # Объединить HLL по всем страницам за день
    # SCAN вместо KEYS — не блокирует event loop (см. [блокирующие команды](../02-blocking-pitfalls.md))
    page_keys = @redis.with { |r| r.scan_each(match: "uv:*:#{date.iso8601}").to_a }
    return 0 if page_keys.empty?

    @redis.with { |r| r.pfcount(*page_keys) }
  end
end
```

3 миллиона HLL-счётчиков × 12 КБ = 36 ГБ. Те же данные в SET — сотни ГБ. Стандартная ошибка [HyperLogLog](../../../databases/redis/data-structures/hyperloglog.md) — 0.81%. Для аналитических дашбордов, где «≈1 024 000» и «1 024 000» неразличимы, это приемлемо. Для точного ответа «был ли конкретный пользователь на странице?» HLL не подходит — для этого нужен SET или Bitmap.
