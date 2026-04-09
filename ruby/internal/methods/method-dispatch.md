---
tags:
  - domain/ruby
  - theme/internals
  - type/concept
aliases:
  - method dispatch
  - method cache
  - inline cache
order: 7
---

# Диспетчеризация методов

> [!info]- Предпосылки
> [Исполнение](../vm/execution.md) — фреймы (METHOD, CFUNC, BLOCK), push/pop, PC/SP/EP. [Объекты и классы](../object-model/objects-and-classes.md) — m_tbl, klass, super, метакласс. [Модули](../object-model/modules.md) — iclass, include/prepend в цепочке super, поиск методов по цепочке. [Формы](../object-model/shapes.md) — shape_id, инлайн-кеш для переменных.

← [Формы объектов](../object-model/shapes.md) | [Определение методов](method-definition.md) →

В [заметке о модулях](../object-model/modules.md) мы видели, как Ruby находит [метод](method-definition.md): начинает с класса получателя, проверяет таблицу методов, не нашёл — переходит по `super` к следующему. Но нашёл — и что дальше? `full_name` определён через `def`, `first_name` — через `attr_reader`, `times` — встроенный C-метод. Все три найдены по одному алгоритму, но вызываются совершенно по-разному. И ещё вопрос: неужели Ruby проходит по цепочке на *каждый* вызов?

## Два шага send

Дизассемблер показывает, что вызов метода — одна инструкция:

```ruby
code = 'euler = Mathematician.new; euler.full_name'
puts RubyVM::InstructionSequence.compile(code).disasm
```

```
0008 opt_send_without_block  <calldata!mid:full_name, argc:0, ARGS_SIMPLE>
```

`opt_send_without_block` — рабочая лошадка вызова методов. За одной инструкцией скрываются два шага: **поиск** (найти метод по имени и получателю) и **диспетчеризация** (вызвать найденный метод подходящим способом). Эти шаги работают по-разному, но вместе образуют полный цикл вызова.

## Поиск метода

Вызов `euler.full_name`. VM берёт класс объекта (`Mathematician`) и начинает обход цепочки `super`:

```
Mathematician  →  m_tbl: {full_name}  → есть!
```

Метод нашёлся сразу. Если бы его не было в `Mathematician`, VM перешёл бы к следующему узлу — модулю или суперклассу — и проверил бы его таблицу. Алгоритм — цикл по связному списку, уже знакомый из [заметки о модулях](../object-model/modules.md):

```
for (; klass; klass = RCLASS_SUPER(klass)) {
    me = lookup_method_table(klass, id);
    if (me) break;
}
```

Каждый узел — обычный `RClass` с таблицей методов (`m_tbl`) и указателем `super`. Include-обёртки (iclass), оригинальные классы от prepend — все неразличимы для этого цикла.

Результат поиска — описание метода (`rb_callable_method_entry_t` в `method.h`). Оно содержит три вещи, которые определят дальнейший путь: **тип** метода (Ruby-код, C-функция, `attr_reader`...), **тело** (ISeq, указатель на C-функцию, имя переменной) и **видимость** (public, private, protected).

### Три разновидности — один механизм

Алгоритм всегда один: взять класс из заголовка объекта и пойти по `super`. Разница — только в том, *какой* класс оказывается стартовой точкой.

**Метод экземпляра.** `euler.full_name` — самый обычный случай. Стартовая точка — класс объекта:

```ruby
Mathematician.ancestors
# => [Mathematician, Person, Object, Kernel, BasicObject]
```

VM проверяет m_tbl в каждом узле по порядку.

**Метод класса.** `Mathematician.field` — вызов на объекте-классе. Класс объекта `Mathematician` — его метакласс:

```ruby
Mathematician.singleton_class.ancestors
# => [#<Class:Mathematician>, #<Class:Person>, #<Class:Object>,
#     #<Class:BasicObject>, Class, Module, Object, Kernel, BasicObject]
```

VM начинает с метакласса `#<Class:Mathematician>` и идёт по цепочке метаклассов вверх. `def self.field` положил метод в `m_tbl` метакласса — поиск найдёт его на первом шаге. «Метод класса» — не отдельный механизм. Это обычный метод экземпляра, который лежит в метаклассе. А `extend Module` — это `include` в метакласс (мы видели это в [заметке о модулях](../object-model/modules.md)).

