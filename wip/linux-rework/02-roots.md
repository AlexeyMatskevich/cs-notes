# Корневые причины — linux/foundations/

## Обзор

Серия проходит naive reader CLEAR по всем 9 файлам, метаязык инструкции (§0.2) не протекает, фактическая база в целом корректна (одна реальная арифметическая ошибка, одна реальная неполнота модели capabilities, остальное — порядковые оценки). Дуга серии держится: каждая заметка открывается причинным мостиком, what-is-os ставит обещание про планировщик, scheduler его закрывает через восемь заметок, processes→threads работает через productive pivot.

Главный корень один и крупный: **в объёмных файлах результат сформулирован как тема целиком, а не как один сдвиг, управляющий глубиной**. Это §1 styleguide дословно: «автор инстинктивно начинает с темы, а не со сдвига». Проявляется в virtual-memory (5821w, семь независимых сдвигов), filesystems (4518w, два сдвига делят файл пополам), cpu-modes (stdio-хвост как отдельная мини-заметка), threads и scheduler (хвосты с альтернативными темами). Все остальные крупные находки — производные от него или независимые L1-L2 механические проблемы (slug-form якоря в 12 из 15 wikilinks с anchor, «мы видели» как метаязык документа в 5 файлах, точечная ошибка арифметики, неполный список наборов capabilities).

Файлы **what-is-os, processes, file-descriptors** корректны по §1/§3/naive-reader и требуют только L1 механических правок (якоря, один factcheck, один «мы видели», L2 compress CoW в processes). **permissions-and-capabilities** корректен содержательно, но требует L1 factcheck (capabilities 3→5 наборов) и L4-решение по позиции в серии (branch vs continuation). L3+ структурная работа нужна в **virtual-memory, filesystems, cpu-modes-and-syscalls**; **threads и scheduler** — граничные, compress хвостов уровня L2.

## Root cause 1: Результат как тема, а не как сдвиг

**Симптомы из линз:**
- §1 Результат: virtual-memory (7 независимых входных вопросов и ответов в одном файле: изоляция, TLB shootdown, demand paging, CoW, overcommit, address space layout; все 6 разделов после §«Механизм целиком» закрываются самостоятельно и не порождают следующий); filesystems (два сдвига — «общая задача FS» и «устройство ext4» — делят файл пополам: fast symlink, extent-деревья, три режима журналирования, сравнение ext4/XFS работают на второй сдвиг); cpu-modes (3 режима буферизации stdio + fread/read разбор 8192-байт буфера отвечают на «как устроена буферизация stdio», не на «стоимость syscall»); threads (1:1/N:1/M:N/горутины GMP отвечают на «модели параллелизма»); scheduler (RT-политики, NUMA, perf sched — каждая тема со своим сдвигом).
- §3 Дуга: cpu-modes-and-syscalls — stdio-хвост после закрытия основной дуги «vDSO как ответ на цену» (second-half drift); filesystems — preview «пять компонентов» до мотивации каждого.
- §4 Нагрузка: virtual-memory 12 ##-секций против предельных 5-6 в §4.1, 3+ признака split; filesystems 11 ##-секций; scheduler и cpu-modes нагружены локально.

**Корень:** автор формулирует результат как «тема» («виртуальная память в Linux», «устройство файловой системы»), а не как конкретный сдвиг в голове читателя. Тогда глубина перестаёт управляться сдвигом — текст растёт за счёт соседних результатов, каждый раздел ставит собственный входной вопрос, закрывает его и не порождает следующий. Тест §1 «убери внутреннее устройство, оставь что делает + цена» даёт для этих файлов нет: TLB shootdown и PCID, extent-деревья, три режима журналирования, три режима буферизации удаляемы для объявленного сдвига — но они нужны для других сдвигов, значит пол другой заметки.

**Уровень:** L3-L5 в зависимости от файла (virtual-memory → L5 split; filesystems → L4 split/compress; cpu-modes → L3 relocate; threads/scheduler → L2-L3 compress).

