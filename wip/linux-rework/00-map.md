# Карта Linux: инвентарь и гипотезы для ревью фазы 1

## Scope Summary

Серия из 31 файла (обзор + 30 заметок, ~98k слов) покрывает Linux как слой между программами и аппаратурой. Ядро организовано по методу последовательного нарастания сложности: от базовых концепций (процесс, поток, файловый дескриптор) через механизмы управления ресурсами (память, планировщик, синхронизация) к внутреннему устройству ядра (syscalls, драйверы, сетевой стек) и специализированным темам (контейнеры, инструментарий). 

Размер заметок варьируется от 1.5k слов (what-is-os — вводная мотивация) до 5.8k слов (virtual-memory — концептуально плотный материал). Пять наиболее объёмных файлов — virtual-memory (5821w), filesystems (4518w), network-stack (4593w), boot (4468w), scheduler (3604w) — часто содержат множественные уровни деталей и являются кандидатами на разбиение. Три самых коротких (what-is-os 1555w, sockets 2255w, memory-mapping 2520w) выполняют роль входных абзацев и мотивирующих примеров в своих подпапках.

## Inventory

| Файл | Предпосылки заявленные | Cross-links в тексте (выборка) | Wordcount | Первые подозрения |
|------|------|------|------|------|
| **foundations/what-is-os** | computer.md (CPU, RAM, DMA) | виртуальная память, процессы, планировщик, file-descriptors, syscalls | 1555 | Мотивирующий вход, три проблемы без ОС переформулированы как три задачи ОС; хорошо структурировано, нет декоративности |
| **foundations/cpu-modes-and-syscalls** | ISA, регистры CPU; what-is-os | процессы, трансляция адресов, планировщик, KPTI, переключение контекста | 3008 | Вводит кольца привилегий и syscall как переход границы; много чисел (стоимость syscall в разных сценариях); буферизация stdio в конце может растянуться в отдельный файл |
| **foundations/processes** | cpu-modes-and-syscalls | tasks_struct, fork/exec, state diagram, потоки | 2806 | Полный жизненный цикл процесса; паттерн fork+exec хорошо мотивирован; Copy-on-Write ссылается на virtual-memory без объяснения деталей — правильно |
| **foundations/threads** | processes | clone(), pthread_create, task_struct, TLS | 2810 | Сравнение потоков и процессов по стоимости; модель 1:1 vs M:N; гонка данных и счётчик-инкремент как пример — хорошо, но синхронизация отложена в concurrency/ |
| **foundations/file-descriptors** | cpu-modes-and-syscalls, processes, threads | inode, open file description, fork и разделённое смещение | 2539 | Трёхуровневая таблица fd-дескрипторов хорошо нарисована; ясное разделение между per-process таблицей и system-wide open file table |
| **foundations/virtual-memory** | file-descriptors, процессы, иерархия памяти, когерентность кешей | MMU, TLB, page fault, Copy-on-Write, многоуровневая page table | 5821 | **Самый объёмный файл в foundations**; страницы, page table, многоуровневое дерево, TLB, demand paging, CoW — каждый из этих подтопиков может быть отдельным; много диаграмм и кода, очень плотно |
| **foundations/filesystems** | none указаны, на самом деле зависит от virtual-memory, file-descriptors | inode, page cache, журнал (journaling), fsync | 4518 | **Объёмный, слабо связан с что-то более высоким**; структура inode и адресные блоки часто описаны через реализацию (block pointers), а не через концепцию; POSIX semantics и sync concerns в конце может отвлекать |
| **foundations/permissions-and-capabilities** | none явные | UID/GID, root, capabilities, DAC vs MAC | 3088 | Входит в конец foundations, но может быть ортогональна предыдущим; capabilities часто не используются в примерах выше |
| **foundations/scheduler** | processes (планировщик вытесняет), virtual-memory (кеш TLB) | CFS, vruntime, красно-чёрное дерево, контекстное переключение, приоритеты | 3604 | **Второй по объёму в foundations**; алгоритм CFS и красно-чёрное дерево подробно разобраны; может содержать детали реализации ниже пола заметки |
| **concurrency/synchronization** | планировщик, потоки, когерентность кешей, syscalls | гонка данных, мьютекс, спинлок, condition variable | 3398 | Хорошо мотивирована через потерянный инкремент; много псевдокода и примеров; правильно ссылается на atomics в computer/ |
| **concurrency/memory-ordering** | потоки | барьеры памяти, компилятор и процессор переупорядочивают, acquire/release | 2732 | Тонкая тема; может быть слишком низко для целевой аудитории foundations |
| **concurrency/lock-free** | synchronization, memory-ordering | CAS, ABA problem, hazard pointers | 3187 | Практические lock-free структуры; много предупреждений о подводных камнях |
| **programming/signals** | cpu-modes-and-syscalls | обработчик сигнала, async-signal-safe, маски, потоки | 2404 | Хорошо структурирована; уместно подчёркивает сложность async обработки |
| **programming/memory-mapping** | virtual-memory, filesystems | mmap, demand paging, shared memory, CoW для файлов | 2520 | Краткая, но полная; связывает виртуальную память и файловую систему через page cache |
| **programming/file-io** | file-descriptors, cpu-modes-and-syscalls | буферизация, fsync, direct I/O, AIO | 3132 | Хорошо мотивирована (гарантии записи на диск); много практических деталей |
| **programming/sockets** | file-io, file-descriptors | TCP/UDP, TCP-сервер полный цикл, SO_REUSEADDR | 2255 | Краткая введение, правильно ссылается на network-stack ядра; примеры кода понятны |
| **programming/io-multiplexing** | sockets, memory-mapping | select, poll, epoll, io_uring, event loop | 3881 | Три поколения: select/poll/epoll с линейным улучшением по стоимости; io_uring только обозначен, детали в ядре |
| **programming/memory-management** | virtual-memory, scheduler | overcommit, OOM killer, huge pages, NUMA | 3316 | Подхватывает потребление памяти на уровне приложения; OOM killer хорошо мотивирован через namespaces |
| **programming/ipc** | processes, threads, file-descriptors | pipes, shared memory, message queues, semaphores | 3078 | Перечень механизмов; может быть слишком справочной (много вариантов, мало причинности) |
| **kernel/syscall-internals** | cpu-modes-and-syscalls, processes | LSTAR, переключение стека, pt_regs, sys_call_table, KPTI | 2504 | Внутреннее устройство syscall от инструкции до обработчика; хорошо отслежены микросекунды |
| **kernel/interrupts** | none явные (зависит от scheduler, devices) | аппаратные прерывания, IRQ handler, задержение в bottom half | 3362 | Как ядро обрабатывает события от оборудования; может быть слишком низко без контекста из scheduler |
| **kernel/devices-and-drivers** | none явные | device tree, major/minor number, /dev, ioctl | 2848 | Как ядро находит оборудование и предоставляет интерфейс; короткая и справочная |
| **kernel/network-stack** | sockets, file-descriptors | путь пакета от сетевой карты до приложения, TCP handshake | 4593 | **Объёмный анатомический разбор**; может содержать детали реализации ниже пола; много диаграмм пути пакета |
| **kernel/memory-management** | virtual-memory, scheduler | выделение физических страниц, buddy allocator, свопинг | 3536 | Внутреннее управление физической памятью; может быть слишком глубоко без конкретной мотивации |
| **infrastructure/elf-and-linking** | none явные (зависит от processes) | ELF format, динамическая линковка, ASLR, символы | 3659 | Как исполняемый файл попадает в память; хорошо объясняет, откуда берутся адреса в виртуальной памяти |
| **infrastructure/terminals** | processes, signals, file-descriptors | ввод/вывод терминала, управляющие символы, демонизация | 3045 | Нестандартный топик, но хорошо связывает fd, сигналы и процессы в практическом сценарии |
| **infrastructure/tracing** | syscall-internals, processes | strace, ptrace, BPF, профилирование | 3017 | Инструментарий для наблюдения за системой; может быть бонусным материалом |
| **infrastructure/boot** | none явные (система целиком) | загрузчик, инит, systemd | 4468 | **От BIOS к первому пользовательскому процессу**; может быть слишком историческим для основного курса |
| **containers/namespaces-and-cgroups** | процессы, scheduler, filesystems, memory-management, signals, permissions, file-descriptors | PID namespace, UTS, IPC, network namespace, cgroups v1/v2 | 2990 | Синтез 8-9 концепций из foundations/ и programming/; очень плотно; может быть непроходимо для читателя без прочного знания частей |
| **containers/containers** | namespaces-and-cgroups | Docker, seccomp, overlay FS, capabilities | 3463 | Собирает из частей контейнер; хорошо мотивировано через отдельные механизмы |

