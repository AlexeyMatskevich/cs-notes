---
tags:
  - domain/ruby
  - theme/internals
  - type/concept
aliases:
  - blocks
  - Proc
  - lambda
  - closure
order: 9
---

# Блоки, Proc и Lambda

> [!info]- Предпосылки
> [Замыкания](../../programming/closures.md) — что такое функция с захваченным окружением, зачем она возникает и почему узкий контракт вроде `select` нельзя насытить без этого механизма. [[ruby/internal/vm/compilation|Компиляция]] — каждый scope (метод, блок) = отдельный ISeq. [[ruby/internal/vm/execution|Исполнение]] — фреймы, EP, динамический доступ через `getlocal idx, level`. [[ruby/internal/vm/control-flow|Управление потоком]] — `throw` + catch tables для break/return. [Управление памятью ОС](../../linux/programming/memory-management.md) — стек vs куча, стоимость `malloc` при stack-to-heap promotion.

← [[ruby/internal/methods/method-definition|Определение методов]] | [Метапрограммирование](metaprogramming.md) →

Блок `{ puts name }` обращается к переменной `name` из окружающего метода через цепочку [[ruby/internal/vm/execution|EP]] — на уровне VM это выглядело технической деталью «блок видит переменные метода». Но за ней стоит фундаментальная идея — [замыкание](../../programming/closures.md), функция вместе с захваченным окружением, — которая объединяет блоки, `Proc` и `lambda` в одну концепцию.

## Блок — это замыкание

Возьмём пример:

```ruby
def greet(name)
  3.times { |i| puts "#{i}: Hello, #{name}" }
end
```

Блок `{ |i| puts ... }` делает две вещи одновременно: принимает параметр `i` (как мини-метод) и читает `name` из метода `greet` (как часть метода). Эта «двойная природа» — не случайность синтаксиса. Это реализация *замыкания* (closure — функция вместе с захваченным окружением) — идеи, которую Сассман и Стил сформулировали в 1975 году для Scheme: замыкание — это сочетание функции и окружения, которое используется при её вызове.

В терминах Ruby: блок хранит две вещи — **код** (свой [[ruby/internal/vm/compilation|ISeq]]) и **ссылку на окружение** ([[ruby/internal/vm/execution|EP]] метода `greet`). Дизассемблер показывает обе:

```
== disasm: #<ISeq:greet@<compiled>>
local table (size: 1, argc: 1)
[ 1] name@0<Arg>
0000 putobject                              3
0002 send                    <calldata!mid:times, argc:0>, block in greet
0005 leave

== disasm: #<ISeq:block in greet@<compiled>>
local table (size: 1, argc: 1)
[ 1] i@0<Arg>
0000 putself
0001 getlocal_WC_0                          i@0
...
0009 getlocal_WC_1                          name@0
...
0019 leave
```

Два фрагмента — метод и блок. В методе `send :times` ссылается на «block in greet» — это ISeq блока, код замыкания. Внутри блока `getlocal_WC_1 name` читает переменную на один уровень вверх по EP — это ссылка на окружение. Эти два элемента мы уже разбирали по отдельности в [[ruby/internal/vm/compilation|заметке о компиляции]] и [[ruby/internal/vm/execution|заметке об исполнении]]. Здесь они соединяются.

## yield: как VM вызывает блок

Когда метод хочет вызвать переданный блок, он делает `yield`. В байткоде это инструкция `invokeblock`. Возьмём метод с двумя `yield`:

```ruby
def each_item
  yield 1
  yield 2
end
```

Его дизассемблер — два `invokeblock`, по одному на каждый `yield`:

```
== disasm: #<ISeq:each_item@<compiled>>
0000 putobject_INT2FIX_1_                          # кладёт 1 как аргумент
0001 invokeblock             <calldata!argc:1, ARGS_SIMPLE>   # yield 1
0003 pop
0004 putobject               2                                # кладёт 2
0006 invokeblock             <calldata!argc:1, ARGS_SIMPLE>   # yield 2
0008 leave
```

`invokeblock` не ищет метод по имени — блок уже передан при вызове. VM находит его в служебном слоте фрейма того метода, который делает `yield`: ниже локальных переменных лежит block handler — ссылка на переданный блок. Для `each_item` он на фрейме самого `each_item`; в цепочке `greet` → `3.times` — на фрейме `Integer#times`, который и вызывает блок. За переменными окружения (`name`) блок ходит отдельно — по цепочке EP в фрейм `greet`, где был создан.