**Singleton-метод объекта.** `def euler.special` создаёт метод только для одного объекта. Ruby лениво создаёт для `euler` его собственный singleton class и кладёт метод туда:

```ruby
def euler.special; "only euler"; end
euler.singleton_class.ancestors
# => [#<Class:#<Mathematician:0x...>>, Mathematician, Person, Object, Kernel, BasicObject]
```

Стартовая точка — singleton class, затем обычная цепочка класса. Другие экземпляры `Mathematician` не имеют этого singleton class и не видят `special`.

Во всех трёх случаях алгоритм поиска один. Различие — куда указывает `klass` в заголовке объекта: на обычный класс, на метакласс или на singleton class.

## Инлайн-кеш

Обход цепочки на каждый вызов — заметная цена. В горячем цикле `euler.first_name` вызывается миллионы раз, а метод каждый раз лежит в том же месте. Можно ли запомнить результат?

Каждый call site в скомпилированных инструкциях хранит **callcache** (`rb_callcache` в `vm_callinfo.h`) — кеш из трёх полей: класс получателя, найденный метод и указатель на функцию вызова. Callcache — software-аналог [аппаратного кеша](../../../computer/data-path/memory-hierarchy.md): запомнить результат дорогого поиска, чтобы не повторять его при каждом вызове.

Рядом с callcache лежит **callinfo** (`rb_callinfo`) — неизменное описание вызова: имя метода, количество аргументов, флаги (есть ли блок, splat, keyword-аргументы). Callinfo не меняется; callcache обновляется при каждом промахе.

### Горячий путь

При повторном вызове `euler.full_name` VM проверяет кеш за два сравнения:

1. Класс получателя совпадает с кешированным? (`cc->klass == CLASS_OF(recv)`)
2. Метод не был инвалидирован? (`!METHOD_ENTRY_INVALIDATED(cme)`)

Если оба условия выполнены — VM вызывает метод напрямую через сохранённый указатель на функцию (`cc->call_`), без поиска. Это горячий путь — две проверки и переход.

При промахе (другой класс получателя или инвалидированный метод) VM ищет результат в таблице кешей класса (`RCLASS_CC_TBL`). Это второй уровень — медленнее, но быстрее полного обхода. Если и там нет — полный поиск по цепочке `super`, результат записывается обратно в оба кеша.

### Инвалидация

Кеш становится неактуальным, когда меняется набор методов: `define_method`, `include`, `prepend`, `alias`, удаление метода. Ruby не сбрасывает все кеши глобально — вместо этого каждый метод несёт флаг `INVALIDATED`. При изменении Ruby помечает затронутые методы, и при следующем обращении кеш обнаруживает, что метод помечен, и пересчитывается.

Сравнение с кешем переменных (из [заметки о формах](../object-model/shapes.md)): кеш методов ключится на класс получателя и инвалидируется явно (флаг на method entry). Кеш переменных ключится на `shape_id` объекта и инвалидируется неявно (`shape_id` изменился — сравнение не прошло). Кеш методов затрагивает все объекты класса при `include`; кеш переменных — только конкретный объект при добавлении новой переменной.

## Типы методов

Кеш вернул описание метода. Но *что* именно вызывать? `full_name` — Ruby-код с инструкциями YARV. `Array#push` — C-функция. `attr_reader :first_name` — простое чтение переменной. Каждый требует своего пути вызова.

Ruby классифицирует каждый метод одним из двенадцати типов (`rb_method_type_t` в `method.h`). При диспетчеризации VM проверяет тип и переключается на соответствующий путь (`vm_call_method_each_type()` в `vm_insnhelper.c`). Четыре типа покрывают подавляющее большинство вызовов.

## ISEQ: обычный Ruby-метод

```ruby
def full_name
  "#{@first_name} #{@last_name}"
end
```

Тип `VM_METHOD_TYPE_ISEQ`. Самый распространённый путь. VM создаёт METHOD-фрейм: устанавливает PC на начало ISeq метода, выделяет порцию стека для локальных переменных (EP), записывает `self = receiver`. Дальше — обычный цикл «прочитай инструкцию → выполни → сдвинь PC», знакомый из [заметки об исполнении](../vm/execution.md). Когда метод завершается (`leave`) — фрейм снимается, результат на стеке вызывающего.

