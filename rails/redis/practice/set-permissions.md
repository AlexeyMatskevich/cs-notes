# Система прав доступа с пересечениями

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [SET](../../../databases/redis/data-structures/03-set.md).

SaaS-платформа управляет доступом к фичам. У каждого тарифного плана — набор разрешений. У пользователя может быть несколько ролей. Нужно быстро проверять «имеет ли пользователь право X?» и вычислять итоговый набор прав без загрузки всего в Ruby.

LIST не подходит: проверка `SISMEMBER` — O(1), проверка в LIST — O(n). LIST допускает дубликаты — добавление одного и того же разрешения дважды приведёт к дублям. HASH не подходит: нет встроенных операций пересечения и объединения. ZSET — score не нужен.

SET даёт O(1) проверку принадлежности и серверные операции над множествами. Здесь полезно разделить два вопроса: проверка одного конкретного права и получение полного набора прав. Для первого не нужен временный union-ключ; для второго пригодятся `SUNION`, `SINTER` и `SDIFF`.

```ruby
class PermissionManager
  def initialize(redis_pool)
    @redis = redis_pool
  end

  # При назначении роли
  def grant_role(user_id, role)
    @redis.with { |r| r.sadd("user:#{user_id}:roles", role) }
  end

  # Проверка конкретного разрешения по всем ролям пользователя
  # Роли обычно немногочисленны, поэтому достаточно pipelined SISMEMBER
  def can?(user_id, permission)
    @redis.with do |r|
      roles = r.smembers("user:#{user_id}:roles")
      return false if roles.empty?

      checks = r.pipelined do |pipe|
        roles.each do |role|
          pipe.sismember("role:#{role}:permissions", permission)
        end
      end

      checks.any?
    end
  end

  # Полный итоговый набор прав — например, для админки или отладки
  def effective_permissions(user_id)
    @redis.with do |r|
      roles = r.smembers("user:#{user_id}:roles")
      role_keys = roles.map { |role| "role:#{role}:permissions" }
      return [] if role_keys.empty?

      r.sunion(*role_keys)
    end
  end

  # Какие общие разрешения у двух планов?
  def common_permissions(plan_a, plan_b)
    @redis.with do |r|
      r.sinter("plan:#{plan_a}:permissions", "plan:#{plan_b}:permissions")
    end
  end

  # Какие разрешения потеряет пользователь при даунгрейде?
  def permissions_lost(current_plan, downgrade_plan)
    @redis.with do |r|
      r.sdiff("plan:#{current_plan}:permissions", "plan:#{downgrade_plan}:permissions")
    end
  end
end
```

[`SINTER`](../../../databases/redis/data-structures/03-set.md) (пересечение), `SUNION` (объединение) и `SDIFF` (разность) выполняют саму операцию на стороне Redis. Клиент получает уже готовый результат, а не собирает его поэлементно в Ruby.

Метод `can?` не пишет временные ключи и сводит проверки по ролям в один [pipeline](../../../databases/redis/architecture/02-pipelining.md). Если таких проверок очень много, итоговый набор прав обычно материализуют в отдельный `user:*:permissions` и пересобирают при изменении ролей.
