# Layer gaps

Концепции, которые всплывают в заметках как мотивация или worked example, но не имеют собственной заметки в репо. Добавляются сюда по мере обнаружения в `/deep-rework` и аналогичных проходах.

## decimal-and-money (databases/sql или foundations)

- **Нужна для:** `foundations/floating-point.md` и `foundations/floating-point-edge-cases.md` — обе заметки прямо зовут «специализированные десятичные типы (DECIMAL/NUMERIC)» как решение для денежных расчётов, но перенаправить читателя некуда.
- **Что это:** формат фиксированной точки (DECIMAL/NUMERIC в SQL, BigDecimal в Java/Ruby) — альтернатива IEEE 754 там, где точное представление десятичных дробей обязательно.
- **Зачем в репо:** завершает дугу «float не подходит для денег», переводит читателя с «не используйте float» на «используйте вот это».
- **Ожидаемый слой:** `databases/sql/schema/decimal-and-money.md` либо `foundations/fixed-point-decimal.md`.
- **Обнаружено:** 2026-04-17 /deep-rework foundations

## integer-overflow-in-practice (отдельный аггрегат или cross-link'и)

- **Нужна для:** `foundations/integers.md` — прикладные проявления знакового переполнения (TCP seq wraparound, Y2038, SQL `INT` overflow, счётчики в Prometheus) сейчас упоминаются только через Ariane-5.
- **Что это:** каталог реальных инцидентов и шаблонов защиты (безопасное приведение типов, checked arithmetic в Rust, проверка границ до операции).
- **Зачем в репо:** показывает, что переполнение — не теоретическое свойство `INT`, а регулярный источник багов в production.
- **Ожидаемый слой:** либо `foundations/integer-overflow-in-practice.md`, либо достаточно cross-link'ов из integers.md в существующие заметки сети/БД, когда те появятся.
- **Приоритет:** низкий — при наличии заметок-потребителей задача решается линками.
- **Обнаружено:** 2026-04-17 /deep-rework foundations

## kahan-summation (algorithms-and-data-structures/techniques)

- **Нужна для:** `foundations/floating-point-edge-cases.md` даёт Kahan summation в одном примере, но объяснение уровня «зачем нужна компенсация ошибки» короткое.
- **Что это:** алгоритм Кахана для суммирования массивов с плавающей точкой без накопления ошибки округления; родственные — Neumaier, Shewchuk, pairwise summation.
- **Зачем в репо:** численные методы и обработка больших массивов — частый случай, где наивное сложение даёт заметную ошибку.
- **Ожидаемый слой:** `algorithms-and-data-structures/techniques/compensated-summation.md` или расширение edge-cases.md до двух-трёх алгоритмов.
- **Приоритет:** низкий.
- **Обнаружено:** 2026-04-17 /deep-rework foundations

## virtual-memory / адресное пространство процесса (linux/memory)

- **Нужна для:** `programming/memory.md` описывает стек и кучу как две области памяти процесса, но само понятие «адресное пространство процесса» не введено. Естественный сосед — будущий `linux/memory/virtual-memory.md`.
- **Что это:** виртуальная память, mapping страниц, разделение ядра и пользователя, роль MMU и TLB.
- **Зачем в репо:** `programming/memory.md` + любые заметки про контейнеры/ОС опираются на модель «у процесса свой диапазон адресов», которая сейчас нигде не объяснена целиком.
- **Ожидаемый слой:** `linux/memory/virtual-memory.md`.
- **Приоритет:** средний — `memory.md` обходится без ссылки, но как только появятся темы из ОС, потребуется опора.
- **Обнаружено:** 2026-04-17 /deep-rework programming

## closure как общая концепция (programming или algorithms-and-data-structures/techniques)

- **Нужна для:** `programming/fp.md` вводит блок, захватывающий `tax_rate` из окружения, и один раз называет это closure + cross-link `ruby/internal/blocks.md`. Общего описания концепции в репо нет.
- **Что это:** функция вместе с захваченным окружением лексических переменных; формальное определение, отличие от простой передачи параметров.
- **Зачем в репо:** closure появится в многих языках, в callback-стилях, в обработке событий и в коде сборщиков. Пока работает inline-gloss в одной заметке, но при росте потребителей понадобится shared-объяснение.
- **Ожидаемый слой:** либо отдельная заметка в `programming/` (если тема соберёт материал), либо `algorithms-and-data-structures/techniques/closure.md`.
- **Приоритет:** низкий — один потребитель.
- **Обнаружено:** 2026-04-17 /deep-rework programming

## persistent-data-structures / structural sharing (algorithms-and-data-structures/techniques)

- **Нужна для:** `programming/fp.md` показывает `.merge` как «новый хеш», не объясняя, почему это дёшево. Аналогично для immutable lists в ФП-языках.
- **Что это:** persistent-структуры с structural sharing: основная часть данных переиспользуется между версиями, копируется только путь к изменению. Treap, HAMT, finger tree.
- **Зачем в репо:** закрывает дугу «неизменяемость = не обязательно дорого».
- **Ожидаемый слой:** `algorithms-and-data-structures/techniques/persistent-data-structures.md`.
- **Приоритет:** низкий — один потребитель.
- **Обнаружено:** 2026-04-17 /deep-rework programming