## Слои и направление зависимостей

### Иерархия слоёв

```
Уровень 4 (Приложения, опции пользователя):
  - containers/ (Docker, изоляция для деплоя)

Уровень 3 (Интеграция и API):
  - programming/ (signals, mmap, file-io, sockets, io-multiplexing, memory-management, ipc)
  - infrastructure/ (elf-and-linking, terminals, tracing, boot)

Уровень 2 (Механизмы и управление):
  - concurrency/ (synchronization, memory-ordering, lock-free)
  - kernel/ (syscall-internals, interrupts, devices-and-drivers, network-stack, memory-management)

Уровень 1 (Фундамент):
  - foundations/ (what-is-os, cpu-modes-and-syscalls, processes, threads, file-descriptors, virtual-memory, filesystems, scheduler, permissions-and-capabilities)

Уровень 0 (входящие зависимости):
  - computer/computer.md (CPU, RAM, DMA, ISA)
```

### Входящие зависимости (V-shape bottom)

1. **computer/computer.md** → foundations/what-is-os (CPU, память, DMA упомянуты как мотивация)
2. **computer/programmer-model/isa.md** → foundations/cpu-modes-and-syscalls (регистры, конвенции вызовов)
3. **computer/data-path/memory-hierarchy.md** → foundations/virtual-memory (cache line для TLB cache line conflict)
4. **computer/data-path/cache-coherency.md** → concurrency/synchronization (MESI, cache line ping-pong, false sharing)
5. **computer/atomic-instructions.md** → concurrency/synchronization (спинлоки опираются на LOCK префикс)

