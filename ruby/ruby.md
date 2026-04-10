---
tags:
  - domain/ruby
  - theme/internals
  - theme/concurrency
  - type/overview
aliases:
  - CRuby
  - MRI
  - YARV
order: 0
---

# Ruby

**Предпосылки:** умение программировать; базовое знание Ruby (синтаксис, классы, модули, блоки); материалы раздела [Programming](../programming/programming.md) считаются уже пройденной базой.

> [!warning] Ruby — WIP
> Эта папка пока не раскрывает Ruby как язык: синтаксис, объектная модель с точки зрения пользователя, идиомы, stdlib. Готовые материалы — [[ruby/internal/internals|внутреннее устройство CRuby]] и [[ruby/internal/concurrency|конкурентность]] — описывают, как реализована виртуальная машина и почему она устроена именно так. Эти материалы дополнительно опираются на [Linux](../linux/linux.md) и [аппаратное обеспечение](../computer/computer.md) — см. их собственные Предпосылки. До появления раздела про язык эта страница — указатель на готовые разделы про реализацию.

У этого раздела две оси. Внутренняя ветка относится именно к CRuby (MRI): путь от исходного кода до исполнения на YARV, [[ruby/internal/object-model/objects-and-classes|объектная модель]], коллекции, [[ruby/internal/gc|GC]] и [[ruby/internal/jit|JIT]], то есть компиляции горячего кода в машинный код во время выполнения. Отдельная ветка разбирает конкурентность Ruby и различия между MRI, JRuby и TruffleRuby.

## Порядок изучения

### Внутреннее устройство (Ruby Internals)

Как Ruby-программа проходит путь от текста до результата: парсинг, компиляция, исполнение, объектная модель, методы, блоки, коллекции, GC, JIT.

- [[ruby/internal/internals|Ruby Internals]] — от исходного кода до исполнения

### Конкурентность и параллелизм

Потоки, GVL, Fiber, Ractor — как Ruby обрабатывает параллельную работу.

- [[ruby/internal/concurrency|Конкурентность]] — потоки, GVL, Fiber, Ractor, серверы

## Как всё связано

*Этот раздел — итоговая карта для тех, кто прочитал материалы выше.*

**Internals vs Concurrency:** VM определяет GVL — глобальную блокировку, ограничивающую CPU-параллелизм потоков. Объектная модель определяет, какие объекты shareable (могут передаваться между Ractor'ами), а какие нет. Конкурентность опирается на понимание [потоков ОС](../linux/foundations/threads.md) и [синхронизации](../linux/concurrency/synchronization.md).

## Sources

- Ruby language documentation: https://docs.ruby-lang.org/en/master/
- CRuby source repository: https://github.com/ruby/ruby
