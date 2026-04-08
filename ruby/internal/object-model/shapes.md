---
tags:
  - domain/ruby
  - theme/internals
  - type/concept
aliases:
  - shapes
  - shape_id
  - object shapes
order: 6
---

# Формы объектов

**Предпосылки:** [Объекты и классы](objects-and-classes.md) — RObject, массив значений ivar, RBasic, shape_id (кратко).

← [Модули](modules.md) | [Диспетчеризация методов](../methods/method-dispatch.md) →

В [заметке об объектах](objects-and-classes.md) мы видели, что `RObject` хранит массив *значений* инстанс-переменных — без имён. `"Leonhard"` лежит в ячейке 0, `"Euler"` — в ячейке 1. Но как Ruby узнаёт, что `@first_name` — это ячейка 0, а `@last_name` — ячейка 1?

## Имя → индекс: хеш-таблица на класс

До Ruby 3.2 каждый класс хранил хеш-таблицу `iv_index_tbl`, которая сопоставляла имена переменных с индексами в массиве:

```
Mathematician
  iv_index_tbl: { @first_name → 0, @last_name → 1 }

euler:  ivar_array = ["Leonhard", "Euler"]
euclid: ivar_array = ["Euclid",  nil     ]
```

Все экземпляры класса ссылались на одну таблицу. При чтении `@first_name` Ruby искал имя в хеше, получал индекс 0 и читал значение из `ivar_array[0]`.

Это работает. Но каждое обращение к переменной — поиск в хеш-таблице. `attr_reader` в горячем цикле вызывается миллионы раз — hash lookup на каждый вызов заметен. Можно ли запомнить ответ?

## Идея кеша и его проблемы

Идея: инструкция `getinstancevariable` запоминает результат — «`@first_name` лежит по индексу 0». При следующем вызове — сразу `ivar_array[0]`, без хеша. Но кеш может оказаться неправильным. Вот три конкретные ситуации.

**Объект эволюционирует.** Ленивая инициализация — частый паттерн:

```ruby
class Mathematician
  attr_accessor :first_name, :last_name

  def department
    @department ||= "Mathematics"
  end
end

euler = Mathematician.new
euler.first_name = "Leonhard"
euler.last_name = "Euler"
# У euler два ivar: @first_name(индекс 0), @last_name(индекс 1)

euler.department
# Теперь три: @first_name(0), @last_name(1), @department(2)
# Структура объекта изменилась
```

Если инструкция закешировала ответ для объекта с двумя переменными, а после вызова `department` у объекта стало три — кеш может быть устаревшим. В данном случае индексы `@first_name` и `@last_name` не изменились, но кеш этого не знает — ему нужен способ проверить.

**Разные объекты — разная структура.** Если в классе есть условная инициализация:

```ruby
class Mathematician
  def initialize(famous:)
    @first_name = nil
    @last_name = nil
    @awards = [] if famous  # не у всех есть @awards
  end
end

euler = Mathematician.new(famous: true)   # 3 ivar
gauss = Mathematician.new(famous: false)  # 2 ivar
```

Один и тот же метод `full_name` вызывается то на euler (три переменные), то на gauss (две). Кеш настроился на одного — промахнулся на другом.

**Разный порядок — разные индексы.** Самая опасная ситуация:

```ruby
m1 = Mathematician.new
m1.first_name = "Leonhard"  # @first_name → индекс 0
m1.last_name = "Euler"      # @last_name  → индекс 1

m2 = Mathematician.new
m2.last_name = "Gauss"      # @last_name  → индекс 0
m2.first_name = "Carl"      # @first_name → индекс 1
```

У m1 `@first_name` на позиции 0, у m2 — на позиции 1. Если кеш запомнил «`@first_name` = индекс 0» по m1, то при обращении к m2 вернёт `@last_name`. Это не просто промах — это неправильный ответ.

Кешу нужен **ключ валидации** — одно число, которое полностью описывает структуру объекта (какие переменные, в каком порядке). Если ключ совпал — кешированный индекс верный. Если нет — пересчитать. Такой ключ должен сравниваться за одну операцию и быть одинаковым у объектов с одинаковой структурой.

## Формы (shapes)

С Ruby 3.2 появились object shapes. Shape — описание структуры объекта: какие переменные, в каком порядке. Каждый объект несёт идентификатор своей формы (`shape_id`) в заголовке — упакован в верхние биты `RBasic.flags` на 64-битных системах, без дополнительного расхода памяти.