**Статус**: Все входящие ссылки выявлены в текстах и явно указаны в Предпосылках или через cross-links. Читатель может войти в linux/ имея знания из computer/.

### Исходящие зависимости (V-shape top)

1. **linux/foundations/processes** ← databases/postgresql/postgresql.md (fork, CoW для BGSAVE, выполнение команд)
2. **linux/foundations/threads** ← ruby/internal/internals.md (GVL как pthread_mutex_t + condition variable, Fiber, Ractor)
3. **linux/programming/io-multiplexing** ← databases/redis/redis.md (epoll event loop, select на других платформах)
4. **linux/programming/signals** ← ruby/internal/concurrency.md (как Ruby обрабатывает сигналы между потоками)
5. **linux/foundations/virtual-memory** ← databases/postgresql/postgresql.md (shared_buffers и управление страницами, fork() + CoW для снимков)
6. **linux/kernel/syscall-internals** ← databases/postgresql/postgresql.md (KPTI и стоимость системных вызовов в счётчиках WAL)
7. **linux/programming/memory-management** ← ruby/internal/internals.md (GC с bitmap marking подготовка к fork() + CoW)
8. **linux/infrastructure/elf-and-linking** ← ruby/internal/internals.md (как Ruby VM загружается)

**Наблюдение**: linux/ мотивирует прямо на уровне примеров (PostgreSQL и Redis используют fork/CoW, мультиплексирование ввода-вывода, управление памятью как заданные способы работы), но не ссылается на эти домены вверх. Это логично — linux/ не должна предполагать наличие postgresql/ — но означает, что читатель не видит, *где* знание применяется, пока не доходит до этих доменов.

## Цепочки зависимостей

### Основная цепочка foundations/ (ядро курса)

```
what-is-os
  → cpu-modes-and-syscalls (как программа просит ядро)
    → processes (как ядро управляет несколькими программами)
      → threads (когда процесс дорог, нужен поток)
        → file-descriptors (как потоки взаимодействуют с ресурсами)
          → virtual-memory (как ядро изолирует память)
            → filesystems (где данные хранятся физически)
              → scheduler (как ядро выбирает, кто работает)
                → permissions-and-capabilities (как ядро контролирует доступ)
```

