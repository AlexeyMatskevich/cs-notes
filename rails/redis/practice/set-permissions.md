# Система прав доступа с пересечениями

**Предпосылки:** [Клиенты и соединения](../00-clients-and-connections.md), [SET](../../../databases/redis/data-structures/03-set.md).

SaaS-платформа управляет доступом к фичам. У каждого тарифного плана — набор разрешений. У пользователя может быть несколько ролей. Нужно быстро проверять «имеет ли пользователь право X?» и вычислять итоговый набор прав без загрузки всего в Ruby.

LIST не подходит: проверка `SISMEMBER` — O(1), проверка в LIST — O(n). LIST допускает дубликаты — добавление одного и того же разрешения дважды приведёт к дублям. HASH не подходит: нет встроенных операций пересечения и объединения. ZSET — score не нужен.

SET даёт O(1) проверку принадлежности и серверные операции над множествами:

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
  def can?(user_id, permission)
    @redis.with do |r|
      roles = r.smembers("user:#{user_id}:roles")
      role_keys = roles.map { |role| "role:#{role}:permissions" }
      return false if role_keys.empty?

      # SUNIONSTORE объединяет все разрешения всех ролей в одно множество
      tmp_key = "tmp:perms:#{user_id}:#{SecureRandom.hex(4)}"
      r.sunionstore(tmp_key, *role_keys)
      result = r.sismember(tmp_key, permission)
      r.del(tmp_key)
      result
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

`SINTER` (пересечение), `SUNION` (объединение) и `SDIFF` (разность) выполняются на сервере за один round-trip. Альтернатива — загрузить оба набора в Ruby и вычислить пересечение в памяти приложения — это дороже по трафику и CPU.

Подробнее: [SET](../../../databases/redis/data-structures/03-set.md).
