# Модули

**Предпосылки:** [Объекты и классы](00-objects-and-classes.md) — RClass, таблица методов, указатель super, метакласс.

← [Объекты и классы](00-objects-and-classes.md) | [Формы объектов](02-shapes.md) →

В [предыдущей заметке](00-objects-and-classes.md) мы видели, что класс — это объект с таблицей методов, таблицей констант и указателем `super` на суперкласс. Наследование через `super` позволяет подклассу использовать методы родителя. Но что если нужно разделить поведение между классами, которые не связаны наследованием?

`Mathematician < Person`, `Biologist < Person`. Оба могут быть профессорами — читать лекции, иметь титул. Вынести это в `Person`? Нет — не все люди профессора. Создать общего предка? Ruby не поддерживает множественное наследование классов. Решение — модуль.

## Модуль — это класс

```ruby
module Professor
  def lectures; end
end
```

Внутри Ruby модуль представлен точно так же, как класс: структура `RClass` с таблицей методов (`m_tbl`), таблицей констант (`const_tbl`) и указателем `super`. Отличие — флаг типа `T_MODULE` вместо `T_CLASS`. У модуля нельзя вызвать `new` (этот метод принадлежит классу `Class`, а не `Module`), нельзя указать суперкласс. Но внутренняя структура — одинаковая:

```ruby
Professor.class      # => Module
Mathematician.class  # => Class
# Оба — RClass внутри, оба хранят методы в m_tbl

Professor.instance_methods(false)  # => [:lectures]
# m_tbl модуля содержит его собственные методы
```

## Include: модуль в цепочке предков

```ruby
class Person
  attr_accessor :first_name, :last_name
end

class Mathematician < Person
  include Professor
end
```

Что делает `include`? Ruby создаёт **included class** — обёртку (внутренний тип `T_ICLASS`, included class — класс-обёртка для включённого модуля), которая **разделяет** таблицу методов с оригинальным модулем. Не копирует — именно разделяет. Эта обёртка вставляется в цепочку `super` между классом и его прежним суперклассом:

```
до include:   Mathematician → Person → Object
после:        Mathematician → Professor(iclass) → Person → Object
```

Цепочку видно через `ancestors`:

```ruby
Mathematician.ancestors
# => [Mathematician, Professor, Person, Object, Kernel, BasicObject]
```

В цепочке появились два незнакомых имени. `BasicObject` — корень иерархии, суперкласс `Object`. `Kernel` — модуль, включённый в `Object`. Именно в `Kernel` живут методы `puts`, `p`, `print` — поэтому они доступны отовсюду: любой объект наследует от `Object`, а `Object` включает `Kernel`.

Поскольку обёртка **разделяет** таблицу методов с оригинальным модулем, добавление метода в модуль после `include` сразу делает его доступным во всех включивших классах — Ruby не копирует методы, а ссылается на одну и ту же таблицу.

### Несколько модулей

Если включить два модуля, каждый вставляется в цепочку по очереди. Последний включённый оказывается ближе к классу — и его методы находятся первыми:

```ruby
class Mathematician < Person
  include Professor  # вставлен первым → дальше от класса
  include Employee   # вставлен вторым → ближе к классу
end

Mathematician.ancestors
# => [Mathematician, Employee, Professor, Person, Object, Kernel, BasicObject]
```

Если у `Employee` и `Professor` есть метод с одинаковым именем — победит `Employee`.

### Включение модуля в модуль

Модулю нельзя указать суперкласс (`module Professor < Employee` — ошибка). Но можно включить один модуль в другой:

```ruby
module Employee
  def hire_date; end
end

module Professor
  include Employee
end

class Mathematician < Person
  include Professor
end

Mathematician.ancestors
# => [Mathematician, Professor, Employee, Person, Object, Kernel, BasicObject]
```

Ruby проходит по всем модулям, включённым в `Professor`, и вставляет обёртки для каждого. `Employee` оказывается в цепочке сразу за `Professor`.

С Ruby 3.0 это работает и в обратную сторону: если `Professor` уже включён в `Mathematician`, а затем вы включаете `Employee` в `Professor` — `Mathematician` увидит методы `Employee`. Ruby теперь хранит список всех классов, включивших модуль, и при изменении модуля пропагирует новые включения ко всем из них.

## Поиск метода: прогулка по цепочке super

Мы видели, как модули встраиваются в цепочку `super`. Теперь проследим, как Ruby проходит по этой цепочке при вызове метода. Создадим математика и зададим имя:

```ruby
ramanujan = Mathematician.new
ramanujan.first_name = "Srinivasa"
```

Как Ruby находит `first_name=`? Получает класс объекта (`Mathematician`) и начинает прогулку по цепочке `super`:

```
Mathematician  →  m_tbl: {}           → нет
Professor      →  m_tbl: {lectures}   → нет
Person         →  m_tbl: {first_name=, first_name, last_name=, last_name}  → есть!
```

Алгоритм — один цикл по связному списку: взять `m_tbl` текущего узла → проверить → не нашли → перейти по `super` → повторить. Классы и модули (точнее, их обёртки) в этом цикле неразличимы — у всех одна и та же структура `RClass` с `m_tbl` и `super`. Так Ruby достигает эффекта множественного наследования: модули добавляют методы в плоский список, а алгоритм поиска остаётся простым.

Когда метод найден, VM определяет, как его вызвать: создать фрейм и исполнить ISeq (Ruby-метод), вызвать C-функцию напрямую (встроенный метод) или прочитать переменную без фрейма (`attr_reader`). Подробности — в [заметке о диспетчеризации](../methods/00-method-dispatch.md).