Все заявленные предпосылки выстроены в очерёдность. Нет мёртвых ссылок.

### Ветвление: concurrency/

```
threads (общее адресное пространство, вытеснение)
  → synchronization (гонка данных, критическая секция, примитивы)
    → memory-ordering (как компилятор и CPU переупорядочивают)
      → lock-free (структуры без блокировок используют atomics)
```

**Наблюдение**: memory-ordering может быть выше по уровню сложности для целевой аудитории foundations. Она требует понимания того, что `counter++` это не одна инструкция и что барьеры памяти нужны, но не требуется полное понимание x86 memory model.

### Ветвление: programming/

```
processes + threads + file-descriptors (базовые механизмы из foundations/)
  → signals (асинхронное уведомление процесса)
    → memory-mapping (отображение файлов в память)
      → file-io (буферизация, fsync, гарантии)
        → sockets (сетевой API через fd)
          → io-multiplexing (мониторить многие fd одним потоком)
  → memory-management (управление памятью приложением)
  → ipc (способы обмена между процессами)
```

**Мёртвые ссылки**: ipc ссылается на processes и threads, но не использует их глубоко (просто перечисляет механизмы).

### Ветвление: kernel/

```
cpu-modes-and-syscalls (как работает переход)
  → syscall-internals (внутреннее устройство)
    → interrupts (обработка событий от оборудования)
      → devices-and-drivers (поиск и инициализация оборудования)
  → network-stack (путь пакета от карты до приложения)
  → memory-management (выделение физических страниц)
```

**Наблюдение**: kernel/ слегка отвязана от остального. syscall-internals мотивирована из cpu-modes, но interrupts не ссылается явно на scheduler, хотя планировщик опирается на аппаратный таймер.

### Ветвление: infrastructure/

```
processes (как запускаются программы)
  → elf-and-linking (где берутся адреса исполняемого файла)
  → boot (как система стартует, инит)
signals + processes + file-descriptors (взаимодействие с терминалом)
  → terminals (управляющие символы, сессии)
syscalls + processes (как наблюдать за системой)
  → tracing (strace, ptrace, BPF)
```

**Наблюдение**: terminals нестандартна и может восприниматься как бонус. boot может быть слишком историческим.

### Ветвление: containers/

```
foundations/ (все 9 файлов используются):
  processes (fork, clone, PID)
  scheduler (CFS, vruntime, resource limits в cgroups)
  filesystems (mount, VFS для overlay)
  memory-management (overcommit, OOM killer)
  signals (kill, SIGCHLD)
  permissions-and-capabilities (UID, GID, capabilities)
  file-descriptors (fd, open/close)
+ programming/memory-management (overcommit, OOM killer)
  → namespaces-and-cgroups (синтез механизмов изоляции)
    → containers (собрать в Docker)
```

**Наблюдение**: namespaces-and-cgroups предполагает глубокое знание всех foundation-файлов сразу. Читатель, пропустивший что-то из foundations, потеряется.

## V-shape гипотезы: где текст может опираться на соседние слои

### Missing downward links (концепции из computer/, не используемые в linux/)

1. **Cache line и false sharing** упомянуты в concurrency/synchronization как мотивация, но не объяснены. Правильно ссылается на cache-coherency.md, но читатель может не пойти по ссылке.
   - **Гипотеза**: Если цель — научить reader'а*видеть* false sharing в своём коде, нужна явная диаграмма cache line в context потоков, работающих на разных ядрах. Сейчас в synchronization.md есть ссылка на когерентность, но нет наглядного примера.

2. **Аппаратные барьеры памяти (MESI, store buffer)** — concurrency/memory-ordering ссылается на memory-ordering из computer/, но memory-ordering в linux может быть слишком глубока для читателя, которого интересует только pthread_mutex_lock.
   - **Гипотеза**: memory-ordering может быть написана с меньшей глубиной реализации (x86 weakly ordered, ARM very weak) для основного потока, с отступлением в конец для x86 деталей.

3. **Иерархия памяти** — virtual-memory ссылается на cache hierarchy, но рассказывает про TLB как про отдельный кеш без связи с L1/L2/L3 иерархией.
   - **Гипотеза**: Диаграмма, показывающая TLB в контексте иерархии памяти (регистры → L1 → TLB → L2 → L3 → RAM), могла бы дать читателю ментальную крючок. Сейчас TLB описан как чёрный ящик.

