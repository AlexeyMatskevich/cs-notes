# Ruby

**Предпосылки:** базовое знание Ruby (синтаксис, классы, модули, блоки).

Ruby — интерпретируемый язык с виртуальной машиной YARV. Этот раздел покрывает две оси: внутреннее устройство CRuby и модель конкурентности.

## Порядок изучения

### Внутреннее устройство (Ruby Internals)

Как Ruby-программа проходит путь от текста до результата: парсинг, компиляция, исполнение, объектная модель, методы, блоки, коллекции, GC, JIT.

- [Ruby Internals](internal/index.md) — от исходного кода до исполнения

### Конкурентность и параллелизм

Потоки, GVL, Fiber, Ractor — как Ruby обрабатывает параллельную работу.

- [Конкурентность](ruby-concurrency.md) — потоки, GVL, Fiber, Ractor, серверы

## Как всё связано

**Internals vs Concurrency:** VM определяет GVL — глобальную блокировку, ограничивающую CPU-параллелизм потоков. Объектная модель определяет, какие объекты shareable (могут передаваться между Ractor'ами), а какие нет. Конкурентность опирается на понимание [потоков ОС](../linux/foundations/03-threads.md) и [синхронизации](../linux/concurrency/00-synchronization.md).

## Sources

- Ruby language documentation: https://docs.ruby-lang.org/en/master/
- CRuby source repository: https://github.com/ruby/ruby