**Стратегии:**
- A: split virtual-memory на три заметки с собственными сдвигами — (а) трансляция и изоляция: страницы + page table + MMU + CR3 + address space layout; (б) отложенные механизмы через page fault: demand paging + CoW + overcommit; (в) TLB и стоимость трансляции: TLB + PCID + shootdown. Trade-off: потеря единой точки входа «виртуальная память», нужен overview-файл в foundations/virtual-memory/; три заметки со своими сдвигами вместо одной с семью; выигрыш в каждом сдвиге управляет своей глубиной.
- B: split filesystems на две заметки — (а) общий механизм FS: inode + directory + VFS + page cache + journal + fsync; (б) ext4-specifics: extent-деревья, три режима журналирования, сравнение с XFS, fast symlink. Trade-off: теряется «одно чтение — полная картина», зато каждая заметка по 2-2.5k слов с ясным сдвигом. Альтернатива: compress в одном файле — свернуть ext4-детали до упоминаний и убрать сравнение XFS.
- C: relocate stdio-хвоста cpu-modes-and-syscalls в `programming/file-io.md` (по Предпосылкам stdio туда логически принадлежит) + оставить в cpu-modes один абзац-указатель «стоимость syscall делает буферизацию ключевой оптимизацией, см. file-io». Trade-off: cpu-modes-and-syscalls сжимается до ~2k слов с чистой дугой «граница → syscall → цена → vDSO», stdio получает свой сдвиг.
- D: compress threads и scheduler хвостов — M:N/горутины → 1 абзац «1:1 upired в стеки ядра; альтернатива — user-space потоки, мультиплексируемые на OS-поток, см. Go/Ruby Fiber»; RT/NUMA/perf в scheduler → по 3-5 строк каждая с cross-link. Trade-off: полные разборы переезжают в будущие специализированные заметки, но сдвиг основной заметки остаётся чистым.

**Рекомендация:** все четыре стратегии комплементарны, выполняются независимо. A (split virtual-memory) — самое тяжёлое, самое нужное. B (filesystems) — «вопрос пользователю»: split или compress. C и D — явные compress/relocate без альтернатив.

## Root cause 2: Slug-form якоря в wikilinks с anchor

**Симптомы из линз:**
- §Integration: 12 из 15 wikilinks с якорями в slug-форме (нижний регистр, дефисы вместо пробелов/двоеточий/скобок). Файлы: cpu-modes (52, 101×2), processes (35, 89, 259 с доп. markdown-нарушением), threads (26, 30, 42, 89), file-descriptors (95, 235), virtual-memory (90, 141, 174), filesystems (25), scheduler (37, 41, 45×3, 91), permissions (25, 226). Правильных примеров три: `#OOM killer: последняя линия защиты`, `#Динамический линкер: ld-linux`, `#exec(): замена программы`.
- Плюс одно markdown-с-якорем нарушение §6.3 (processes.md:259: `[паттерне демонизации](../infrastructure/terminals.md#паттерн-демонизации)` — должен быть wikilink).
- Плюс смешение wikilink/markdown для `../`-путей в 4 файлах (file-descriptors:23,222; scheduler:75; processes:39; threads и file-descriptors на signals/sockets).

**Корень:** автор знает правильный формат (есть три примера), но большинство инстанций написаны по slug-привычке (GitHub/Quartz интуиция). По §6.3 для Obsidian якорь wikilink должен буква-в-букву повторять текст заголовка. Правка механическая: grep по `#[a-zа-я-]+` в wikilinks, замена на точный текст.

**Уровень:** L1 (инварианты — контракт на корректность ссылок; feedback_obsidian_anchors прямо это фиксирует).

**Стратегии:**
- A: проход по всем 9 файлам, механическая замена slug → точный текст заголовка. Одна Edit-сессия per файл. Trade-off: нет.

**Рекомендация:** A. Main agent сам, одна сессия на файл.

## Root cause 3: Самореферентные обороты «мы видели/создали/разобрали»

**Симптомы из линз:**
- §Check: 5 из 9 файлов с «мы видели» как документной кросс-референцией. processes.md:150 «Мы создали процесс и загрузили программу», processes.md:279 «все части... лежат перед нами, можно проследить»; virtual-memory.md:25 «В [что такое ОС] мы уже видели эту ситуацию», virtual-memory.md:206 «В [процессах] мы видели, что fork()», virtual-memory.md:326 «Разобрав все компоненты... проследим сценарий»; filesystems.md:321 «Мы уже видели, что write()»; scheduler.md:20-21 «В первой заметке о [задачах ОС] мы сказали»; permissions.md:25, 46, 292 (три случая).