Shapes образуют глобальное дерево переходов. Корень — пустая форма (нет переменных). Каждый переход — добавление одной переменной:

```
root (нет переменных)
  └─ @first_name → shape A (index=0)
       └─ @last_name → shape B (index=1)
```

Когда euler получает `@first_name`, его `shape_id` переходит от root к shape A. Когда получает `@last_name` — от A к B. Каждый переход записывает имя переменной и её индекс в массиве.

`shape_id` полностью описывает структуру. Это и есть ключ валидации: если `cached_shape_id == object.shape_id` — структура не изменилась, кешированный индекс верный.

Важное свойство: формы не привязаны к классу. Два объекта разных классов, получившие одинаковые переменные в одинаковом порядке, разделяют одну форму:

```ruby
class Mathematician; attr_accessor :first_name, :last_name; end
class Physicist;     attr_accessor :first_name, :last_name; end

euler  = Mathematician.new; euler.first_name = "Leonhard"; euler.last_name = "Euler"
newton = Physicist.new;     newton.first_name = "Isaac";    newton.last_name = "Newton"
# Оба → shape B (одинаковые переменные, одинаковый порядок)
```

Проверить можно через `ObjectSpace.dump` — у обоих объектов одинаковый `shape_id`, хотя классы разные.

Вернёмся к трём проблемным ситуациям и проверим, как формы их решают:

- **Объект эволюционирует** (`@department` добавлен): `shape_id` изменился (B → C). Кеш промахивается, пересчитывается для нового shape. Следующие вызовы попадают.
- **Разная структура** (euler с `@awards`, gauss без): разные `shape_id`. Кеш промахивается при переключении между объектами, пересчитывается. Каждый промах стоит одного пересчёта.
- **Разный порядок** (m1: first→last, m2: last→first): это *разные ветки* дерева, *разные `shape_id`*, *разные индексы*. Кеш не может ошибиться — `shape_id` не совпадёт, произойдёт пересчёт с правильным индексом.

Ни один из сценариев не приведёт к ошибке. В худшем случае — промах, пересчёт и обновление кеша.

Внутри Ruby форма (`rb_shape_t` в `shape.h`) хранит три ключевых поля: `parent_id` (родитель в дереве переходов), `edge_name` (имя переменной этого перехода) и `next_field_index` (индекс в массиве значений).

## Инлайн-кеш в действии

Дизассемблер показывает, как байткод использует этот механизм:

```ruby
code = 'def full_name; "#{@first_name} #{@last_name}"; end'
puts RubyVM::InstructionSequence.compile(code).disasm
```

```
== disasm: #<ISeq:full_name@<compiled>:1 (1,0)-(1,46)>
0000 getinstancevariable                    :@first_name, <is:0>
...
0009 getinstancevariable                    :@last_name, <is:1>
...
```

У каждой инструкции `getinstancevariable` два операнда: имя переменной (`:@first_name`) и кеш-слот (`<is:0>`, `<is:1>`). Именно в этом слоте и хранится пара `(shape_id, index)`.

По идее это похоже на [аппаратные кеши процессора](../../../computer/data-path/memory-hierarchy.md) — запомнить результат дорогого поиска, но не путать: shape cache — software-уровень.

Теперь разберём, как работает `getinstancevariable :@first_name, <is:0>`:

1. VM читает `shape_id` объекта из заголовка.
2. Из кеш-слота `<is:0>` атомарно читает пару `(cached_shape_id, cached_index)`, упакованную в одно 64-битное число.
3. Сравнение: `cached_shape_id == shape_id`?
4. **Попадание:** `ivar_array[cached_index]` — одно сравнение целых чисел + одно чтение из массива. Всё.
5. **Промах:** VM ищет `@first_name` по дереву форм от текущей, находит индекс, записывает новую пару `(shape_id, index)` в кеш-слот.

В `vm_insnhelper.c` это выглядит так: `vm_getivar()` на строке 1312 выполняет `if (LIKELY(cached_id == shape_id))` — и при совпадении сразу на строке 1319 возвращает `ivar_list[index]`. При промахе вызывается `fill_ivar_cache()` (строка 1238), которая записывает новый результат.

