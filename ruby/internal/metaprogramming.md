---
tags:
  - domain/ruby
  - theme/internals
  - type/concept
aliases:
  - metaprogramming
  - eval
  - define_method
  - refinements
order: 10
---

# Метапрограммирование

**Предпосылки:** [[ruby/internal/methods/method-definition|Определение методов]] — CREF, `definemethod`, `class << obj`, self vs CREF. [Блоки](blocks.md) (опирается на серию VM-заметок: [[ruby/internal/vm/compilation|компиляция]], [[ruby/internal/vm/execution|исполнение]], [[ruby/internal/vm/control-flow|управление потоком]]) — замыкания, EP, stack-to-heap, Proc.

← [Блоки](blocks.md) | [JIT](jit.md) →

В [[ruby/internal/methods/method-definition|заметке об определении методов]] мы видели, что `def` всегда работает через [[ruby/internal/methods/method-definition|CREF]] — лексическую область. Но `def` не создаёт замыкания: тело метода не видит локальных переменных окружающего scope. В [заметке о блоках](blocks.md) — обратная ситуация: блок является замыканием, он видит окружение через [[ruby/internal/vm/execution|EP]]. Метапрограммирование в Ruby — это способы совместить оба механизма: менять, куда попадает метод (CREF), и что видит его код (EP).

## def не создаёт замыкание

Ключевое слово `def` **не создаёт замыкания**. Тело метода, определённого через `def`, не имеет доступа к локальным переменным окружающего scope. Это граница.

Но `eval`, `instance_eval` и `define_method` используют блоки или строки — и блоки, как мы знаем из [заметки о блоках](blocks.md), являются замыканиями. Это открывает возможности, которых нет у `def`.

### eval — код, который пишет код

```ruby
a = 2
b = 3
eval("puts a + b")   # => 5
```

`eval` парсит и компилирует строку в новый [[ruby/internal/vm/compilation|ISeq]] — это знакомый процесс из [[ruby/internal/vm/compilation|заметки о компиляции]]. Затем Ruby создаёт новый фрейм для выполнения этого ISeq, но устанавливает `EP` так, чтобы он указывал на окружение вызова. Результат: код внутри `eval` видит локальные переменные `a` и `b` — через тот же механизм EP, что и обычный блок.

`eval` можно вызвать с объектом `Binding` — это «замыкание без функции», указатель на конкретный фрейм стека:

```ruby
def get_binding
  x = 42
  binding
end

eval("puts x", get_binding)   # => 42
```

`Binding` сохраняет EP фрейма, в котором был вызван `binding`. Передавая его в `eval`, мы говорим Ruby использовать это окружение вместо текущего.

### instance_eval — три эффекта в одном

```ruby
str2 = "world"
obj = Object.new
obj.instance_variable_set(:@str, "hello")

obj.instance_eval do
  puts "#{@str} #{str2}"   # => "hello world"
end
```

Код внутри `instance_eval` одновременно видит `str2` (из окружения) и `@str` (из `obj`). Это выглядит как «два окружения», но на самом деле работают три независимых механизма:

**1. Замыкание сохраняется.** `yield_under()` (`vm_eval.c:2186`) копирует `rb_captured_block`, оставляя оригинальный EP. Локальные переменные доступны через цепочку EP — как у обычного блока.

**2. `self` меняется на receiver.** В скопированном блоке поле `self` перезаписывается на `obj`. Поэтому `@str` ищется в `obj`, а не в окружающем контексте. Это единственное отличие от обычного блока.

**3. Лексическая область переключается — лениво.** Ruby создаёт новый CREF с флагом `CREF_SINGLETON` и сохраняет в `klass_or_self` сам объект-receiver (не его класс). Если внутри `instance_eval` выполнить `def`, Ruby вызовет `CREF_CLASS_FOR_DEFINITION()` (`eval_intern.h:191`) — и только в этот момент создаст singleton-класс через `rb_singleton_class()`. Если `def` нет — singleton-класс не создаётся вообще.

```ruby
obj.instance_eval { puts self.class }   # singleton-класс НЕ создан
obj.instance_eval { def m; end }        # singleton-класс создан (метод `m` попал туда)
```

Эта ленивость — оптимизация: множество вызовов `instance_eval` в реальном коде (например, DSL-ы) не определяют методов.

### class_eval — тот же путь, без singleton

```ruby
Quote.class_eval do
  def greet; "hi"; end
end
```

`class_eval` (`module_eval` — алиас) проходит тот же путь, что и `instance_eval`, но с `singleton=FALSE`. Разница:

| | `instance_eval` | `class_eval` |
|---|---|---|
| `self` | receiver (любой объект) | модуль/класс |
| `def` попадает в | singleton-класс receiver'а | сам модуль/класс |
| CREF_SINGLETON | да | нет |
| замыкание | да | да |

На практике: `class_eval` — для добавления обычных методов в класс; `instance_eval` — для работы с конкретным объектом.

## define_method — метод как замыкание

```ruby
class Logger
  %w[info warn error].each do |level|
    define_method(level) do |msg|
      puts "[#{level.upcase}] #{msg}"
    end
  end
end
```

`define_method` принимает имя метода и блок. Блок — замыкание, поэтому каждый из трёх методов «помнит» своё значение `level`. С `def` так не получится — `def` не создаёт замыкание.

Внутри Ruby создаёт method entry типа `VM_METHOD_TYPE_BMETHOD` (`proc.c`), который хранит ссылку на `rb_proc_t`. Когда метод вызывается, Ruby перезаписывает `self` на receiver'а (как у `instance_eval`), но EP замыкания сохраняется — блок по-прежнему видит `level`.

Существенное следствие: методы, определённые через `define_method`, **медленнее** обычных `def`-методов. Для ISEQ-метода dispatch может использовать оптимизированный путь без создания Proc. Для BMETHOD — всегда вызов через `invoke_iseq_block_from_c()` (`vm.c:1774`).

## Refinements — лексически ограниченное переопределение

Refinements решают конкретную проблему: как переопределить метод **только в части** программы, не ломая остальной код.

```ruby
module Shout
  refine String do
    def greet
      upcase + "!!!"
    end
  end
end

"hello".greet   # NoMethodError

using Shout
"hello".greet   # => "HELLO!!!"
```

Внутри это работает через три шага:

**1. `refine` создаёт модуль.** Ruby создаёт модуль с флагом `RMODULE_IS_REFINEMENT` и сохраняет в нём `refined_class` — указатель на целевой класс (`String`). Методы, определённые в блоке `refine`, попадают в `m_tbl` этого модуля.

**2. Оригинальный метод помечается.** Если в целевом классе уже есть метод с таким именем, `make_method_entry_refined()` (`vm_method.c:1227`) оборачивает его: тип меняется на `VM_METHOD_TYPE_REFINED`, а оригинальный method entry сохраняется в `def->body.refined.orig_me`.

**3. `using` активирует.** `using Shout` сохраняет хеш `{String => iclass}` в поле `refinements` текущего CREF. При диспетчеризации, когда Ruby встречает метод типа REFINED, он проверяет CREF текущей лексической области. Если активный refinement найден — вызывает уточнённый метод; если нет — вызывает оригинальный.

Refinements действуют **лексически**: после `using` до конца файла или определения класса/модуля. Внутри тела метода `using` не работает — это ограничение по дизайну, а не баг.

## Две оси — одна таблица

Пять способов определить метод различаются по двум осям: куда попадает метод (в текущий класс или в singleton class) и что видит его тело (замыкание текущего scope или нет).

```
                   куда метод          замыкание     self внутри
def                CREF (лекс. обл.)   нет           receiver
def self.x         CLASS_OF(self)      нет           receiver
class << obj       новый CREF          нет           singleton class
instance_eval      singleton (лениво)  да            receiver
class_eval         класс/модуль        да            класс/модуль
define_method      текущий класс       да            receiver
eval               CREF вызова         да            из окружения
```

Все эти варианты — комбинации двух осей: *куда попадает метод* (лексическая область или explicit target) и *что видит код* (замыкание или нет). Понимание этих двух механизмов — CREF и EP — превращает «множество несвязанных методов» в логичную систему.

## Sources

- Pat Shaughnessy, 2013, *Ruby Under a Microscope* — глава 9: метапрограммирование и замыкания.
- Исходники Ruby (коммит `0d4538b57d`, 2026-01-10): `eval_intern.h` (CREF_SINGLETON — CREF_FL_SINGLETON/IMEMO_FL_USER3, строка 240; CREF_CLASS — строка 182; CREF_CLASS_FOR_DEFINITION — строка 193), `vm_insnhelper.c` (refined dispatch — строка 4957), `vm_eval.c` (specific_eval — строка 2269, yield_under — строка 2188, rb_obj_instance_eval — строка 2338), `vm_method.c` (resolve_refined_method — строка 2027, make_method_entry_refined — строка 1229), `vm.c` (invoke_block — строка 1738, invoke_iseq_block_from_c — строка 1776), `eval.c` (add_activated_refinement — строка 1514).

---

← [Блоки](blocks.md) | [JIT](jit.md) →