## Prepend: модуль перед классом

`include` ставит модуль *за* классом в цепочке — методы класса находятся первыми. Иногда нужно наоборот.

Допустим, `Professor` хочет добавлять титул «Prof.» к имени:

```ruby
module Professor
  def name
    "Prof. #{super}"
  end
end

class Mathematician
  attr_accessor :name
  include Professor
end

poincare = Mathematician.new
poincare.name = "Henri Poincaré"
poincare.name  # => "Henri Poincaré"  ← без титула!
```

При `include` модуль оказался за классом. Ruby нашёл `name` из `attr_accessor` в `Mathematician` и не дошёл до `Professor`. Замена `include` на `prepend` решает проблему:

```ruby
class Mathematician
  attr_accessor :name
  prepend Professor
end

poincare = Mathematician.new
poincare.name = "Henri Poincaré"
poincare.name  # => "Prof. Henri Poincaré"

Mathematician.ancestors
# => [Professor, Mathematician, Object, Kernel, BasicObject]
```

`prepend` ставит модуль *перед* классом. Как это работает внутри? Ruby создаёт **origin class** — переносит собственные методы класса в отдельную копию и вставляет её после модуля:

```
Mathematician(оболочка) → Professor(iclass) → Mathematician(origin, методы) → Object
```

Теперь `Professor#name` найдётся первым. `super` из него приведёт к origin — оригинальному `name` из `attr_accessor`. Снаружи origin невидим: `ancestors` показывает `[Professor, Mathematician, ...]`, скрывая внутреннюю механику.

### Extend: include в метакласс

Допустим, мы хотим, чтобы методы `Professor` были доступны не экземплярам `Mathematician`, а самому классу — как методы класса. В [предыдущей заметке](00-objects-and-classes.md) мы видели, что методы класса хранятся в метаклассе. `extend` делает именно это — включает модуль в метакласс объекта:

```ruby
class Mathematician
  extend Professor
end

Mathematician.lectures  # метод класса, не экземпляра
```

`extend` на экземпляре работает так же — включает модуль в singleton class этого объекта:

```ruby
ramanujan = Mathematician.new
ramanujan.extend(Professor)
ramanujan.lectures  # метод только этого объекта
```

## Поиск констант: два дерева

Методы Ruby ищет по цепочке `super` — от класса объекта вверх по иерархии наследования. Константы устроены иначе: в `module A; module B; C = 1; end; end` константа `C` принадлежит `B`, а не `A` — хотя `B` не наследует от `A`. Ruby ищет её сначала в `B`, потом в `A` — лексически, по вложенности определений в исходном коде, — и только потом по цепочке `super`. Для этого нужен отдельный механизм, не связанный с таблицей методов.

Каждый раз, когда вы пишете `class` или `module`, Ruby создаёт **лексическую область** (lexical scope) — участок кода, вложенный в предыдущий. Области образуют цепочку вложенности:

```ruby
module Namespace           # область 1: Namespace
  CONST = "hello"
  class MyClass            # область 2: MyClass, вложена в Namespace
    p CONST                # => "hello"
  end
end
```

`MyClass` не наследует от `Namespace` (его суперкласс — `Object`). Тем не менее `CONST` найдена. Ruby нашёл её не по цепочке `super`, а по цепочке лексических областей — от внутренней к внешней.

Внутри VM эта цепочка хранится как связный список **CREF** (Constant Reference — ссылка на область поиска констант, структура `rb_cref_t`): каждый узел содержит текущий класс или модуль и ссылку на внешнюю область. При каждом `class`/`module` Ruby добавляет новый узел в начало списка. В скомпилированных инструкциях обращение к константе — инструкция `opt_getconstant_path`, которая использует CREF текущего фрейма.

Алгоритм поиска константы:

1. Пройти по цепочке CREF (лексические области): для каждой области проверить `const_tbl` соответствующего класса/модуля.
2. Если не нашли — пройти по цепочке `super` (как для методов).

Лексическая область первична:

```ruby
class Superclass
  FIND_ME = "Found in superclass"
end

module Ns
  FIND_ME = "Found in lexical scope"
  class Sub < Superclass
    p FIND_ME
  end
end
# => "Found in lexical scope"
```

`Sub` наследует от `Superclass`, но `FIND_ME` найдена в модуле `Ns` — через лексическую область. Суперкласс проверяется только если лексическая цепочка не дала результата.

### Создание класса = создание константы

Когда вы пишете `class Foo; end` внутри `module Bar`, Ruby делает две вещи: создаёт структуру `RClass` для `Foo` и добавляет константу `Foo` в `const_tbl` модуля `Bar`. Именно поэтому работает запись `Bar::Foo` — это поиск константы `Foo` в `Bar`. Классы и модули — это константы, указывающие на объекты `RClass`.

## Sources

- Pat Shaughnessy, 2013, *Ruby Under a Microscope* — глава 6: модули, поиск методов и констант.
- Исходники Ruby (коммит `0d4538b57d`, 2026-01-10): `class.c` (rb_include_class_new — создание included class; ensure_origin — prepend и origin class; rb_include_module — пропагация к подклассам), `method.h` (rb_cref_t — лексическая область), `vm_insnhelper.c` (vm_get_ev_const — поиск константы).

---

← [Объекты и классы](00-objects-and-classes.md) | [Формы объектов](02-shapes.md) →