**Корень:** §0.2 styleguide прямо даёт форму: «выше видели, как X замедляет Y» (пересказ факта) vs «мы видели» (пересказ документа). Подлежащее «мы» + сказуемое действия текста («видели/создали/разобрали») превращает предмет внимания с темы на документ. Автор знает правило (в серии нет метатерминов «нарратив», «мостик», «дуга»), но самореференция проскакивает на стыках заметок и перед финальными walkthrough.

**Уровень:** L1 (инварианты — §0.2 чистый язык).

**Стратегии:**
- A: проход по 5 файлам, переформулировать каждую фразу на предметную. Примеры готовы в check.md: «fork() создаёт дочерний процесс — копию родительского» вместо «Мы видели, что fork() создаёт...»; «fork, exec, состояния... складываются в один жизненный цикл. Проследим его» вместо «все части лежат перед нами»; «В [что такое ОС] эту ситуацию разбирали на примере двух программ без ОС» вместо «мы уже видели». Trade-off: нет.

**Рекомендация:** A. Main agent сам, точечные Edit на каждое вхождение.

## Root cause 4: Фактические точечные ошибки и неполнота модели

**Симптомы из линз:**
- §Factcheck L1 #1: virtual-memory.md:234 — «Redis-сервер с 10 ГБ данных вызывает fork() — ребёнок получает page table за ~100 мкс». Арифметическая ошибка: для 10 ГБ RSS page table ~20 МБ, копирование ~500-1000 мкс. 100 мкс — это для 1 ГБ (правильно указано на строке 218). Искажает модель Redis BGSAVE, где медленный fork — реальный источник p99-latency spike.
- §Factcheck L1 #2: permissions-and-capabilities.md:178-184 — описаны три набора capabilities (Permitted/Effective/Inheritable) вместо пяти. Пропущены Bounding (основной механизм Docker/containerd/runc, строка 226 уже упоминает Docker) и Ambient (добавлен в 4.3 для передачи caps в не-setcap бинарники).
- §Factcheck L2: cpu-modes:72 «~340 системных вызовов» (на 6.x — более 460, устаревшее число); cpu-modes:163 «musl BUFSIZ 4096 или 1024» (в musl BUFSIZ=1024, 4096 — FreeBSD); processes:220 «systemd поднимает pid_max до 4194304» (4194304 — PID_MAX_LIMIT ядра, systemd его активирует, а не выбирает); threads:109 «процесс с 10 потоками получает в 10 раз больше CPU если не cgroups» (autogroup включён по умолчанию с 2.6.38); scheduler:142 «sched_min_granularity 1-4 мс» (mainline default 0.75 мс).