Кеш-слот (`iseq_inline_iv_cache_entry` в `vm_core.h`) — одно 64-битное число, в которое упакованы `shape_id` (32 бита) и `index` (16 бит). Два `getinstancevariable` в методе `full_name` — два независимых кеш-слота (`<is:0>` и `<is:1>`), каждый кеширует свою переменную.

`attr_reader :first_name` работает по тому же пути. Разница — кеш хранится не в кеш-слоте ISeq, а в `rb_callcache` — структуре, связанной с вызовом метода (подробнее в [заметке о диспетчеризации](../methods/method-dispatch.md)). При диспетчеризации типа IVAR вызывается та же `vm_getivar()`, но кешированная пара берётся из другого места.

Запись ivar (`setinstancevariable`) устроена аналогично. Дополнительная оптимизация: если текущая форма объекта — прямой родитель целевой формы (shape A, а кеш помнит shape B, дочерний от A), VM выполняет переход за один шаг — без полного пересчёта. Это типичная ситуация при первом присвоении `@department` объекту, у которого уже есть `@first_name` и `@last_name`.

## Когда формы не спасают: вариации и too complex

Кеш промахивается при каждой смене `shape_id`, но после пересчёта снова попадает. Проблема начинается, когда стабильного состояния нет.

Если объекты одного класса инициализируются по-разному — разный набор переменных, разный порядок присваивания — каждый вариант порождает отдельную ветку дерева форм. Ruby считает количество «вариаций» для каждого класса. Когда вариаций становится больше восьми (`SHAPE_MAX_VARIATIONS` в `shape.h`), Ruby выдаёт предупреждение и переводит новые объекты в состояние «too complex». Такой объект хранит переменные в персональной хеш-таблице — по сути возврат к подходу с хеш-таблицей, но на уровне каждого объекта, а не класса:

```ruby
Warning[:performance] = true

class Flexible
  def initialize(attrs)
    attrs.each { |k, v| instance_variable_set(:"@#{k}", v) }
  end
end

9.times { |i| Flexible.new({"var_#{i}" => i}) }
# warning: The class Flexible reached 8 shape variations,
#   instance variables accesses will be slower and memory usage increased.
#   It is recommended to define instance variables in a consistent order,
#   for instance by eagerly defining them all in the #initialize method.
```

Каждый вызов с уникальным набором ключей — это новая ветка дерева. Девять вариантов — больше порога.

Решение: инициализировать все переменные явно в `initialize`, даже если значение `nil`. Тогда все объекты класса проходят одинаковый путь и разделяют одну форму:

```ruby
class Mathematician
  def initialize
    @first_name = nil
    @last_name = nil
    @department = nil
  end
end
```

## Встроенное и внешнее хранение

Горячий путь кеша заканчивается чтением `ivar_array[index]`. Но где именно лежит этот массив — зависит от количества переменных объекта.

Когда объект создаётся, GC выделяет слот определённого размера. Если переменных немного — массив значений встроен прямо в слот (embedded storage). Когда переменных становится больше, чем помещается — Ruby выносит массив в отдельный участок памяти (heap storage). С Ruby 3.2 GC выделяет слоты разного размера — [Variable Width Allocation](../gc.md) (VWA) — чтобы объекты с бóльшим числом переменных помещались в один слот без выноса массива в heap. Форма отслеживает, в каком пуле находится объект — через часть битов `shape_id`.

[YJIT](../jit.md) — JIT-компилятор CRuby — использует формы ещё эффективнее: при компиляции горячего метода он проверяет ожидаемый `shape_id` и затем читает ivar по заранее известному смещению прямо из машинного кода.

## Sources

- Jemma Issroff, 2022, «Implementing Object Shapes in CRuby» — RubyKaigi talk, введение shapes в CRuby.
- Chris Seaton, 2015, «Specialising Dynamic Techniques for Implementing the Ruby Programming Language» — PhD thesis, оригинальная идея shapes для Ruby.
- Исходники Ruby (коммит `0d4538b57d`, 2026-01-10): `shape.h` (rb_shape_t, shape_id_t, SHAPE_MAX_VARIATIONS, rb_attr_index_cache), `shape.c` (дерево переходов, вариации, performance warning), `vm_insnhelper.c` (vm_getivar — hot path, fill_ivar_cache — заполнение при промахе), `vm_core.h` (iseq_inline_iv_cache_entry), `insns.def` (getinstancevariable, setinstancevariable).

---

← [Модули](modules.md) | [Диспетчеризация методов](../methods/method-dispatch.md) →