## CFUNC: C-метод

`Integer#times`, `String#upcase`, `Array#push` — методы, написанные на C и встроенные в Ruby. Тип `VM_METHOD_TYPE_CFUNC`. VM создаёт CFUNC-фрейм (чтобы метод появлялся в backtrace при ошибке) и вызывает C-функцию напрямую. Инструкций YARV нет — C-код делает всю работу и возвращает результат. Когда вы видите `CFUNC` в выводе `caller` — это именно такой вызов.

## IVAR и ATTRSET: без фрейма

```ruby
class Mathematician
  attr_reader :first_name    # создаёт IVAR-метод
  attr_writer :first_name    # создаёт ATTRSET-метод
end
```

`attr_reader` создаёт метод типа `VM_METHOD_TYPE_IVAR`. Его единственная задача — вернуть значение одной инстанс-переменной. Операция настолько проста, что VM **не создаёт фрейм**: снимает получателя со стека, читает переменную через `vm_getivar()` и кладёт результат обратно. Ни PC, ни EP, ни переключения контекста.

`attr_writer` — тип `VM_METHOD_TYPE_ATTRSET`. Аналогично: без фрейма записывает значение через `vm_setivar()`.

Кеш для чтения/записи переменной хранится прямо в callcache — в том же формате `(shape_id, index)`, что и в [заметке о формах](../object-model/shapes.md). Разница с кеш-слотом инструкции `getinstancevariable` — только в том, где лежит кешированная пара: в callcache (для `attr_reader`) или в ISeq (для `getinstancevariable`). Функция чтения — одна и та же `vm_getivar()`.

Разница с `def first_name; @first_name; end` — не только в краткости записи. `def` создаёт ISEQ-метод: при каждом вызове — фрейм, инструкция `getinstancevariable`, возврат. `attr_reader` создаёт IVAR-метод: прямое чтение без фрейма. В дизассемблере оба вызова выглядят одинаково — `opt_send_without_block :first_name`. Разница проявляется только на этапе диспетчеризации, когда VM смотрит на тип найденного метода.

## Видимость

Проверка видимости происходит *после* поиска, но *до* диспетчеризации — внутри `vm_call_method()` (`vm_insnhelper.c`). VM читает видимость из флагов найденного метода и проверяет контекст вызова:

- **public** — вызов разрешён всегда.
- **private** — только без явного получателя. VM проверяет флаг `FCALL` в callinfo: `puts "hello"` — FCALL (неявный `self`), вызов разрешён. `euler.secret` — не FCALL (есть явный `euler.`), вызов запрещён.
- **protected** — получатель должен быть экземпляром того же класса (или подкласса), где метод определён. `rb_obj_is_kind_of(self, defined_class)`.

При нарушении видимости VM не бросает ошибку напрямую — вместо этого вызывает `method_missing` с причиной: `MISSING_PRIVATE` или `MISSING_PROTECTED`. Стандартная реализация `method_missing` в `BasicObject` превращает это в `NoMethodError` с соответствующим сообщением.

```ruby
euler = Mathematician.new
euler.full_name   # public → диспетчеризация
euler.secret      # private, есть явный получатель → method_missing → NoMethodError
```

## method_missing

Если поиск по всей цепочке не нашёл метод — VM не сдаётся сразу. Вместо этого вызывает `method_missing` на том же объекте, сдвигая аргументы:

```ruby
euler.nonexistent(1, 2)
# превращается в:
euler.method_missing(:nonexistent, 1, 2)
```

`method_missing` — обычный метод, который ищется по тем же правилам. Стандартная реализация в `BasicObject` бросает `NoMethodError`. Но классы могут переопределить его — это основа динамических API:

```ruby
class Mathematician
  def method_missing(name, *args)
    if name.to_s.start_with?("find_by_")
      # динамический поиск
    else
      super  # стандартное поведение — NoMethodError
    end
  end
end
```

Защита от бесконечной рекурсии: если `method_missing` сам не найден (кто-то удалил его из `BasicObject`), VM бросает `NoMethodError` напрямую, без повторного поиска.