**Корень:** смешанный. L1 (#1 и #2) — реальные ошибки, искажающие модель читателя. L2 — числовые оценки без привязки к железу/версии ядра, устаревшие числа API, атрибуция ядерных констант userspace-инструментам. Источник: curse of knowledge (автор знает детали на момент записи) + отсутствие явной оговорки «на Intel Skylake, ядро 6.x».

**Уровень:** L1 для двух пунктов (Redis fork арифметика и capabilities 3→5), L2 для остальных.

**Стратегии:**
- A: L1-пункты — точечные Edit. Для Redis: «10 ГБ → ~20 МБ page table → 500-1000 мкс». Для capabilities: расширить раздел до пяти наборов с коротким описанием Bounding (Docker) и Ambient (не-setcap бинарники). Остальные L2 — точечные уточнения по контексту правки (обновить ~340 → «более 450», «musl BUFSIZ 1024», «systemd упирает в потолок ядра PID_MAX_LIMIT», «autogroup включён по умолчанию», «mainline default 0.75 мс»). Trade-off: нет.

**Рекомендация:** A. Main agent сам.

## Root cause 5: Forward-references к терминам без inline-глоссы

**Симптомы из линз:**
- §Читатель: cpu-modes-and-syscalls.md:101 — TLB среди косвенных стоимостей syscall без опоры (TLB определён только через три файла в virtual-memory); cpu-modes:125 — «страницы 8 КБ» в vDSO без определения страницы; processes.md:83-89 — полный раздел CoW с механизмом page fault, read-only, копированием 4 КБ до введения виртуальной памяти (+ дублирование с virtual-memory:205-254); virtual-memory.md:186 — VMA появляется в алгоритме page fault без inline-глоссы; virtual-memory.md:196 — ссылка на ELF-заголовок как существенный шаг механизма demand paging без Предпосылки.

**Корень:** §2 контракт Предпосылок: термин появляется только если объяснён выше, прямо сейчас, или в Предпосылках. Forward-reference создаёт скрытую предпосылку в пределах серии. Особенно заметно между cpu-modes (TLB, страницы) и virtual-memory (где они вводятся), а также processes CoW, который объясняет механизм до того, как введена виртуальная память.

**Уровень:** L1-L2. TLB и VMA — L1 (inline-глосса + forward wikilink решает); CoW в processes — L2 (сократить раздел до functional gloss «fork не копирует 2 ГБ, потому что страницы разделяются до первой записи; полный механизм — в virtual-memory», полный разбор оставить в virtual-memory).

**Стратегии:**
- A: в cpu-modes-and-syscalls заменить «TLB» на inline-глоссу «TLB — кеш трансляций, теряет актуальность при переключении» с forward wikilink, либо снять пункт, оставив «промахи кешей» (читатель не теряет модель «syscall дорогой»). В virtual-memory переместить inline-глоссу VMA в первое использование. В processes сократить CoW до 1-2 предложений + wikilink на virtual-memory. Trade-off: нет.

**Рекомендация:** A. Main agent сам.

## Root cause 6: Наивная модель декларируется, но не используется как рычаг

**Симптомы из линз:**
- §Читатель: processes — наивная модель «процесс = запущенная программа» названа, но вход в fork не использует более глубокую ошибку «новый процесс = новая программа = отдельный старт с нуля» как разрыв; file-descriptors — «fd как просто число» названа неявно, но трёхуровневая структура объясняется не как ответ на разрыв (fork+offset загадка приходит только после схемы); filesystems — модель «файл = данные в файле, write = на диск» не ломается явно во входе, сдвиг «имя отдельно от inode» приходит позже; scheduler — наивная модель «планировщик даёт поровну» не названа, CFS вводится как ответ на round-robin, а не как ответ на ошибку читателя; permissions — вход через перечень требований Nginx, а не через слом «root/обычный хватит»; threads — модель «поток = лёгкий процесс» не оспорена явно.

**Корень:** §2 conceptual change (Posner & Strike): пока наивная модель не названа и не показана как несостоятельная, новая не приживается. Мотивация через сценарий («нужно ещё одну вещь») работает слабее, чем слом схемы («кажется X — на самом деле Y»). Автор знает правильную модель и инстинктивно даёт её сразу; рычаг «увидеть, с чем придёт читатель» использован частично.

**Уровень:** L2 (дуга/мотивация — тексты читаются, но не ведут через слом схемы).

**Стратегии:**
- A: в каждом файле с пропущенным рычагом добавить 1-2 фразы «Кажется, что X. На самом деле Y, и вот почему» во вход. Для permissions — полная переработка входа Nginx: «Кажется, хватает двух уровней — root и обычный. Но посмотрим, что нужно Nginx: порт 80 без доступа к /etc/shadow, собственные логи без права трогать PostgreSQL. Одного флага „root/не-root" недостаточно». Trade-off: удлиняет вход на 2-4 строки, но существенно усиливает мотивацию.

**Рекомендация:** A. Main agent сам, один блок на файл.

## Root cause 7: Пропущенные места активной обработки в threshold-заметках

**Симптомы из линз:**
- §Проверка: threads.md — threshold-концепция гонки данных, но диаграмма counter++ подаётся post-factum; нет вопроса-предсказания перед ней; file-descriptors.md — трёхуровневая таблица контринтуитивна, но нет `<details>`-задачи про shared offset в fork; virtual-memory.md — самый тяжёлый файл (5821w, 8+ концепций: страницы, page table, MMU, TLB, page fault, demand paging, CoW, overcommit, address space), при этом ни одного `<details>`-блока самопроверки. В cpu-modes, filesystems, scheduler, permissions такие блоки есть и работают.

**Корень:** §5 self-explanation effect (Chi): материал усваивается глубже, когда подводит читателя к ответу, который тот может дать сам. Для threshold-концепций это особенно важно — без активной обработки старая модель сосуществует с новой. В virtual-memory несколько естественных точек для предсказания (сколько фреймов выделится после malloc(1 GB); что произойдёт с R/W-битом, если один из двух CoW-участников делает exit; что увидит следующая запись родителя после fork+write в ребёнке).

**Уровень:** L2 (файловый паттерн, не точечный; паттерн применяется уже в половине файлов серии).

**Стратегии:**
- A: добавить один `<details>`-блок самопроверки в threads (перед диаграммой counter++), в file-descriptors (перед разделом «fork и разделённое смещение»), 1-2 в virtual-memory (malloc(1 GB) и CoW exit). Trade-off: удлиняет файлы на 10-20 строк каждый, но активирует threshold-переход.

**Рекомендация:** A. Main agent сам; формулировки задач готовы в check.md.

## Root cause 8: V-shape пробелы к computer/programmer-model/

**Симптомы из линз:**
- §Integration: регистры CPU (`rax`, `rsp`, `rbp`, `rip`) в cpu-modes, processes, scheduler — ни разу не залинкован `computer/programmer-model/isa.md`; ABI calling convention в cpu-modes:58 (System V AMD64: номер в rax, аргументы в rdi/rsi/...) — не залинкован `abi-and-data-layout.md`; SIMD-регистры FPU/SSE/AVX в scheduler:41 — не залинкован `simd.md`; pipeline flush в cpu-modes:101 — не залинкован `computer/cpu/out-of-order-execution.md`; TLB как кеш — не явная опора на `computer/data-path/cache-internals.md`.

**Корень:** §2 слои зависимостей. Термины вводятся как данность, хотя `computer/programmer-model/` их объясняет. Читатель видит имена без ментальной опоры. V-shape bottom не закрыт: есть ссылки на computer/computer.md overview, но нет точечных на конкретные модели.

**Уровень:** L3 (полнота — текст понятен, но читатель не опирается на уже существующие заметки).

**Стратегии:**
- A: добавить точечные cross-link при первой содержательной встрече в каждом разделе — одна фраза-ссылка, не переобъяснение. Пример: «порядок регистров следует [System V AMD64 calling convention](../../computer/programmer-model/abi-and-data-layout.md)». Trade-off: нет, только выигрыш.

**Рекомендация:** A. Main agent сам, в ходе L1 правок.

## Root cause 9: Позиция permissions-and-capabilities в серии

**Симптомы из линз:**
- §Дуга: мостик с scheduler формально причинный («scheduler не спрашивает, имеет ли процесс право»), но permissions по содержанию — параллельная подсистема (security), а не следующий слой. Реально заметка опирается на processes (UID/GID в task_struct, fork/exec), file-descriptors (open, проверка прав), filesystems (inode, rwx-биты) — ни одна зависимость не идёт от scheduler. Read-through от scheduler к permissions ощущается как «закончили основную линию, теперь добавим безопасность».

**Корень:** §3 дуга — позиционный vs содержательный переход. Серия имеет параллельные ветки, но сейчас мостик маскирует branch под continuation. Решение на уровне плана изучения linux.md (порядок), а не внутри файла.

**Уровень:** L4 (structural — изменение порядка в `linux.md` / linux/foundations overview, вопрос каскадных обновлений в prev/next навигации).

**Стратегии:**
- A: переместить permissions раньше — после file-descriptors или filesystems, где проверка прав при open() впервые становится мотивированной. Trade-off: нужно обновить навигацию в нескольких файлах, мостики с scheduler/filesystems. Основная линия foundations становится: what-is-os → cpu-modes → processes → threads → file-descriptors → permissions → virtual-memory → filesystems → scheduler (или аналогичная вставка).
- B: оставить на месте, но явно пометить как начало security-ветки. Мостик: «Основная линия (time/memory/storage) закрылась. Параллельно ядро решает другой вопрос — кто имеет право». Trade-off: нет перестановки, но читатель сразу понимает, что это branch.

**Рекомендация:** вопрос пользователю. Обе стратегии работают; A точнее по дуге, B дешевле. Решение требует понимания, что пользователь хочет от серии (линейный курс vs модульная справка).

## Layer gaps

- **red-black-tree** (algorithms-and-data-structures/non-linear/)
  - Нужна для: scheduler.md:119 (CFS/EEVDF runqueue), virtual-memory.md:188 (VMA lookup)
  - Что это: самобалансирующийся BST с цветами узлов и ограниченными ротациями, amortized O(log n) с малой константой
  - Зачем в репо: два независимых потребителя в foundations/ (§9 structure-guide порог для выделения shared-заметки). Обе текущие ссылки ведут на parent binary-search-tree.md, что не раскрывает specific свойства red-black. Читатель planner'а не видит, почему именно red-black, а не AVL/hash-table/skip-list.
  - Обнаружено: 2026-04-23 /deep-rework linux

Остальные кандидаты (IBRS, SELinux/AppArmor/PAM/ACL, no_new_privs, autogroup, seccomp-BPF) не проходят порог: либо debatable, либо уже покрыты inline-расшифровкой, либо помечены автором как будущие заметки, либо есть в CLAUDE.md как deferred (seccomp-BPF).

## Файлы без существенных находок

- **what-is-os.md** — §1 корректен, §3 корректен, naive-reader CLEAR, одна точечная правка по §0.2 не требуется. Единственное — NVMe SQ/CQ/Doorbell детали ниже пола (§4 Нагрузка), compress точечный.
- **processes.md** — §1 корректен, §3 корректен, naive-reader CLEAR. L2 compress CoW (дублирует virtual-memory), L1 «мы видели» ×2, L1 slug-якоря ×3, L2 improve naive model рычаг. Всё механическое.
- **file-descriptors.md** — §1 корректен, §3 корректен, naive-reader CLEAR. L1 slug-якоря ×2, L1 format ../ paths, L2 `<details>`-задача shared offset, L2 naive model рычаг. Всё механическое.

permissions-and-capabilities.md без L3+ работы содержательно, но имеет L1 factcheck (3→5 capabilities sets), L1 slug-якоря, L1 «мы видели» ×3, L4 решение по позиции в серии.

## Рекомендация по структуре фазы 4

Разнести работу **по природе операции, а не по файлу**:

1. **Main agent сам (L1 механические правки, один проход на файл):**
   - Slug-form якоря в wikilinks — 12 инстанций в 6 файлах.
   - «Мы видели/создали/разобрали» — переформулировка на предметную в 5 файлах.
   - Factcheck L1: virtual-memory:234 Redis fork арифметика; permissions:178-184 три→пять наборов capabilities.
   - Factcheck L2: cpu-modes (~340→450, musl BUFSIZ), processes (pid_max атрибуция), threads (autogroup), scheduler (min_granularity 0.75 мс), cpu-modes (vvar тик 1-10 мс).
   - Forward-references inline-глоссы: TLB в cpu-modes, VMA position в virtual-memory.
   - V-shape cross-link к computer/programmer-model/: регистры (isa.md), ABI (abi-and-data-layout.md), SIMD (simd.md), pipeline (out-of-order-execution.md), TLB↔cache (cache-internals.md).
   - Дублирование объяснений: CoW в processes → compress до functional gloss; context switch в scheduler → ссылка на processes.
   - Naive-model рычаги: 1-2 фразы во входе 5 файлов.
   - `<details>`-задачи самопроверки: threads (counter++), file-descriptors (shared offset), virtual-memory (malloc(1GB), CoW exit) — 3-4 блока.
   - Формат ссылок: wikilink/markdown нормализация для ../ путей.
   - Compress хвостов: threads (M:N → 1 абзац), scheduler (RT/NUMA/perf → compact).

2. **Writer teammates (L3+ structural, параллельно в разных worktree):**
   - virtual-memory split на 3 заметки (трансляция/эффекты/TLB-стоимость) + overview-файл virtual-memory.md в foundations/virtual-memory/. Крупнейшая работа, самая нужная.
   - filesystems split или compress — «вопрос пользователю» по стратегии B в Root cause 1.
   - cpu-modes-and-syscalls stdio-хвост relocate в programming/file-io.md.

3. **Main agent как каскад (L4 structural):**
   - Решение по позиции permissions (Root cause 9) — «вопрос пользователю», после ответа каскадно обновить linux.md Порядок изучения, prev/next навигацию, мостики в связанных файлах.
   - После virtual-memory split: обновить все wikilink-якоря, указывающие на `virtual-memory#X`, во всех 30 файлах серии linux/ и в зависимых доменах (ruby/internal/, databases/postgresql/, databases/redis/).
   - layer-gaps.md: добавить red-black-tree кандидата.

Порядок: сначала main agent идёт через L1-L2 механику (она не зависит от split-решений и снижает шум для writer-teammates). Параллельно сформулировать «вопросы пользователю» по стратегиям virtual-memory split (принимает ли A без альтернатив), filesystems (A split или compress), permissions (A move или B explicit branch). После ответов — запускать writer-teammates на L3+ работу в параллельных worktree.
