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

## finite-state-machine (algorithms-and-data-structures/techniques)

- **Нужна для:** `computer/data-path/cache-coherency.md` — MESI вводится и диаграммируется как state machine, но сама рамка FSM не объяснена; `computer/atomic-instructions.md` — состояния кеш-линии при CAS и LL/SC; потенциально — будущие TCP state machine (networking), состояния транзакции/блокировки (databases), `system-design/cases/hotel-booking.md` (state machine заказа), `system-design/microservices.md` (оркестратор как FSM).
- **Что это:** методическая рамка описания системы через конечное множество состояний и переходов по событиям. Формально — тройка (Q, Σ, δ) или пятёрка с начальным и финальными состояниями. Прикладная форма — диаграмма состояний и таблица переходов.
- **Зачем в репо:** FSM уже используется в cache-coherency как модель, появляется как упоминание в system-design — пора вынести общую теорию наверх, чтобы технологические заметки опирались на одну базу, а не переизобретали рамку.
- **Ожидаемый слой:** `algorithms-and-data-structures/techniques/finite-state-machine.md`.
- **Приоритет:** средний — четыре потребителя в разных доменах, §9 structure-guide срабатывает.
- **Обнаружено:** 2026-04-17 /deep-rework computer

## red-black-tree (algorithms-and-data-structures/non-linear)

- **Нужна для:** `linux/foundations/scheduler.md:119` — CFS/EEVDF runqueue; `linux/foundations/virtual-memory.md:188` (до split — в будущем в `linux/foundations/virtual-memory/page-faults.md`) — VMA lookup при page fault.
- **Что это:** самобалансирующийся BST с цветами узлов и ограниченными ротациями; амортизированное O(log n) на вставку/удаление/поиск с малой константой; leftmost/rightmost получается за O(1) при кешировании указателя.
- **Зачем в репо:** два независимых потребителя в `linux/foundations/` (порог §9 structure-guide для выделения shared-заметки). Обе текущие ссылки ведут на родительский `binary-search-tree.md`, что не раскрывает специфику red-black. Читатель планировщика не видит, почему red-black, а не AVL или hash-table.
- **Ожидаемый слой:** `algorithms-and-data-structures/non-linear/red-black-tree.md`.
- **Приоритет:** средний — два load-bearing потребителя в foundations-слое.
- **Обнаружено:** 2026-04-23 /deep-rework linux

## spectre-meltdown-mitigations (linux/kernel)

- **Нужна для:** `linux/foundations/cpu-modes-and-syscalls.md:52, 101` — стоимость syscall 200-700 нс с KPTI+IBRS; `linux/foundations/scheduler.md:37` — overhead KPTI 20-30% на syscall-heavy нагрузках; `linux/kernel/syscall-internals.md` — расширение существующего раздела KPTI.
- **Что это:** набор аппаратных и программных митигаций против Spectre/Meltdown — KPTI (изоляция таблиц страниц ядра, раздельные user/kernel PT), IBRS (ограничение speculative execution через регистр), retpoline (замена indirect branch на return trampoline). Что делает каждая, сколько стоит, когда применяется.
- **Зачем в репо:** полная картина стоимости syscall и context switch требует понимать, что именно добавляют митигации. Сейчас KPTI объясняется только в `syscall-internals` на уровне эффекта, IBRS — голое имя в cpu-modes без расшифровки. Три митигации — три разных ответа на одну проблему, trade-off между защитой и латентностью.
- **Ожидаемый слой:** `linux/kernel/spectre-meltdown-mitigations.md`.
- **Приоритет:** низкий-средний.
- **Обнаружено:** 2026-04-23 /deep-rework linux

## autogroup-scheduler (linux/foundations или linux/kernel)

- **Нужна для:** `linux/foundations/threads.md:109` — утверждение «10 потоков = 10x CPU» устаревает из-за autogroup; `linux/foundations/scheduler.md` — не упомянут как дефолтный механизм группировки задач.
- **Что это:** `kernel.sched_autogroup_enabled=1` (дефолт с 2.6.38, октябрь 2010, Mike Galbraith) — группирует задачи одной сессии TTY в одну scheduler group. CFS/EEVDF делит CPU между группами, а не между отдельными `task_struct`. Процесс с 10 потоками из одной сессии получает ту же долю CPU, что и однопоточный процесс из другой.
- **Зачем в репо:** дефолтный механизм распределения CPU, ломающий наивную модель «потоки делят время поровну». Работает без настройки cgroups. Актуально для примеров с multithread-процессами и для понимания, почему `make -j8` не убивает отзывчивость терминала.
- **Ожидаемый слой:** подраздел в будущей заметке `linux/kernel/cfs-and-groups.md` или расширение `scheduler.md`.
- **Приоритет:** низкий — может быть покрыт inline-расшифровкой в scheduler.md при следующей переработке.
- **Обнаружено:** 2026-04-23 /deep-rework linux

## no-new-privs-sandbox (linux/foundations или linux/containers)

- **Нужна для:** `linux/foundations/permissions-and-capabilities.md` — модель sandbox для worker-процесса; `linux/containers/containers.md` — Docker `--security-opt=no-new-privileges`; связка с `seccomp`.
- **Что это:** флаг `prctl(PR_SET_NO_NEW_PRIVS)` (Linux 3.5+, 2012) — после установки процесс и все потомки не могут получить новые привилегии через execve: setuid-бит и file capabilities игнорируются. Используется в Docker, systemd (`NoNewPrivileges=yes`), seccomp-фильтрах.
- **Зачем в репо:** без этого флага модель «worker сбросил привилегии» неполна — worker может вызвать setuid-binary и вернуть root. `no_new_privs` закрывает этот путь. Ключевой механизм современного sandboxing (Docker default, systemd services, Chrome renderer).
- **Ожидаемый слой:** подраздел `containers.md` или отдельная короткая заметка `linux/containers/no-new-privs.md`.
- **Приоритет:** низкий — inline-упоминания достаточно в большинстве сценариев.
- **Обнаружено:** 2026-04-23 /deep-rework linux

## cgroup-v2 (linux/containers)

- **Нужна для:** `linux/containers/namespaces-and-cgroups.md` — дефолт с 2016, унификация иерархии; `linux/foundations/scheduler.md` — cgroup v2 CPU controller; `linux/foundations/threads.md` — упоминание cgroups при распределении CPU.
- **Что это:** cgroup v2 как единая иерархия ресурсов (v1 имел отдельные иерархии per-controller). Systemd использует v2 по умолчанию на современных дистрибутивах (Fedora с 2019, Debian с 2021). Модель «каждый процесс — в одной точке иерархии» вместо v1 «процесс в N иерархиях одновременно». CPU.weight заменяет cpu.shares; memory.low/high/max заменяет memory.limit_in_bytes и soft limits.
- **Зачем в репо:** современные контейнеры (Docker 20+, Podman, containerd с runc) работают на v2, v1 упоминается как исторический. Без явной заметки про v2 читатель не понимает, как cgroups связаны с systemd slice/unit и почему «cgroups в контейнере» на современной машине — это v2.
- **Ожидаемый слой:** расширение `linux/containers/namespaces-and-cgroups.md` или отдельный `linux/containers/cgroup-v2.md`.
- **Приоритет:** средний — containers/ переработка упирается в v1/v2 split.
- **Обнаружено:** 2026-04-23 /deep-rework linux