Когда `invokeblock` выполняется, VM создаёт BLOCK-фрейм и устанавливает его EP так, чтобы он ссылался на EP окружения — метода `greet`. Вот как выглядит стек фреймов в момент выполнения `puts` внутри блока:

```
CFP → BLOCK   { |i| puts "#{i}: Hello, #{name}" }
               EP ─────────────────────────────────┐
      CFUNC   Integer#times                        │
      METHOD  greet(name)                          │
               EP ← ──────────────────────────────┘
                     name = "Ruby"
```

BLOCK-фрейм и METHOD-фрейм `greet` связаны через EP. Между ними стоит CFUNC-фрейм `Integer#times`, но это не мешает — блок «перепрыгивает» через промежуточные фреймы и видит переменные `greet` напрямую. Именно так `getlocal_WC_1 name` находит `name` — поднимается на один уровень EP.

## Нулевая стоимость

Блоки передаются повсюду — `each`, `map`, `select`, `times`. Блок хранит код и окружение, и наивная реализация завела бы под это отдельный объект в куче — то есть [malloc](../../linux/programming/memory-management.md) на каждый вызов `each`, `map`, `times`. В цикле на миллион элементов это миллион выделений и освобождений памяти под объекты, которые живут лишь на время одного вызова, — стоимость, которой можно избежать целиком.

Ruby избегает этого трюком: описание блока для передачи (`rb_captured_block` — `self`, окружение, код) совпадает по раскладке с началом самого фрейма. Поэтому при передаче блока-литерала VM не аллоцирует новый объект — она записывает ISeq блока в текущий фрейм и передаёт указатель на часть этого фрейма как «описание блока». Никакого malloc.

Блок-литерал без `Proc.new` — ноль аллокаций. Создание, передача и вызов блока происходят целиком на стеке.

## Когда блок должен пережить метод

Пока блок используется внутри метода, который его создал, всё работает на стеке. Но что если блок нужно вернуть наружу?

```ruby
def make_greeter(name)
  lambda { |greeting| "#{greeting}, #{name}!" }
end

greeter = make_greeter("Ruby")
puts greeter.call("Hello")   # => "Hello, Ruby!"
```

`make_greeter` возвращает lambda. Метод завершился, его фрейм снят со стека. Но lambda всё ещё ссылается на `name` через EP. Если EP указывает на стек, а стек уже перезаписан — будет мусор. Нужно сохранить окружение в более надёжном месте.

При создании `Proc` или `lambda` Ruby копирует фрейм стека в кучу (heap). Копирование окружения из стека в кучу — вызов malloc ([управление памятью](../../linux/programming/memory-management.md)). Функция `vm_make_env_each()` в `vm.c` выполняет три шага:

1. Выделяет область в куче и копирует туда все локальные переменные текущего фрейма.
2. Создаёт объект окружения (`rb_env_t`), управляемый GC, который оборачивает эту копию.
3. Перенаправляет `cfp->ep` на heap-копию — теперь и метод, и lambda работают с одним и тем же окружением в куче.

Если окружений несколько (блок внутри блока), функция рекурсивно продвигает всю цепочку.

Третий шаг — перенаправление EP — объясняет неочевидное поведение:

```ruby
def mutation_test
  str = "original"
  l = lambda { str }
  str = "modified"     # меняем ПОСЛЕ создания lambda
  l.call
end
puts mutation_test     # => "modified"
```

Lambda видит «modified», а не «original», потому что и `str = "modified"`, и тело lambda работают через один и тот же EP, который после создания lambda указывает в кучу. Изменение записывается в heap-копию — и lambda его видит.

По этой же причине две lambda, созданные в одном scope, разделяют окружение:

```ruby
def make_counter
  count = 0
  inc = lambda { count += 1; count }
  dec = lambda { count -= 1; count }
  [inc, dec]
end

inc, dec = make_counter
inc.call   # => 1
inc.call   # => 2
dec.call   # => 1
```

Оба замыкания ссылаются на одну heap-копию `count`. Вторая lambda не создаёт второй копии — `vm_make_env_each` проверяет, было ли окружение уже скопировано (флаг `VM_ENV_FLAG_ESCAPED` на EP), и если да — переиспользует существующий `rb_env_t`.

## Proc: блок-как-объект

Блок сам по себе — не объект. Его нельзя сохранить в переменную, вернуть из метода или вызвать `.call`. Чтобы превратить блок в объект, Ruby оборачивает его в `Proc`.

Три способа создать Proc:

```ruby
p1 = Proc.new { |x| x * 2 }    # явно
p2 = proc { |x| x * 2 }        # сокращение (Kernel#proc)
def foo(&blk); blk; end         # &block параметр
p3 = foo { |x| x * 2 }
```

Во всех случаях Ruby создаёт `rb_proc_t` (`vm_core.h`) — структуру, которая содержит `rb_block` (замыкание: ISeq + EP) и три однобитных флага. C-обёртка делает эту структуру полноценным Ruby-объектом класса `Proc`, управляемым GC.

Создание Proc запускает `vm_make_env_each` — стек копируется в кучу. После этого Proc можно безопасно хранить в переменной и вызывать позже, даже когда метод-создатель давно завершился.

## Lambda: Proc со строгостью метода

```ruby
lam = lambda { |a, b| [a, b] }
```

Lambda — тот же Proc, но с `is_lambda = true`. Один бит — два следствия.

**Аргументы.** Lambda проверяет арность как метод: неправильное количество аргументов — `ArgumentError`. Proc — нет: дополняет недостающие `nil`, обрезает лишние.

```ruby
lam = lambda { |a, b| [a, b] }
pr  = proc   { |a, b| [a, b] }

lam.call(1)        # ArgumentError: wrong number of arguments (given 1, expected 2)
pr.call(1)         # => [1, nil]
pr.call(1, 2, 3)   # => [1, 2]
```

Внутри это переключение одного enum: lambda передаёт аргументы как `arg_setup_method` (строгий, как у метода), proc — как `arg_setup_block` (мягкий, как у блока). Выбор — по флагу `is_lambda` (`vm_insnhelper.c`).

**return.** В lambda `return` выходит из lambda — как из метода. В proc `return` выходит из *окружающего* метода — как если бы return стоял в теле метода напрямую.

```ruby
def test_lambda
  l = lambda { return 10 }
  l.call
  "after lambda"       # выполняется
end

def test_proc
  p = proc { return 10 }
  p.call
  "after proc"         # НЕ выполняется
end

test_lambda   # => "after lambda"
test_proc     # => 10
```

Механизм — тот же `throw`, что мы видели в [[ruby/internal/vm/control-flow|заметке об управлении потоком]]. `return` компилируется в `throw TAG_RETURN`. Когда [[ruby/internal/vm/execution|VM]] обрабатывает throw, она ищет целевой фрейм по цепочке EP. Для lambda: VM видит флаг `VM_FRAME_FLAG_LAMBDA` на фрейме блока и останавливается — return выходит из lambda. Для proc: флага нет, VM продолжает искать — доходит до METHOD-фрейма окружающего метода и выходит из него.

Если метод уже завершился (Proc пережил его), throw не находит METHOD-фрейм — и Ruby бросает `LocalJumpError`:

```ruby
def make_returner
  proc { return 42 }
end

p = make_returner
p.call   # LocalJumpError: unexpected return
```

`break` работает аналогично: в lambda — выход из lambda, в proc — выход из итератора. `next` одинаков для обоих — возврат значения из текущего вызова блока.

## Три формы — одна идея

Блок, Proc и lambda — три уровня материализации одного замыкания:

```
                   аллокация    объект?    аргументы    return
блок               стек         нет        мягкие       из метода
Proc               heap         да         мягкие       из метода
lambda             heap         да         строгие      из lambda
```

Все три хранят одну и ту же пару — код и окружение. Разница — в степени «самостоятельности»: блок неотделим от вызова, Proc можно передавать, lambda ведёт себя как полноценный метод.

## Sources

- Gerald J. Sussman, Guy L. Steele Jr., 1975, «Scheme: An Interpreter for Extended Lambda Calculus» — оригинальное определение closure.
- Pat Shaughnessy, 2013, *Ruby Under a Microscope* — глава 8: блоки, замыкания, Proc.
- Исходники Ruby (коммит `0d4538b57d`, 2026-01-10): `vm_core.h` (rb_captured_block — строка 878, rb_proc_t — строка 1287, rb_env_t — строка 1300, VM_FRAME_FLAG_LAMBDA — строка 1405), `vm.c` (VM_CFP_TO_CAPTURED_BLOCK — строка 283, vm_make_env_each — строка 1077), `vm_insnhelper.c` (vm_invoke_iseq_block — строка 5366, vm_invoke_block — строка 5484, return/lambda detection — строка 1837), `vm_args.c` (arg_setup_type — строка 32), `insns.def` (invokeblock — строка 1135, send с блоком — строка 847).

---

← [[ruby/internal/methods/method-definition|Определение методов]] | [Метапрограммирование](metaprogramming.md) →