### Missing upward links (где linux/ не мотивирует приложение)

1. **fork() + CoW** хорошо объяснена в processes, но нет примера, где это критично. PostgreSQL использует fork() + CoW для BGSAVE (снимок памяти без копирования 10+ ГБ), но linux/ не упоминает.
   - **Гипотеза**: processes.md могла бы заканчиваться мотивирующим абзацем: «Это знание вернётся, когда мы разберём, как базы данных создают снимки состояния памяти без блокировок. fork() + CoW делает это возможным.» Или хотя бы в виде forward reference в структуре-guide'а.

2. **io-multiplexing** описана блестяще (select → poll → epoll с улучшением O(n) → O(ready)), но примеров использования в реальных системах нет. Redis, Nginx, PostgreSQL используют epoll или kqueue.
   - **Гипотеза**: Абзац в конце io-multiplexing.md: «На практике: сервер Redis обслуживает 100 тысяч соединений из одного потока через epoll. PostgreSQL можно настроить через параметр multiplexing_method. На macOS и BSD используется kqueue — аналог epoll с ограничением в 1024 соединения на системе.» Это даст читателю якорь.

3. **Управление памятью ядра** (kernel/memory-management) скупо связана с programming/memory-management. Читатель не видит, как allocation в приложении связана с buddy allocator в ядре.
   - **Гипотеза**: Краткий раздел в программировании, объясняющий, как `malloc()` → `brk()`/`mmap()` → выделение ядром страниц через buddy allocator, создал бы мостик.

### Скрытые зависимости (в тексте используется, в Предпосылках не указано)

1. **virtual-memory** ссылается на Copy-on-Write в контексте fork() без явного объяснения механизма (write-protect, page fault, копирование одной страницы). Читатель, пропустивший processes, потеряется. **Но это правильно**: процессы должны идти раньше, и предпосылки их указывают.

2. **scheduler** использует красно-чёрное дерево (CFS, вставка/удаление за O(log n)), но в Предпосылки не включены структуры данных из algorithms-and-data-structures/. **Мнение**: это ошибка. Читатель, не знакомый с RB-tree, не сможет понять, как CFS работает за O(log n).

3. **network-stack** ссылается на TCP handshake, но TCP не объяснена в sockets (только упомянута как SOCK_STREAM). **Мнение**: Должна быть явная ссылка на networking/transport/tcp.md в Предпосылки network-stack.

### Места, где читатель теряет мотивацию

1. **filesystems** (4518w) — очень объёмный файл, начинается с абстрактного определения inode, переходит к структуре на диске (block pointers), потом к журналированию. Без контекста «зачем нам nодинованое хранилище?» плывёт структура.
   - **Гипотеза**: Начать с проблемы: «Когда мы пишем в файл через write(), данные попадают в page cache (виртуальная память). Но когда процесс упадёт, что произойдёт с данными? И как ядро находит файл по имени `/var/log/app.log` среди миллиардов блоков на диске?» Это двойная мотивация: durability + lookup.

2. **kernel/memory-management** — выделение физических страниц через buddy allocator. Без контекста многопроцессорности и подхода (why not bump allocator?) остаётся справкой.
   - **Гипотеза**: Начать с проблемы: «На машине 100 процессов конкурируют за RAM. Ядро должно выделять и возвращать страницы быстро, без фрагментации. Выглядит как задача из algorithms, но работает на критическом пути.»

3. **infrastructure/boot** — от BIOS к первому пользовательскому процессу. Может быть интересно, но для большинства читателей это историческая деталь, не mentальный крючок.
   - **Гипотеза**: boot может переехать в опциональный раздел или быть сжатой до одной страницы с forward reference на остальное.

## Observable гипотезы о проблемах (семена для линз)

### Структурные проблемы

1. **Справочный стиль вместо нарратива**:
   - containers/namespaces-and-cgroups и programming/ipc часто перечисляют возможности вместо того, чтобы вести читателя через выбор (когда использовать PID namespace вместо UTS namespace? когда pipe вместо shared memory?).
   - **Места**: IPC раздел в programming/ipc (перечисление семафоров, очередей сообщений), первая половина namespaces-and-cgroups.

