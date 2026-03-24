# Linux

**Предпосылки:** [аппаратное обеспечение](../computer/index.md) (CPU, кеш, RAM, хранилище, DMA).

Операционная система превращает набор транзисторов в платформу для программ. Ядро Linux изолирует процессы друг от друга, абстрагирует оборудование через файловые дескрипторы и системные вызовы, распределяет CPU и память между сотнями задач. Каждый механизм — ответ на конкретную проблему: виртуальная память защищает процессы от чужих данных, планировщик CFS обеспечивает отзывчивость при фоновой нагрузке, futex делает мьютексы быстрыми без syscall при отсутствии конкуренции, epoll масштабирует сервер на десятки тысяч соединений.

## Порядок изучения

Заметки организованы по слоям: от базовых абстракций ОС — через механизмы синхронизации и системные вызовы — к внутреннему устройству ядра и инфраструктуре.

### Основы

Фундаментальные абстракции: процесс, поток, файловый дескриптор, виртуальная память, файловая система, планировщик.

- [Что такое операционная система](foundations/00-what-is-os.md) — три проблемы без ОС, абстракция, изоляция, разделение ресурсов
- [Режимы CPU и системные вызовы](foundations/01-cpu-modes-and-syscalls.md) — ring 0/3, механизм syscall, vDSO, буферизация
- [Процессы](foundations/02-processes.md) — fork/exec/wait, copy-on-write, зомби, сироты
- [Потоки](foundations/03-threads.md) — clone(), kernel vs user threads, общая память
- [Файловые дескрипторы](foundations/04-file-descriptors.md) — «всё — файл», три уровня таблиц, dup2, pipe
- [Виртуальная память](foundations/05-virtual-memory.md) — страницы, MMU, TLB, page fault, demand paging, CoW
- [Файловые системы](foundations/06-filesystems.md) — inode, журналирование, page cache, fsync
- [Планировщик](foundations/07-scheduler.md) — CFS, vruntime, вытеснение, nice, RT-политики
- [Права доступа и capabilities](foundations/08-permissions-and-capabilities.md) — UID/GID, rwx, setuid, umask, capabilities, сброс привилегий

### Конкурентность

Синхронизация потоков и модель памяти.

- [Синхронизация](concurrency/00-synchronization.md) — race condition, CAS, мьютекс, futex, condition variable
- [Модель памяти](concurrency/01-memory-ordering.md) — torn read/write, Relaxed, Acquire/Release, SeqCst
- [Lock-free структуры](concurrency/02-lock-free.md) — стек Трейбера, ABA, tagged pointers, RCU

### Системное программирование

Практический API: сигналы, mmap, файловый ввод-вывод, сокеты, мультиплексирование.

- [Сигналы](programming/00-signals.md) — sigaction, async-signal-safety, signalfd
- [Отображение памяти](programming/01-memory-mapping.md) — mmap (PRIVATE/SHARED/ANONYMOUS), mprotect, POSIX shared memory
- [Файловый ввод-вывод](programming/02-file-io.md) — O_DIRECT, O_SYNC, readv/writev, file locking
- [Сокеты](programming/03-sockets.md) — TCP server/client, Unix domain sockets, sendfile
- [Мультиплексирование ввода-вывода](programming/04-io-multiplexing.md) — select → epoll → io_uring, timerfd, eventfd
- [Управление памятью](programming/05-memory-management.md) — huge pages, THP, overcommit, OOM killer, NUMA
- [Межпроцессное взаимодействие](programming/06-ipc.md) — семафоры, очереди сообщений, System V IPC, передача fd

### Ядро

Внутреннее устройство: как работают syscall, прерывания, драйверы, сетевой стек.

- [Механизм системных вызовов](kernel/00-syscall-internals.md) — LSTAR, sys_call_table, pt_regs, KPTI
- [Прерывания](kernel/01-interrupts.md) — top/bottom half, softirq, tasklet, workqueue, NAPI
- [Устройства и драйверы](kernel/02-devices-and-drivers.md) — file_operations, udev, модули, /proc, /sys, I/O scheduler
- [Сетевой стек](kernel/03-network-stack.md) — NIC → DMA → NAPI → IP → netfilter → TCP → socket buffer
- [Управление памятью ядра](kernel/04-memory-management.md) — buddy allocator, slab/SLUB, зоны, watermarks, kswapd, direct reclaim, writeback

### Инфраструктура

Как программа попадает в память, как работает терминал, как наблюдать за системой, как она загружается.

- [ELF и линковка](infrastructure/00-elf-and-linking.md) — PLT/GOT, динамический линковщик, LD_PRELOAD, ASLR
- [Терминалы](infrastructure/01-terminals.md) — PTY, line discipline, raw mode, job control, SSH
- [Трассировка](infrastructure/02-tracing.md) — strace, perf, eBPF/bpftrace, ptrace, GDB
- [Загрузка системы](infrastructure/03-boot.md) — UEFI → загрузчик → vmlinuz → initramfs → systemd

### Контейнеры

Изоляция без виртуализации.

- [Пространства имён и контрольные группы](containers/00-namespaces-and-cgroups.md) — 8 типов namespaces, cgroups v2, OOM per-cgroup
- [Контейнеры](containers/01-containers.md) — overlay FS, seccomp, capabilities, Docker, container vs VM

## Как всё связано

**Изоляция vs производительность:** процессы полностью изолированы (fork ~50 мкс), потоки разделяют память (clone ~10 мкс) но требуют синхронизации. Выбор определяет архитектуру: Redis — однопоточный с epoll, PostgreSQL — процесс на соединение, Go — горутины поверх пула потоков.

**Безопасность vs скорость:** ring 0/3 = syscall overhead ~200 нс. vDSO и futex минимизируют переходы в ядро. io_uring убирает syscall на горячем пути через shared memory. Каждый шаг — компромисс между защитой и латентностью.

**Durability vs латентность:** write() в page cache мгновенный, fsync() гарантирует запись на диск но стоит ~50 мкс (SSD) — ~10 мс (HDD). Базы данных балансируют между потерей данных при сбое и пропускной способностью.

**Справедливость vs отзывчивость:** CFS балансирует через vruntime — интерактивные потоки с низким vruntime мгновенно получают CPU. RT-потоки (SCHED_FIFO) нарушают справедливость ради гарантий латентности.

**Атомарность vs throughput:** мьютексы сериализуют доступ, lock-free структуры дают параллелизм за счёт сложности (ABA, memory reclamation). На практике мьютекс + правильная структура данных побеждает lock-free в большинстве случаев.

**Абстракция vs контроль:** epoll абстрагирует readiness, io_uring даёт batched submission ценой сложности API. O_DIRECT обходит page cache, давая контроль ценой потери read-ahead.

## См. также

- [Аппаратное обеспечение](../computer/index.md) — CPU, кеш, RAM, хранилище, шины
- [PostgreSQL](../databases/postgresql/index.md) — shared_buffers и page cache, WAL и sequential I/O, MVCC и процессы
- [Redis](../databases/redis/index.md) — event loop на epoll, fork+CoW для BGSAVE
- [System Design: кеширование](../system-design/07-caching.md) — иерархия латентностей

## Sources

- Michael Kerrisk, 2010, *The Linux Programming Interface*: https://man7.org/tlpi/
- Robert Love, 2010, *Linux Kernel Development* — 3rd edition
- Brendan Gregg, 2019, *BPF Performance Tools* — Addison-Wesley
- Abraham Silberschatz, Peter B. Galvin, Greg Gagne, 2018, *Operating System Concepts* — 10th edition
