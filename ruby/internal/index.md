# Ruby Internals: от исходного кода до исполнения

**Предпосылки:** умение программировать; базовое знание Ruby (синтаксис, классы, модули, блоки); материалы раздела [Programming](../../programming/index.md) считаются уже пройденной базой.

Ruby-программа проходит путь от текста до результата через несколько фаз: парсинг, компиляция в байткод, исполнение виртуальной машиной. По пути VM работает с объектами, классами, модулями, методами и блоками — каждый из которых имеет конкретное представление в C-коде CRuby. Понимание этих представлений объясняет поведение Ruby, которое на уровне языка кажется магическим.

## Порядок изучения

```
VM (00-03) --> Object Model (00-02) --+--> Methods --> Blocks --> Metaprogramming --+
                                      |                                             |
                                      +--> GC --> Collections ----------------------+--> JIT
```

### VM: от текста до исполнения

Четыре фазы обработки Ruby-кода: текст → токены → AST → байткод → исполнение на стековой виртуальной машине.

- [Токенизация и парсинг](vm/00-tokenization-and-parsing.md) — текст → токены → AST
- [Компиляция](vm/01-compilation.md) — AST → [ISeq](vm/01-compilation.md) (байткод YARV)
- [Исполнение](vm/02-execution.md) — фреймы, [EP](vm/02-execution.md), стек значений, VM-цикл
- [Управление потоком](vm/03-control-flow.md) — if/while, break/return через jump и throw

### Объектная модель

Как Ruby представляет объекты, классы и модули в памяти. Зависит от VM ([VALUE](vm/02-execution.md), фреймы).

- [Объекты и классы](object-model/00-objects-and-classes.md) — RObject, RClass, метакласс, m_tbl
- [Модули](object-model/01-modules.md) — include/prepend, iclass, цепочка super, поиск констант через [CREF](object-model/01-modules.md)
- [Формы (Shapes)](object-model/02-shapes.md) — [shape_id](object-model/02-shapes.md), инлайн-кеш доступа к ivar

*После Object Model — две независимые ветки. Можно читать в любом порядке.*

---

### Ветка A: Методы и метапрограммирование

**Методы.** Жизненный цикл метода: поиск, вызов, определение, удаление. Зависит от объектной модели (m_tbl, цепочка super) и VM (фреймы, [ISeq](vm/01-compilation.md)).

- [Диспетчеризация методов](methods/00-method-dispatch.md) — поиск метода, типы вызова, method cache
- [Определение методов](methods/01-method-definition.md) — def, [CREF](methods/01-method-definition.md), definemethod, remove/undef

**Блоки и замыкания.** Замыкания, Proc, lambda. Зависит от VM ([EP](vm/02-execution.md), фреймы), компиляции ([ISeq](vm/01-compilation.md)) и управления потоком (throw).

- [Блоки](blocks.md) — yield, Proc.new, lambda, stack-to-heap promotion

**Метапрограммирование.** eval, instance_eval, define_method, refinements. Зависит от определения методов ([CREF](methods/01-method-definition.md)) и блоков (замыкания, [EP](vm/02-execution.md)).

- [Метапрограммирование](metaprogramming.md) — eval, instance_eval, define_method, refinements

---

### Ветка B: Память и коллекции

**Сборка мусора.** Управление памятью: аллокация, mark-sweep, генерации, компактификация. Зависит от VM ([VALUE](vm/02-execution.md), стек) и объектной модели (RBasic, flags).

- [GC](gc.md) — mark-sweep, generational, incremental, compaction, VWA

**Коллекции.** Внутреннее устройство встроенных типов Array, Hash, String. Зависит от объектной модели ([VALUE](vm/02-execution.md), RBasic), GC (VWA, слоты, write barrier) и [структур данных](../../algorithms-and-data-structures/linear/).

- [Array](collections/00-array.md) — RArray: embedded/heap-хранение, стратегия роста (×1.5), shared-массивы (CoW)
- [Hash](./collections/01-hash.md) — RHash: AR table (≤8 элементов), ST table (open addressing), переход между ними
- [String](collections/02-string.md) — RString: embedded/heap, кодировки, CoW, frozen strings, интернирование (fstring)

---

### JIT-компиляция

JIT — компиляция горячего байткода в машинный код во время работы программы. В этой ветке она зависит от обеих линий: VM ([ISeq](vm/01-compilation.md), фреймы), методов (инлайн-кеш, CME), форм ([shape_id](object-model/02-shapes.md)), GC (code cache).

- [JIT-компиляция](jit.md) — YJIT (BBV), ZJIT (method-based), охранные проверки, инвалидация, кеш кода

## Как всё связано

*Этот раздел — итоговая карта для тех, кто прочитал заметки выше. Термины здесь не объясняются — они определены в соответствующих файлах.*

**VM vs Объектная модель:** VM оперирует значениями типа [VALUE](vm/02-execution.md) на стеке. Объектная модель определяет, что стоит за каждым VALUE — RObject с массивом ivar и указателем klass. VM использует klass для диспетчеризации методов, shapes — для доступа к переменным.

**Статическая структура vs Динамическое поведение:** Объектная модель (классы, модули, shapes) задаёт структуру — где лежат методы и переменные. Методы и блоки определяют поведение — как код находится и исполняется. Метапрограммирование размывает эту границу: `define_method` создаёт метод из замыкания, `instance_eval` меняет `self` и лексическую область.

**Кеширование на каждом уровне:** Shapes кешируют доступ к ivar ([`shape_id`](object-model/02-shapes.md) → index). Method cache кеширует поиск методов (class serial → method entry). JIT-компилятор добавляет третий уровень — специализированный машинный код, который опирается на shape cache и method cache. Все три механизма оптимизируют горячий путь и инвалидируются при изменении структуры: переопределение метода сбрасывает method cache и JIT-код, изменение формы объекта сбрасывает shape cache и JIT-guard'ы.

**Объектная модель vs Коллекции:** Обобщённый `RObject` хранит ivar в массиве, а klass определяет поведение. Встроенные типы (Array, Hash, String) заменяют `RObject` специализированными структурами (`RArray`, `RHash`, `RString`), оптимизированными под конкретный паттерн доступа. Все начинаются с `RBasic` — поэтому `klass`, GC-флаги и shapes работают одинаково для любого объекта.

**Коллекции vs GC:** VWA из GC напрямую влияет на производительность коллекций: чем крупнее слот, тем больше данных хранится в embedded-режиме без malloc. Write barrier из generational GC срабатывает при каждой записи в массив или хеш. Compaction может переместить коллекцию в больший слот, вернув её из heap в embedded.

## Sources

- CRuby source repository: https://github.com/ruby/ruby
- Pat Shaughnessy, 2013, *Ruby Under a Microscope* — Ruby internals from tokenization to GC