2. **Кодовые имена без ментального крючка**:
   - `task_struct` появляется в processes и много раз после; в Предпосылки не попала явная стойка. Не все читатели понимают, что это просто «дескриптор процесса».
   - **Места**: processes.md, scheduler.md, kernel/interrupt.md используют без переразъяснения.
   - Аналогично: `pt_regs`, `vm_area_struct`, `inode`, `PTE`.

3. **Порядок разделов выглядит документацией, а не нарративом**:
   - virtual-memory: страницы → page table → многоуровневое дерево → TLB → demand paging → CoW. Порядок логичен технически, но каждый раздел требует концентрации. Нет промежуточного подвода и нет наглядной диаграммы целиком до углубления.
   - **Места**: virtual-memory первая половина (до раздела про многоуровневую page table).

4. **Длинные блоки кода/псевдокода без сценарной мотивации**:
   - cpu-modes-and-syscalls содержит flowchart syscall, потом сложный пример fork+exec+waitpid с проверкой статуса. Код полезен, но читатель может потеряться в деталях без промежуточного резюме.
   - **Места**: processes.md (паттерн fork+exec, пример handle_request), kernel/syscall-internals (pt_regs на стеке, таблица регистров).

5. **Метатермины и самореферентность**:
   - virtual-memory содержит несколько случаев «выше видели», «ниже разберём» (self-reference) вместо предметной причинности.
   - **Места**: возможны в virtual-memory и scheduler, где много перекрестных ссылок.

### Пропущенные связи

1. **Иерархия переключения контекста** разбросана:
   - context switch между потоками: 1-5 мкс (потоки → TLB не перезагружается)
   - context switch между процессами: 3-10 мкс (процессы → CR3, TLB flush)
   - context switch от signal: дополнительная стоимость (signal handling)
   - context switch на epoll_wait: переход в ядро, регистрация fd
   Читатель видит отдельные числа, но не объединяет их в иерархию.

2. **Copy-on-Write ожидается читателю в двух формах**:
   - processes: fork() → CoW для всего адресного пространства
   - memory-mapping: mmap() → CoW для файлов (в виде "это зависит от того, открыт ли файл MAP_PRIVATE")
   Читатель может не заметить, что это одна техника.

3. **Стоимость переключения привилегий растёт, а не объясняется**:
   - cpu-modes-and-syscalls: syscall стоит 100-300 нс без защит, 200-700 нс с KPTI
   - kernel/syscall-internals: KPTI описана, но мало объяснено, *почему* это добавляет стоимость (переключение таблиц страниц, flush TLB?)
   - **Миссия**: связать эти две точки явной цепочкой причин.

### Недоиспользованные слои зависимостей

1. **Permissions-and-capabilities** находится в конце foundations, но её отдельные приложения:
   - Она не участвует в основной цепочке (foundations) до containers/
   - Но сигналы, файловый I/O, и sockets полагаются на UID/GID при реальном использовании.
   - **Гипотеза**: Permissions могла бы быть введена раньше (после processes? после file-descriptors?), или хотя бы явно связана в кросс-ссылках.

2. **Scheduler** рассказывает про CFS, приоритеты, потоки реального времени, но не связана явно с:
   - Блокировками в programming/synchronization (мьютекс блокирует поток, планировщик выбирает другой)
   - Контроллем групп в containers/ (cgroups ограничивают процессорное время, планировщик это соблюдает)
   - **Гипотеза**: Между scheduler.md и siguiente в foundations/ (permissions-and-capabilities?) может быть явный мостик.

## Observable гипотезы о проблемах (семена для линз) — Summary

| Проблема | Примеры файлов | Тип |
|----------|---|---|
| Справочный стиль вместо нарратива | ipc, namespaces-and-cgroups | Дуга |
| Кодовые имена без опоры | processes, scheduler, kernel/ | Читатель (§2) |
| Порядок разделов как документация | virtual-memory, scheduler | Дуга |
| Длинные блоки кода без сценария | processes, syscall-internals | Нагрузка |
| Метатермины и самореференция | virtual-memory, scheduler | Чистый язык |
| Иерархия стоимости разбросана | cpu-modes, kernel/syscall, потоки | Дуга |
| Copy-on-Write в двух видах | processes, memory-mapping | Полнота |
| KPTI мало объяснена | cpu-modes vs kernel/syscall | Читатель |
| Permissions недоиспользована | foundations | Дуга |
| Scheduler не связана с синхронизацией и cgroups | scheduler | Дуга |