## super

Допустим, `Mathematician` переопределяет `full_name` из `Person` и хочет вызвать оригинал:

```ruby
class Person
  def full_name; "default"; end
end

class Mathematician < Person
  def full_name; "Math: " + super; end
end
```

В дизассемблере `super` — инструкция `invokesuper`:

```
== disasm: #<ISeq:full_name@<compiled>>
0000 putstring  "Math: "
0002 putself
0003 invokesuper  <calldata!argc:0, FCALL|ARGS_SIMPLE|SUPER|ZSUPER>, nil
0006 opt_plus     <calldata!mid:+, argc:1, ARGS_SIMPLE>
0008 leave
```

`invokesuper` использует тот же алгоритм обхода, но с другой стартовой точкой: не от класса объекта, а от **суперкласса того класса, где определён текущий метод**. `full_name` определён в `Mathematician` → поиск начинается с `Person` → находит `Person#full_name`.

Bare `super` (без аргументов) автоматически передаёт все аргументы и блок текущего метода — флаг `ZSUPER` в calldata. `super(x, y)` передаёт явно указанные аргументы.

## Оптимизированные инструкции

Помимо `opt_send_without_block`, YARV компилирует некоторые вызовы в специальные инструкции: `opt_plus`, `opt_minus`, `opt_aref` (`[]`), `opt_length` и другие. Каждая пробует быстрый путь — например, `opt_plus` проверяет, что оба операнда — целые числа, и складывает их напрямую, без поиска метода `+`. Если быстрый путь не сработал (получатель не Integer, или метод `+` переопределён) — инструкция откатывается к полному пайплайну: поиск, кеш, диспетчеризация.

Это не отдельный механизм — это short-circuit перед стандартным путём. В горячем коде с числами `opt_plus` экономит весь цикл поиска, но семантика остаётся той же: если `+` переопределён, Ruby вызовет переопределённую версию.

## Остальные типы

Двенадцать типов покрывают все способы определения методов в Ruby. Четыре основных мы разобрали: ISEQ, CFUNC, IVAR, ATTRSET. Остальные встречаются реже:

- **BMETHOD** — метод, созданный через `define_method` с блоком. Внутри хранится Proc, который VM вызывает при диспетчеризации.
- **ALIAS** — результат `alias_method`. Хранит ссылку на оригинальный метод, при диспетчеризации разыменовывается и вызывается оригинал.
- **ZSUPER** — метод-заглушка для делегации к `super` (создаётся внутренне, например при `include` модуля, содержащего вызов `super`).
- **OPTIMIZED** — ускоренные версии `Kernel#send`, `Proc#call`, обращений к `Struct` полям. VM обрабатывает их без полного dispatch.
- **REFINED** — метод из refinement. Поиск идёт через лексическую цепочку refinements, а не только по super chain.
- **MISSING** — обёртка для `method_missing`, хранящая причину вызова (метод не найден, нарушение видимости, `super` без суперкласса).
- **UNDEF** — метод явно удалён через `undef_method`. Поиск находит запись, но диспетчеризация вызывает `method_missing`.

## Sources

- Pat Shaughnessy, 2013, *Ruby Under a Microscope* — глава 4: диспетчеризация методов.
- Исходники Ruby (коммит `0d4538b57d`, 2026-01-10): `method.h` (rb_method_type_t — 12 типов, строка 117; rb_method_entry_t, rb_callable_method_entry_t — описание найденного метода; METHOD_ENTRY_INVALIDATED — флаг инвалидации), `vm_callinfo.h` (rb_callinfo — описание вызова, строка 65; rb_callcache — инлайн-кеш, строка 278), `vm_insnhelper.c` (vm_search_method_fastpath — горячий путь кеша, строка 2357; vm_call_method — проверка видимости, строка 5004; vm_call_method_each_type — dispatch switch, строка 4865; vm_call_ivar — IVAR без фрейма, строка 4060), `vm_method.c` (search_method0 — обход super chain, строка 1686), `insns.def` (opt_send_without_block, invokesuper, opt_plus — инструкции вызова).

---

← [Формы объектов](../object-model/shapes.md) | [Определение методов](method-definition.md) →