## Кандидаты в scope options для пользователя

На основе инвентаря и гипотез предлагаю три scope-варианта. Каждый соответствует разному пониманию читателя и цели.

### **Spine only** (foundations/ полностью, 9 файлов, ~28k слов)

Фундаментальные абстракции ОС от процесса до прав доступа.

**Что входит**: what-is-os, cpu-modes-and-syscalls, processes, threads, file-descriptors, virtual-memory, filesystems, scheduler, permissions-and-capabilities.

**Что теряется**: все углубления (concurrency, programming, kernel, infrastructure, containers).

**Improves for the reader**: 
- Кумулятивное знание фундамента, на котором строится всё остальное. Читатель понимает границы между процессами, как управляется время и память.
- Каждый файл в foundations/ опирается на предыдущие и переполняется into следующего. Более когерентный нарратив.
- Достаточно для понимания PostgreSQL's fork() + CoW, Ruby's GVL как потоков, базового Nginx с процессом на соединение.

**Скрытая стоимость**: containers/ и большинство programming/ остаются без фундамента. Читатель не видит, как эти механизмы *используются*.

---

### **One углубление** — **programming/ полностью** (7 файлов, ~22k слов)

Практический API: после того, как читатель усвоил foundations/, переходит к тому, как программы используют эти механизмы.

**Что входит**: foundations/ (все 9) + programming/ (signals, memory-mapping, file-io, sockets, io-multiplexing, memory-management, ipc).

**Что теряется**: kernel/ (внутреннее устройство), concurrency/ (тонкие моменты синхронизации), containers/, infrastructure/ (кроме применения в programming).

**Improves for the reader**: 
- После foundations/ читатель немедленно видит, как вызвать эти механизмы из кода (read/write, mmap, fork, signals).
- Практические примеры: TCP-сервер, epoll event loop, буферизация, OOM killer.
- Достаточно для написания системного ПО среднего размера (веб-сервер, демон, сетевая утилита).
- io-multiplexing может мотивировать Redis и Nginx.

**Скрытая стоимость**: Без concurrency/ потоки остаются без глубокого погружения в синхронизацию. Без kernel/ читатель видит API, но не видит, что происходит внутри.

---

### **Cross-cutting** (только linux.md + согласованность между подпапками)

Без добавления новых файлов: проверка, что каждый файл правильно связан, предпосылки выполнены, cross-links встроены.

**Что входит**: linux.md (обзор) + проверка и доработка всех 30 файлов на предмет консистентности.

**Что теряется**: новое содержание.

**Improves for the reader**: 
- Каждый файл может быть входом благодаря полной ссылочной сетке.
- Не требуется читать по порядку — можно прыгать между темами и не потеряться.
- Новые читатели, ищущие конкретный топик (epoll, mmap, fork), находят его и могут прочитать с автоматическим раскрытием предпосылок через ссылки.

**Скрытая стоимость**: Не решает проблемы нарратива и мотивации внутри файлов.

---

### **Full pass** (все 30 файлов, ~98k слов)

Полная переработка всех файлов по методике styleguide.

**Improves for the reader**: 
- Каждый файл переписан как объяснение, а не справка.
- Нарратив внутри каждого: от мотивации к механизму к следствиям.
- Скрытые зависимости выявлены и встроены.
- V-shape связи с computer/, postgresql/, redis/, ruby/ явные.
- Читатель видит, откуда идёт знание (computer) и где оно используется (databases, runtime).

**Стоимость**: 200+ часов переработки 30 файлов + доработка cross-links в зависимых доменах.

---

**Мнение на финальный выбор**: Spine only (foundations/) + One углубление (programming/) вместе дают наибольший ROI для читателя: он может заканчивается с возможностью писать системное ПО, опираясь на твёрдый фундамент. Full pass даёт совершенство, но требует пропорциональной стоимости в усилиях ревью и переработки.
