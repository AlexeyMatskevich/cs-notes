# Линза Integration — linux/foundations/

## Сводка

Папка хорошо интегрирована вверх (есть секции «См. также» к Ruby, Redis BGSAVE и PostgreSQL WAL) и вниз (все файлы имеют `computer/`-ссылки из `Предпосылки`). Основная systemic проблема Focus A — **slug-form якоря** (нижний регистр, дефисы вместо пробелов/двоеточий) вместо точного текста заголовка по §6.3: нарушены почти во всех ссылках с anchor'ом и во всех файлах, кроме `what-is-os.md`, `file-descriptors.md`, `filesystems.md`. Вторая по тяжести — смешение форматов: markdown с anchor там, где §6.3/§6.5 прямо требуют wikilink, плюс wikilinks на `../`-пути там, где §6.5 требует markdown. Focus B: узкие реальные пробелы — `processes.md` не мотивирует fork+CoW вверх как паттерн Redis/PostgreSQL (упоминание convert остаётся локальным), `scheduler.md` не связывает FPU/SSE/AVX регистры вниз с `computer/programmer-model/` и не мотивирует preemption как причину GIL-latency.

## По файлам

### what-is-os.md

#### Фокус A: reference integration

**Integrated links findings:**

- what-is-os.md:41. Два повторных использования концепций из Предпосылок (`процессоре`, `оперативной памяти`) — оба помечены cross-link на `../../computer/computer.md`. Это верно по §6.2, но ссылка ведёт на overview-файл целиком, хотя нужны конкретные модели (CPU, RAM). Класс: correct (якорь).
- what-is-os.md:146–164. Раздел «Три задачи операционной системы» впервые предъявляет термин «виртуальная память» с ссылкой на `virtual-memory.md` (forward-reference, ок). Но MMU и page fault появляются ещё четыре раза в том же разделе без ссылки — у читателя, не знакомого с этими терминами, локальной опоры нет. Класс: correct.
- what-is-os.md:182–198. Термин «планировщик» используется четыре раза в пределах одного раздела «Распределение ресурсов» с повторяющимся cross-link на `scheduler.md`. По §6.2 это корректно (каждое новое содержательное упоминание в новой строке), но читается шумно — первые два упоминания стоят в одном абзаце. Класс: correct (минорно — это forward-reference, первая встреча в одном абзаце не требует второго link'a).
- what-is-os.md:195–198. «процесс» (cross-link на `processes.md`) используется три раза в одном коротком абзаце — первое вхождение корректно, второе и третье на соседних строках также залинкованы. По §6.2 «максимум одна ссылка на концепцию в одной строке» — правило не нарушено (ссылки на разных строках), но визуально перегружено. Класс: correct (стилистический шум, не баг).

**Якоря findings:**

- what-is-os.md:14 (Предпосылки). Ссылка `[аппаратное обеспечение](../../computer/computer.md) (CPU, кеш, RAM, хранилище, DMA)` — целевой файл это overview всего домена, а Предпосылки перечисляют конкретные концепции (CPU, кеш, RAM). Якорь на раздел `#Путь данных` в `computer.md` дал бы точечный landing, но overview-файл — исключение, где общая ссылка допустима. Класс: acceptable (не требует правки).
- what-is-os.md:41. `[процессоре](../../computer/computer.md)`, `[оперативной памяти](../../computer/computer.md)` — обе ссылки ведут на один overview-файл. Для «оперативной памяти» лучше якорь на `#Путь данных` или прямо на `../../computer/data-path/ram.md`. Класс: correct (не помогает читателю сверить точное значение).

**Формат ссылок findings:**

- what-is-os.md:14, 41, 78, 153, 182, 184, 195, 196, 198. Все ссылки markdown с `../../`-префиксом — по §6.5 это правильный формат. Никаких нарушений.

**Внутренние якоря findings:**

- Не применимо: файл короткий (257 строк), концепции определяются последовательно без повторных содержательных упоминаний в далёких разделах.

**Wip-queue кандидаты:**

- what-is-os.md:41. Термин «плоское адресное пространство» (обсуждается до введения VM) используется как данность; в `../../computer/data-path/ram.md` RAM описана как массив байт, но «плоское адресное пространство физической RAM» как отдельная концепция может требовать уточнения. Однако в контексте заметки (проблема ломается без ОС) этого достаточно из Предпосылок. Не wip-кандидат.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- what-is-os.md:24. «bare-metal» введён хорошо, но связь с инструкциями CPU из `../../computer/programmer-model/isa.md` (код исполняется напрямую, без посредника) оставлена за скобками — читатель видит только функциональный эффект. Исправлять не нужно: Предпосылки покрывают.
- what-is-os.md:146–164. MMU описан как «аппаратный блок процессора» — это функциональный уровень, достаточный для заметки верхнего уровня. Ссылка вниз на `virtual-memory.md` (вперёд в серии) прозрачно подготавливает. Нет явных пробелов.

**Missing upward motivation:**

- what-is-os.md:195–198. «RAM, дисковый I/O, сокет» — перечисление типов ресурсов, которыми занимается ОС. Здесь логичная точка для forward-ссылки на `filesystems.md` и `cpu-modes-and-syscalls.md` — но обе есть выше. Можно в этом же блоке упомянуть, что shared_buffers PostgreSQL и shared memory Redis — это частные случаи, которые VM отдаёт процессам; но файл открывающий, сюда такая мотивация не нужна — она рассыпает дугу.

### cpu-modes-and-syscalls.md

#### Фокус A: reference integration

**Integrated links findings:**

- cpu-modes-and-syscalls.md:16. Регистры CPU описаны в Предпосылках inline («именованные ячейки хранения…»), и ссылка на `../../computer/programmer-model/isa.md` ведёт на ISA. В тексте дальше регистры `rax`, `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`, `rcx`, `r11`, `rip`, `rsp`, `rflags` упоминаются многократно (строки 58, 66, 68, 72–74) — ни одна из этих содержательных встреч не имеет cross-link на ISA или abi. Читатель, вернувшийся в середину файла, не видит, откуда берутся имена регистров. Класс: correct (нужна интегрированная ссылка при первой содержательной встрече в каждом новом разделе).
- cpu-modes-and-syscalls.md:58. «соглашение следующее: номер syscall — в `rax`, аргументы — в `rdi`, `rsi`…» — это прямое описание ABI (System V AMD64 ABI calling convention). Существует `../../computer/programmer-model/abi-and-data-layout.md`, но cross-link в тексте отсутствует — хотя это точный случай §6.2 «локальная опора на правильное место репозитория». Класс: correct.
- cpu-modes-and-syscalls.md:72. «находит нужную функцию в таблице системных вызовов (sys_call_table)» — ровно та точка, где уместна ссылка на `../kernel/syscall-internals.md#sys_call_table: массив обработчиков`. В данный момент ссылки нет, читатель смотрит только на локальное пояснение. Класс: correct.
- cpu-modes-and-syscalls.md:101. Описаны «переключение таблиц страниц (KPTI)» и «IBRS» — KPTI залинкована на `syscall-internals.md#kpti-двойные-таблицы-страниц` (якорь неправильный, см. ниже), IBRS — без ссылки. IBRS — отдельная концепция, в репо её нет (кандидат в wip-queue).
- cpu-modes-and-syscalls.md:213. «принцип тот же, что у [буферного кеша PostgreSQL]» — интегрированная ссылка как пример по §6.2. Корректно. Но здесь же разумно дать якорь на раздел конкретного механизма, а не весь buffer-cache.md. Класс: correct (якорь).

**Якоря findings:**

- cpu-modes-and-syscalls.md:52. Wikilink `[[linux/kernel/syscall-internals#kpti-двойные-таблицы-страниц|KPTI]]`. Реальный заголовок в target: `### KPTI: двойные таблицы страниц` (строка 172 `syscall-internals.md`). Якорь должен быть `#KPTI: двойные таблицы страниц` — с оригинальным регистром, пробелами, двоеточием. Текущая форма — slug-version (GitHub/Quartz slug), по §6.3 не работает. Класс: correct.
- cpu-modes-and-syscalls.md:101 (две встречи: в прозе "подробнее — в [[linux/kernel/syscall-internals#стоимость-входа-и-выхода|механизме системных вызовов]]" и "KPTI"). Первый якорь: реальный заголовок `## Стоимость входа и выхода` — нужен `#Стоимость входа и выхода`. Второй — та же проблема со slug для KPTI. Класс: correct.
- cpu-modes-and-syscalls.md:213. `[буферного кеша PostgreSQL](../../databases/postgresql/durability/buffer-cache.md)` без якоря — пассивная ссылка на весь файл, хотя идея читателю нужна точечная («удерживать данные на быстром уровне иерархии»). Якорь на `#Какой слой `buffer-cache.md` определяет иерархию?` или аналогичный подраздел сделал бы ссылку точнее. Класс: correct (improvement, не баг).

**Формат ссылок findings:**

- cpu-modes-and-syscalls.md:213. `[буферного кеша PostgreSQL](../../databases/postgresql/durability/buffer-cache.md)` — markdown с `../../` префиксом без якоря, по §6.5 правильный формат.
- cpu-modes-and-syscalls.md:247. «См. также» — markdown `[Ruby I/O и GVL](../../ruby/internal/concurrency.md)` — правильный формат.
- cpu-modes-and-syscalls.md:52, 101. Wikilinks с якорями — формат выбран правильно, проблема только в slug-form самого якоря (см. выше).

**Внутренние якоря findings:**

- cpu-modes-and-syscalls.md:140. Термин «vDSO» определён выше в разделе `## vDSO: системный вызов без системного вызова` (строка 115). В разделе буферизации (строка 149 и далее) vDSO упоминается только вскользь — «vDSO решает проблему для нескольких конкретных функций» (строка 149) — без якоря на определение. По §6.2 при упоминании в другом разделе того же файла нужен `[[cpu-modes-and-syscalls#vDSO: системный вызов без системного вызова|vDSO]]`. Класс: correct.
- cpu-modes-and-syscalls.md:101, 224. Термин «syscall» и «системный вызов» упоминаются в 10+ разделах: «Цена системного вызова» (строка 99), «Анатомия read()» (строка 105), «Буферизация» (строка 147), «Итого: иерархия стоимости» (строка 224). Определение дано в `## Механизм системного вызова` (строка 50). При переходе на строку 101 или 224 нет якоря назад на определение. Для утилитарных повторов это избыточно, но один-два случая в далёких разделах были бы полезны. Класс: correct (минорно).

**Wip-queue кандидаты:**

- «IBRS» (cpu-modes-and-syscalls.md:101) — в тексте расшифровка есть («Indirect Branch Restricted Speculation»), но как концепция — защита от Spectre — она упоминается в репо только вскользь. Ожидаемый слой: `linux/kernel/` (связано с syscall-internals). Зачем: полная картина стоимости syscall требует понять, что добавляют митигации.
- «PCID» упоминается дважды (cpu-modes-and-syscalls.md ничего, но в virtual-memory.md:166–168 и scheduler.md:37). В `virtual-memory.md` определение есть inline; отдельная заметка не требуется. Не wip-кандидат.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- cpu-modes-and-syscalls.md:58 «Фаза 1: подготовка запроса». Читатель видит «номер syscall — в `rax`, аргументы — в `rdi`, `rsi`…» — это System V AMD64 ABI calling convention. Без связи с `../../computer/programmer-model/abi-and-data-layout.md` механика выглядит как произвольная магия, хотя это общее соглашение. Как исправить: одно предложение с ссылкой на ABI при первой встрече — «порядок регистров следует [System V AMD64 calling convention](../../computer/programmer-model/abi-and-data-layout.md), которое используется везде для функций и syscall».
- cpu-modes-and-syscalls.md:101 «сброс конвейера процессора (pipeline flush)» — описан как функциональный эффект, но без опоры на `../../computer/cpu/out-of-order-execution.md`, где speculative pipeline и его стоимость разобраны как механизм. Читатель здесь получает объяснение без ментальной опоры на модель процессора. Как исправить: при первой встрече `pipeline flush` — одна ссылка вниз.
- cpu-modes-and-syscalls.md:224–241 «Итого: иерархия стоимости». Таблица упоминает регистры CPU (0.3 нс), вызов функции (1–5 нс), syscall (~200 нс), SSD (~50 мкс), HDD (~5 мс). Это классическая latency numbers pyramid, которая уже введена в `../../computer/data-path/memory-hierarchy.md`. Сейчас cross-link отсутствует. Как исправить: одно предложение-ссылка на memory-hierarchy перед/после таблицы.

**Missing upward motivation:**

- cpu-modes-and-syscalls.md:146 «Буферизация: сокращение числа системных вызовов». Тема прикладная: stdio-буфер снижает число syscall на несколько порядков. Напрямую связана с `linux/programming/io-multiplexing.md` (epoll как следующий уровень оптимизации) и с `databases/postgresql/query-processing/memory-and-spill.md` (`work_mem`). Сейчас только forward-ссылка на PostgreSQL buffer-cache как аналогию — но через неё не построен мост к «почему epoll появится позже». Упоминание одной строкой не обязательно, но «См. также» в конце только Ruby — можно было бы шире.
- cpu-modes-and-syscalls.md:243. Финальный мостик: «Единица такого управления — [процесс]». Это хороший мост вперёд в серии, но upward-мотивация отсутствует: не упомянуто, что процесс станет единицей для PostgreSQL (процесс-на-соединение), Redis (один основной + фоновые), Ruby/Sidekiq. Это была бы сильная мотивация. Как исправить: в «См. также» добавить Postgres/Sidekiq-мост или одну фразу в финальный мостик.

### processes.md

#### Фокус A: reference integration

**Integrated links findings:**

- processes.md:19. «[Системные вызовы](cpu-modes-and-syscalls.md) дают программе доступ к ядру» — правильная интегрированная ссылка при первой встрече.
- processes.md:31. «Сегмент кода (text) содержит машинные инструкции» — концепция «сегмент» (text/data/bss/heap/stack) — это ABI-тема, `../../computer/programmer-model/abi-and-data-layout.md` её должен покрывать. Cross-link отсутствует, хотя концепция далее переиспользуется в `virtual-memory.md:270–322` — там есть полное адресное пространство. Класс: correct (нужна ссылка на abi-and-data-layout или forward на virtual-memory#адресное-пространство-процесса).
- processes.md:33. «Указатель инструкции (`rip` на x86-64)», «Указатель стека (`rsp`)», «Базовый указатель (`rbp`)» — перечисление регистров. Как в cpu-modes-and-syscalls.md, без ссылки на ISA/ABI эти имена висят в воздухе. Класс: correct (см. Focus B).
- processes.md:33. «TLB (Translation Lookaside Buffer — кеш трансляций адресов)» — inline-расшифровка есть, но cross-link на `virtual-memory.md#TLB: кеш трансляций` дал бы сильный forward-link. Здесь упоминание служебное (объяснение стоимости context switch), по §6.2 побочное — inline ок. Класс: correct (улучшение, не баг).
- processes.md:35. «Таблица [[linux/foundations/file-descriptors#трёхуровневая-таблица|файловых дескрипторов]]» — wikilink с якорем используется правильно (anchor нужен — см. ниже формат якоря).
- processes.md:39. «[[linux/programming/signals|сигнальные]] маски» — wikilink на sibling-подпапку, путь начинается с `linux/`, что полный vault-root — подходит для wikilink. Но target в `linux/programming/signals.md` — это `../programming/signals.md` из `linux/foundations/`. По §6.5 правило «wikilink, если target в подпапке текущего каталога»: `../programming/` — выход наверх. Формально должен быть markdown. Класс: correct (convert to markdown: `[сигнальные](../programming/signals.md)`).
- processes.md:89. «Полный механизм Copy-on-Write разберём в [[linux/foundations/virtual-memory#copy-on-write-fork-без-копирования|виртуальной памяти]]» — wikilink с якорем уместен, но якорь неправильный (см. ниже).
- processes.md:94. «загружает на их место содержимое указанного [[linux/infrastructure/elf-and-linking#exec() и загрузка ELF|исполняемого файла]]» — wikilink с якорем, якорь правильный (точный текст заголовка).
- processes.md:158, 162, 196, 197. «Сигнал» и его упоминания 4 раза — сначала inline с расшифровкой (строка 158 «Сигнал (например, SIGTERM)»), затем повторы на строках 162, 196, 197. Все с одинаковым линком `../programming/signals.md` (markdown). Формат правильный по §6.5 (markdown через `../`). §6.2 — «при каждом содержательном употреблении в новой строке» — соблюдено. Класс: correct.
- processes.md:259. `[паттерне демонизации](../infrastructure/terminals.md#паттерн-демонизации)` — markdown-ссылка с якорем. §6.3 явно требует wikilink для любой ссылки с якорем. Кроме того, якорь slug-form: реальный заголовок `### Паттерн демонизации` (строка 155 terminals.md), правильный якорь `#Паттерн демонизации`. Двойное нарушение. Класс: correct.
- processes.md:297. «IPC (Inter-Process Communication, межпроцессное взаимодействие — пайпы, разделяемая память, [сокеты](../programming/sockets.md))» — IPC как концепция расшифрована inline, но есть отдельная заметка `../programming/ipc.md`, которая прямо об этом. Cross-link на ipc.md отсутствует. Класс: correct.

**Якоря findings:**

- processes.md:35. Якорь `#трёхуровневая-таблица` — slug-form. Реальный заголовок: `## Трёхуровневая таблица` (строка 52 `file-descriptors.md`). Правильный якорь: `#Трёхуровневая таблица`. Класс: correct.
- processes.md:89. Якорь `#copy-on-write-fork-без-копирования` — slug-form. Реальный заголовок: `## Copy-on-write: fork() без копирования` (строка 204 `virtual-memory.md`). Правильный якорь: `#Copy-on-write: fork() без копирования` (с двоеточием и скобками). Класс: correct.
- processes.md:259. Якорь `#паттерн-демонизации` — slug-form. Реальный заголовок `### Паттерн демонизации` в `terminals.md:155`. Правильный якорь: `#Паттерн демонизации`. Плюс формат (см. выше). Класс: correct.

**Формат ссылок findings:**

- processes.md:35. `[[linux/foundations/file-descriptors#трёхуровневая-таблица|файловых дескрипторов]]` — wikilink потому что есть якорь (правильно по §6.3) и потому что target в foundations/ (та же папка) — ok. Но проверь правило §6.5: target в той же папке, значит по §6.5 для такого случая можно было бы markdown без якоря. С якорем всегда wikilink — именно это и выбрано. Класс: correct (формат правильный; якорь неправильный).
- processes.md:39, 297, 158, 162, 196, 197. Термин «сигнал/signals» — wikilink `[[linux/programming/signals|сигнальные]]` vs markdown `[сигнал](../programming/signals.md)` используются параллельно в одном файле. По §6.5 все эти target не попадают в подпапку текущего каталога (foundations/ не имеет подпапки `programming/` — это `../programming/`), значит везде должен быть markdown. Wikilink на строке 39 — нарушение §6.5. Класс: correct.
- processes.md:89. `[[linux/foundations/virtual-memory#copy-on-write-fork-без-копирования|виртуальной памяти]]` — target в той же папке foundations/. Формат wikilink выбран из-за якоря. Ок по §6.3.
- processes.md:94. `[[linux/infrastructure/elf-and-linking#exec() и загрузка ELF|исполняемого файла]]` — target в sibling-папке `../infrastructure/`. Wikilink с якорем правильно по §6.3.
- processes.md:259. Markdown c якорем — нарушение §6.3 (должен быть wikilink).

**Внутренние якоря findings:**

- processes.md:200, 220, 232, 281, 285, 291, 293. «Зомби» определён в разделе «Зомби: почему wait() необходим» (строка 200). В разделе «Сценарий целиком» (строка 281) зомби упоминаются трижды (строки 291, 293) без якоря назад. По §6.2 внутри одного файла при упоминании в других разделах нужен якорь на `[[processes#Зомби: почему wait() необходим|зомби]]`. Класс: correct (минорно — раздел «Сценарий» задуман как сквозной пример, ссылки назад избыточны; но одна точка входа в середину файла (кто-то пришёл по anchor'у от внешней заметки) — полезна).
- processes.md:297. «fork», «task_struct», «IPC» — все три повторяются в финальном абзаце после введения, в далёких частях файла без якорей. «task_struct» определён в разделе 37 как `### Дескриптор процесса: task_struct`, но в строке 297 без якоря. Нужен `[[processes#Дескриптор процесса: task_struct|task_struct]]`. Класс: correct.

**Wip-queue кандидаты:**

- Термин «subreaper» (processes.md:253) — есть inline-расшифровка («заместителем родителя»), но полная концепция покрытия в Docker/systemd отсутствует. Ожидаемый слой: `linux/containers/containers.md` (там есть одно упоминание «Контейнерные рантаймы используют subreaper»). Не wip-кандидат (достаточно inline).
- Термин «process group» и «setsid» (processes.md:259, 277) — связан с сессиями в `../infrastructure/terminals.md`. Уже есть ссылка на terminals.md. Не wip-кандидат.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- processes.md:33. «Указатель инструкции (`rip` на x86-64)… Указатель стека (`rsp`)… Базовый указатель (`rbp`)» — классические регистры CPU из программной модели. Без ссылки на `../../computer/programmer-model/isa.md` (где ISA разобрана) или abi (где calling convention описывает `rsp`/`rbp` как часть stack frame) читатель получает имена без ментальной модели. Как исправить: одна ссылка на `../../computer/programmer-model/abi-and-data-layout.md` («stack frame из ABI — именно то, что ядро сохраняет при context switch»).
- processes.md:33. «переключение контекста… перезагружает регистр CR3 (базовый адрес таблицы страниц), что сбрасывает TLB (Translation Lookaside Buffer — кеш трансляций адресов)». Концепция «кеш трансляций» — это TLB как кеш. Она опирается на общую модель кеширования из `../../computer/data-path/memory-hierarchy.md` и `cache-internals.md`. Сейчас TLB выглядит магическим аппаратным элементом. Как исправить: одна forward-ссылка «подробнее о TLB — в [виртуальной памяти](virtual-memory.md)» (там она раскрыта) — но и там нет явной опоры на cache-хиерархию.
- processes.md:87–89. Copy-on-Write объяснён на уровне эффекта (read-only бит → page fault → копирование 4 КБ). Упомянут page fault как «прерывание о нарушении доступа». Ментальная опора на «прерывания CPU как механизм» отсутствует (нет forward-ссылки на `../kernel/interrupts.md`). Не критично — механика полностью раскрывается в `virtual-memory.md`.

**Missing upward motivation:**

- processes.md:100–149. Паттерн fork+exec показан на примере ImageMagick convert. Это прикладной пример, но не мотивирует upward: «этот же паттерн — основа Unicorn/Puma workers (Ruby), PostgreSQL per-connection architecture, Redis BGSAVE». Без этого читатель не видит, что fork+exec — не просто исторический паттерн для shell, а актуальный production-инструмент. Как исправить: в разделе «Сценарий целиком» (строка 281) или в финальном абзаце (297) одна фраза: «Тот же паттерн fork+CoW используется для [BGSAVE Redis](../../databases/redis/persistence/rdb.md) — дочерний процесс сериализует snapshot, родитель обрабатывает команды».
- processes.md:285–295. Сценарий с convert хорош, но финальный мостик (строка 297) не упоминает, что этот паттерн масштабируется вверх. «См. также» отсутствует в этом файле (в отличие от других заметок серии). Как исправить: добавить секцию «См. также» с ссылками на Redis BGSAVE, PostgreSQL master/backend-процессы, Unicorn/Puma preforking — типичные upward-потребители fork+CoW.

### threads.md

#### Фокус A: reference integration

**Integrated links findings:**

- threads.md:14. Предпосылки: `[процессы](processes.md) (fork, exec, адресное пространство, task_struct)` — правильно перечислены концепции.
- threads.md:18. «Вызов fork создаёт независимый процесс» — первое упоминание, без cross-link хотя fork — ключевая концепция. Но fork — уже в Предпосылках, и в предыдущей заметке. По §6.2 побочные упоминания без cross-link ок, если термин в Предпосылках. Класс: correct (минорно, fork можно залинковать при первой встрече).
- threads.md:26. «copy-on-write откладывает физическое копирование страниц» — интегрированная ссылка `[[linux/foundations/virtual-memory#copy-on-write-fork-без-копирования|copy-on-write]]` есть. Wikilink из-за якоря (правильно). Якорь неправильный (slug-form; см. ниже).
- threads.md:30. «трансляции адресов предыдущего процесса в [[linux/foundations/virtual-memory#tlb-кеш-трансляций|TLB]]» — интегрированная ссылка уместна (TLB не в Предпосылках этого файла). Якорь неправильный.
- threads.md:42. «таблица [[linux/foundations/file-descriptors#файловые-дескрипторы|файловых дескрипторов]]» — wikilink с якорем. Якорь `#файловые-дескрипторы` — slug-form, но реального заголовка `## Файловые дескрипторы` в `file-descriptors.md` нет (это title-H1, `# Файловые дескрипторы`). Это ссылка на title, что и в obsidian обычно работает (anchor совпадает с H1), но лучше ссылаться на более конкретный подраздел вроде `## Всё — файл` или `## Трёхуровневая таблица`. Класс: correct (якорь неправильный или лишний).
- threads.md:89. «структура-дескриптор [[linux/foundations/processes#дескриптор-процесса-task_struct|task_struct]]» — wikilink с якорем. Якорь `#дескриптор-процесса-task_struct` — slug-form. Реальный: `### Дескриптор процесса: task_struct`. Правильный якорь: `#Дескриптор процесса: task_struct`. Класс: correct.
- threads.md:109. «[Планировщик](scheduler.md) ядра (CFS — Completely Fair Scheduler)» — forward-ссылка в серии. Но важно: в ядре 6.6+ не CFS, а EEVDF. Другой файл (`scheduler.md:182`) на это указывает. Локально терминология устаревшая, но контекст позволяет (упоминание «ядре CFS» как исторически дефолтном). Класс: minor (не integration-проблема).
- threads.md:115. «через POSIX (Portable Operating System Interface) Threads (pthreads) — стандартизированный интерфейс, реализованный в glibc как NPTL» — pthread как первое упоминание с расшифровкой. Cross-link отсутствует, но pthreads — это сам предмет данной заметки, не другой файл. Корректно.
- threads.md:133. «`pthread_create` выделяет стек для нового потока (через [mmap](../programming/memory-mapping.md))» — интегрированная ссылка на `memory-mapping.md`, markdown через `../` — правильный формат §6.5. Класс: correct.
- threads.md:163. «[Атомарные операции](../../computer/atomic-instructions.md)» — первое упоминание с integrated link. Правильно.
- threads.md:167. TLS — «thread-local storage, TLS; не путать с Transport Layer Security» — хорошая разборка омонимии. Нет cross-link, но TLS — определяется прямо здесь. Корректно.
- threads.md:220. «См. также»: ссылка на `[Ruby GVL](../../ruby/internal/concurrency.md)` — корректная upward-связь.

**Якоря findings:**

- threads.md:26. `#copy-on-write-fork-без-копирования` — slug-form. Правильно: `#Copy-on-write: fork() без копирования`. Класс: correct.
- threads.md:30. `#tlb-кеш-трансляций` — slug-form. Реальный заголовок: `## TLB: кеш трансляций`. Правильно: `#TLB: кеш трансляций`. Класс: correct.
- threads.md:42. `#файловые-дескрипторы` — slug-form. Реальный — title файла `# Файловые дескрипторы` (H1). На H1 якорей обычно не ставят (сам landing на файл = landing на H1). Если нужна конкретика — якорь на `## Всё — файл` или `## Трёхуровневая таблица`. Класс: correct (либо убрать якорь, либо заменить на подраздел).
- threads.md:89. `#дескриптор-процесса-task_struct` — slug-form. Правильно: `#Дескриптор процесса: task_struct`. Класс: correct.
- threads.md:28. `[shared memory](../programming/memory-mapping.md)` — markdown link без якоря на всю заметку memory-mapping. Но заметка покрывает несколько концепций (anonymous mapping, file mapping, shared). Якорь на конкретный раздел был бы точнее. Класс: correct (improvement).

**Формат ссылок findings:**

- threads.md:26, 30, 42, 89. Все wikilinks с якорями — правильный формат (§6.3). Якоря slug-form — см. выше.
- threads.md:14 (Предпосылки), 133 (mmap), 158 (сокетах), 163 (атомарные операции), 183 (kernel thread), 220 (Ruby GVL), 225 (pthreads man). Все markdown `../`-ссылки — правильный формат §6.5.
- threads.md:28 «семафор (IPC)», «shared memory» — ссылки на mmap-заметку. Markdown правильно.

**Внутренние якоря findings:**

- threads.md:109 «Планировщик ядра (CFS)… не различает процессы и потоки» — ссылка на `scheduler.md`. Концепция «поток» как единица планирования определяется в разделе 36 («Поток: параллелизм без изоляции»). При упоминании в далёких разделах (109, 183) якорь на `[[threads#Поток: параллелизм без изоляции|поток]]` не обязателен, но визуально полезен. Класс: correct (минорно).
- threads.md:115, 133, 135. «pthread_create» упоминается многократно. Определяется в разделе «Библиотека pthreads» (строка 113). Повторы в том же разделе — без якоря ок.
- threads.md:176. «TLS» — определяется в разделе «Локальное хранилище потока» (строка 167) и упоминается дальше в том же разделе. Ок.

**Wip-queue кандидаты:**

- «futex» (в threads.md: упоминание `futex_wait()` в scheduler.md, а в threads.md не упоминается) — есть в `../concurrency/synchronization.md`. Не wip.
- «NPTL» (threads.md:115) — есть inline-расшифровка. Не wip.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- threads.md:30. «переключение контекста между процессами стоит 3–10 мкс, потому что ядро перезагружает регистр CR3… трансляции адресов предыдущего процесса в TLB становятся неактуальными». TLB как кеш — это ментальная модель. Связь с `../../computer/data-path/memory-hierarchy.md` (TLB как ещё один уровень кеша) и `cache-internals.md` (полностью ассоциативный кеш) не сделана, а именно эта параллель сильно помогает запомнить. Как исправить: одна фраза-ссылка на cache-internals («TLB — тот же принцип, что L1/L2 cache, только для трансляций»).
- threads.md:69. «ядро не перезагружает CR3 и трансляции в TLB остаются валидными — оба потока используют одни и те же таблицы страниц, значит закешированные пары «виртуальный адрес → физический» подходят обоим» — хорошее объяснение, но без упоминания, что это общий принцип — reusing cache state между родственными processes/threads. Можно связать с `../../computer/data-path/cache-internals.md`, но не обязательно — объяснение полное.
- threads.md:141–157. Race condition на `counter++` — классический пример. Три машинные инструкции (`mov`, `inc`, `mov`) — опора на ISA из `../../computer/programmer-model/isa.md`. Сейчас нет ссылки; следующий содержательный узел (атомарные операции) линкуется правильно, но сам пример с тремя инструкциями мог бы опираться на ISA-notion. Как исправить: при первом упоминании «три операции: загрузка… инкремент регистра… запись» — одна ссылка на ISA.

**Missing upward motivation:**

- threads.md:27 «при 10 000 процессов, даже если каждый потребляет всего 10 МБ уникальной памяти, это 100 ГБ» — пример apache prefork MPM. Хорошо. Но далее, после объяснения threads, не сказано, что Ruby (MRI Puma), Node.js — это именно thread-based серверы или hybrid (Puma + cluster). «См. также» содержит Ruby GVL — но не упомянуто, что puma thread pool = этот самый паттерн threads-per-request. Как исправить: в разделе «Общая память: преимущество и проблема» или в «См. также» добавить «Puma workers — форки, Puma threads — POSIX потоки», ссылаясь на `../../rails/sidekiq/` или `../../ruby/internal/concurrency.md#puma`.
- threads.md:185–208. Модели N:1, 1:1, M:N описаны абстрактно. Go goroutines — правильный пример M:N. Но Java Virtual Threads, Node.js event loop, Ruby Fibers — это близкие темы, не связанные. Ruby Fiber упомянут только в «См. также», но связь N:1 vs M:N через Fibers просится. Как исправить: при объяснении N:1 связь с «Ruby Fiber — пример N:1 из пользовательского пространства, описан в [Ruby конкурентности](../../ruby/internal/concurrency.md)».

### file-descriptors.md

#### Фокус A: reference integration

**Integrated links findings:**

- file-descriptors.md:15. Предпосылки: потоки + процессы + cpu-modes-and-syscalls. Все с inline-расшифровкой нужных концепций.
- file-descriptors.md:23, 222. «сетевой [[linux/programming/sockets|сокет]]» — wikilink. По §6.5 это полный vault-root путь, но target в `../programming/sockets.md` относительно текущего файла — выход наверх через `../`. §6.5 требует markdown для любой ссылки с `../` префиксом. Текущий wikilink нарушает §6.5 (правило Quartz-резолвер интерпретирует без `./`/`../` как от vault-root). Класс: correct (convert to markdown `[сокет](../programming/sockets.md)`).
- file-descriptors.md:36, 37. «socket()» упомянут голым термином — уместная краткость (это системный вызов, не отдельная концепция).
- file-descriptors.md:95. «подробнее о структуре inode на диске — в [[linux/foundations/filesystems#inode-метаданные-файла|файловых системах]]» — wikilink с якорем. Якорь slug-form: `#inode-метаданные-файла`. Реальный: `## Inode: метаданные файла`. Правильно: `#Inode: метаданные файла`. Класс: correct.
- file-descriptors.md:235. «`/proc` — виртуальная файловая система… устройство `/proc` описано в разделе [[linux/kernel/devices-and-drivers#наблюдаемость-proc-и-sys|Наблюдаемость: /proc и /sys]]» — wikilink с якорем. Якорь `#наблюдаемость-proc-и-sys` — slug-form. Реальный: `## Наблюдаемость: /proc и /sys`. Правильно: `#Наблюдаемость: /proc и /sys`. Класс: correct.
- file-descriptors.md:257. «когда процесс завершается (через `exit()`, получение [сигнала](../programming/signals.md) или возврат из `main()`)» — markdown через `../` — формат правильный. Класс: correct.
- file-descriptors.md:325. «Как это возможно — вопрос [виртуальной памяти](virtual-memory.md)» — forward-ссылка в серии, корректно.

**Якоря findings:**

- file-descriptors.md:95. `#inode-метаданные-файла` — slug-form. Правильно: `#Inode: метаданные файла`. Класс: correct.
- file-descriptors.md:235. `#наблюдаемость-proc-и-sys` — slug-form. Правильно: `#Наблюдаемость: /proc и /sys`. Класс: correct.

**Формат ссылок findings:**

- file-descriptors.md:23, 222. Wikilinks `[[linux/programming/sockets|...]]` — target через `../` относительно текущего файла, по §6.5 должен быть markdown. Класс: correct (convert).

**Внутренние якоря findings:**

- file-descriptors.md:99, 104, 115, 124, 131, 207. «fork()» упоминается многократно в разных разделах. Определён в Предпосылках (processes.md). В тексте линкован на `processes.md` только в строке 324 (финальный абзац) — а все использования на строках 99, 104, 184 без ссылки. По §6.2 — каждое содержательное использование на новой строке должно быть линковано. Класс: correct (не все встречи залинкованы; но fork утилитарный — есть в Предпосылках, так что одна ссылка в ключевом месте ок).
- file-descriptors.md:90 «Open file description». Определён в этом разделе, используется в разделах 99 (fork и разделённое смещение), 134 (dup), 222 (close). Внутренние якоря на `[[file-descriptors#Трёхуровневая таблица|open file description]]` при повторных встречах — по §6.2 полезны. Класс: correct (минорно).

**Wip-queue кандидаты:**

- Нет явных кандидатов. Концепции fd, pipe, inode, dup2 — все раскрыты.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- file-descriptors.md:52–95. Трёхуровневая таблица (per-process fd → open file description → inode) — пример trade-off между индексами и указателями на уровне ядра. Опора на `../../algorithms-and-data-structures/linear/array.md` (fd-таблица — массив указателей) была бы естественной, но не обязательной.
- file-descriptors.md:218. «Буфер pipe ограничен: на Linux по умолчанию это 65536 байт (16 страниц по 4 КБ)» — упоминаются страницы, но без ссылки на `virtual-memory.md` (forward-ссылка). В контексте файла это побочный факт, не мешает читателю.

**Missing upward motivation:**

- file-descriptors.md:323. Финальный абзац описывает fd как «точку входа процесса во внешний мир». Это прямая подводка к: «именно эту абстракцию Redis использует через epoll для мультиплексирования, Nginx — для worker'ов». Upward-мотивация отсутствует. Как исправить: в финальном абзаце или «См. также» (отсутствует в файле) упомянуть, что «accept loop веб-сервера опирается на лимит fd» или связать с epoll в `../programming/io-multiplexing.md`.
- file-descriptors.md:261. «Сервер логирования: fork() и pipe вместе» — приложение, близкое к supervisor-паттерну. Upward-связь с Redis (master + workers) или PostgreSQL (postmaster + backends) отсутствует. Как исправить: одна фраза «этот же паттерн master-процесс + воркеры с pipe — основа Nginx, PostgreSQL, Unicorn».

### virtual-memory.md

#### Фокус A: reference integration

**Integrated links findings:**

- virtual-memory.md:15 (Предпосылки). `[иерархия памяти](../../computer/data-path/memory-hierarchy.md) (cache line)`, `[когерентность кешей](../../computer/data-path/cache-coherency.md) (MESI)` — корректные downward-ссылки с inline-расшифровкой.
- virtual-memory.md:19. «[процесс](processes.md)» первое упоминание — правильно. Потом ещё 4 раза в том же абзаце — §6.2 «максимум одна ссылка на концепцию в одной строке». Ок.
- virtual-memory.md:25. «В [что такое ОС](what-is-os.md) мы уже видели эту ситуацию» — self-reference через «мы», что противоречит styleguide §0.2 «Самореферентные обороты». Этот пункт не integration-линзы, но помечу. Класс: skip (styleguide-тема, не integration).
- virtual-memory.md:90. «Страницы ядра имеют U/S=0, и процесс из ring 3 не может их прочитать» — wikilink `[[linux/foundations/cpu-modes-and-syscalls#кольца-привилегий|ring 3]]`. Якорь slug-form. Реальный заголовок `## Кольца привилегий`. Правильно: `#Кольца привилегий`. Класс: correct.
- virtual-memory.md:141. Аналогично `#кольца-привилегий` — slug-form, правильно `#Кольца привилегий`. Класс: correct.
- virtual-memory.md:174. «Аналогия с [[computer/data-path/cache-coherency#протокол-mesi-четыре-состояния-кеш-линии|когерентностью кешей]]» — wikilink с якорем. Якорь slug-form. Реальный заголовок `## Протокол MESI: четыре состояния кеш-линии` (строка 28 `cache-coherency.md`). Правильно: `#Протокол MESI: четыре состояния кеш-линии`. Класс: correct.
- virtual-memory.md:188. «red-black дерево — [бинарное дерево поиска](../../algorithms-and-data-structures/non-linear/binary-search-tree.md), самобалансирующийся вариант» — intgrated link с inline-расшифровкой. Корректно.
- virtual-memory.md:196. «[ELF-заголовок](../infrastructure/elf-and-linking.md)» — markdown на sibling, без якоря. Полезнее якорь на `#Что внутри исполняемого файла`. Класс: correct (improvement).
- virtual-memory.md:266. «вступает [[linux/programming/memory-management#OOM killer: последняя линия защиты|OOM killer]]» — wikilink с якорем. Якорь правильный (`#OOM killer: последняя линия защиты` — точный текст заголовка в `memory-management.md:156`). Класс: correct.
- virtual-memory.md:314. «[[linux/infrastructure/elf-and-linking#Динамический линкер: ld-linux|динамический линкер]]» — wikilink с якорем. Реальный заголовок `## Динамический линкер: ld-linux` (строка 104 elf-and-linking.md). Якорь правильный. Класс: correct.
- virtual-memory.md:348. «См. также: Ruby GC» — upward-ссылка, корректно.

**Якоря findings:**

- virtual-memory.md:90, 141. `#кольца-привилегий` — slug-form. Правильно `#Кольца привилегий`. Класс: correct.
- virtual-memory.md:174. `#протокол-mesi-четыре-состояния-кеш-линии` — slug-form. Реальный заголовок `## Протокол MESI: четыре состояния кеш-линии` (строка 28 `cache-coherency.md`). Правильно: `#Протокол MESI: четыре состояния кеш-линии`. Класс: correct.

**Формат ссылок findings:**

- virtual-memory.md:90, 141, 174. Wikilinks с якорями — формат правильный (§6.3). Якоря — slug-form.
- virtual-memory.md:17 (`filesystems.md`), 196 (`elf-and-linking.md`). Forward-ссылки markdown без якорей — формат правильный (§6.5).
- virtual-memory.md:266, 314. Wikilinks с правильными якорями — отличный пример того, как должно быть.
- virtual-memory.md:348. Markdown `[Ruby GC](../../ruby/internal/gc.md)` — правильный формат.

**Внутренние якоря findings:**

- virtual-memory.md:82, 97, 127, 133, 145, 176. Много секций с определениями: «Страницы», «Page table», «MMU и регистр CR3», «TLB», «Page fault». Термины используются в далёких разделах — «Сценарий целиком» (строка 324), «Адресное пространство процесса» (270). Внутренние якоря на определения избирательно полезны, но не критичны — дуга линейная, читатель идёт сверху вниз. Класс: correct (минорно, один-два внутренних якоря в финальном сценарии были бы уместны).
- virtual-memory.md:324–336. «Сценарий целиком: malloc, touch, fork, write» — проходится по VMA, PTE, present-bit, page fault, CoW, Demand paging, Overcommit — все концепции, определённые выше в файле. Нет якорей. По §6.2 конец раздела: «если определение и упоминание стоят рядом, ссылка избыточна». Здесь упоминания далеко от определений (200+ строк), якорь был бы уместен. Класс: correct.

**Wip-queue кандидаты:**

- «Demand paging» (virtual-memory.md:194) — определён тут, используется здесь же. Нет отдельной заметки (не надо).
- Red-black tree (virtual-memory.md:188) — как отдельной заметки нет в `algorithms-and-data-structures/`. Ссылка на binary-search-tree как parent-concept — компромисс. Кандидат в wip-queue для будущего: `algorithms-and-data-structures/non-linear/red-black-tree.md`. Использование в `virtual-memory.md` (VMA lookup) и `scheduler.md` (CFS runqueue) — два независимых потребителя, по §9 structure-guide это уже достаточно для отдельной заметки. Ожидаемый слой: `algorithms-and-data-structures/non-linear/`. Зачем: две заметки ссылаются на «red-black дерево» как на известную структуру, а её понятного описания в репо нет — только упоминания в `binary-search-tree.md`.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- virtual-memory.md:145 «TLB: кеш трансляций». TLB объясняется хорошо (полностью ассоциативный кеш, L1/L2 DTLB, hit rate). Но связь с общей моделью кеширования из `../../computer/data-path/cache-internals.md` (tag/index/offset, ассоциативность, политики вытеснения) не сделана явно. Читатель получает TLB как изолированный факт. Как исправить: одна фраза «TLB устроен как обычный аппаратный кеш (см. [устройство кеша](../../computer/data-path/cache-internals.md)) — только индекс/тег по номеру страницы, не по адресу байта».
- virtual-memory.md:130. «Четыре уровня — 240–400 нс только на адресный перевод» — эта стоимость — следствие того, что таблицы лежат в RAM (~60–100 нс на чтение). Опора на `../../computer/data-path/memory-hierarchy.md` уже есть в Предпосылках, но cross-link при этой конкретной оценке был бы сильным. Класс: минорно.
- virtual-memory.md:162 «Случайный доступ к памяти — другое дело: каждое обращение может затронуть другую ветвь дерева, кеш не помогает» — это классическая spatial locality из memory-hierarchy. Один cross-link назад при этой фразе усилил бы ментальную модель. Класс: минорно.

**Missing upward motivation:**

- virtual-memory.md:235. «Redis выполняет фоновое сохранение (BGSAVE) через fork()… пиковое потребление: 10 ГБ + 3 ГБ = 13 ГБ… OOM kill». Отличный пример upward-мотивации. Ссылка на `redis/persistence/rdb.md` была бы полезна, но inline-описание достаточное. Сейчас нет cross-link. Класс: correct (improvement, не критично).
- virtual-memory.md:264. «JVM запрашивает большой непрерывный блок для кучи (heap) через `mmap()`» — пример overcommit для Java. Аналогичный пример для Ruby (preload+fork, Puma cluster mode) — в «См. также» есть ссылка на `ruby/internal/gc.md`, но без привязки к bitmap marking как решению CoW. Достаточно.
- virtual-memory.md:268. «PostgreSQL, например, рекомендует `overcommit_memory=2`» — отличная upward-деталь. Cross-link на `postgresql.md` или `databases/postgresql/durability/buffer-cache.md` был бы корректным. Класс: correct (improvement).
- virtual-memory.md:315. «Несколько процессов, использующих одну библиотеку, разделяют одни и те же физические фреймы кода — это один из главных способов экономии RAM» — прямая подводка к PostgreSQL per-connection (shared postgres binary) и Unicorn/Puma preforking (shared Ruby code). Сейчас без upward-ссылки. Класс: correct (improvement).

### filesystems.md

#### Фокус A: reference integration

**Integrated links findings:**

- filesystems.md:15 (Предпосылки). «[виртуальная память](virtual-memory.md) (страницы, page fault)», «[хранилище](../../computer/data-path/storage.md) (HDD seek/rotation, SSD latency)» — все корректны.
- filesystems.md:25. «С точки зрения ядра, [[computer/data-path/storage#hdd-механика-вращающихся-пластин|диск]]» — wikilink с якорем. Якорь `#hdd-механика-вращающихся-пластин` — slug-form. Нужно сверить заголовок в `storage.md`. Предположительно `## HDD: механика вращающихся пластин`. Правильно: `#HDD: механика вращающихся пластин`. Класс: correct.
- filesystems.md:119. «ext4 строит [B-дерево](../../algorithms-and-data-structures/non-linear/b-tree.md) (сбалансированное дерево поиска) экстентов» — integrated link с inline-расшифровкой. Корректно.
- filesystems.md:125, 167, 171, 224. «процесс» — несколько упоминаний. Линк на `processes.md` есть только в строке 125 и 321, между ними много голых упоминаний. §6.2 «на каждой новой строке где термин работает содержательно, — снова ссылка» — частично нарушено.
- filesystems.md:171. «[файловых дескрипторов](file-descriptors.md)» — intgrated link. Ок.
- filesystems.md:224. «Это аналог [minor page fault](virtual-memory.md) в виртуальной памяти» — markdown-ссылка без якоря на конкретный раздел «Page fault: когда трансляция не удалась». Должен быть wikilink с якорем (по §6.3 любая ссылка с якорем — wikilink; но здесь только текст «minor page fault», не anchor). На самом деле это ссылка на файл без якоря — markdown корректно. Однако якорь на раздел `#Page fault: когда трансляция не удалась` дал бы точечный landing. Класс: correct (improvement).
- filesystems.md:242. «PostgreSQL поддерживает [shared_buffers](../../databases/postgresql/durability/buffer-cache.md)» — markdown на внешнюю заметку, без якоря. Корректно.
- filesystems.md:266. «Идея та же, что и [WAL (Write-Ahead Log) в PostgreSQL](../../databases/postgresql/durability/wal.md)» — markdown на внешнюю заметку. Корректно.
- filesystems.md:303. «PostgreSQL обеспечивает Durability в [ACID](../../databases/acid.md)» — markdown на общую теорию. Корректно.

**Якоря findings:**

- filesystems.md:25. `#hdd-механика-вращающихся-пластин` — slug-form. Правильный формат по §6.3 требует проверки реального заголовка. Класс: correct.
- filesystems.md:224, 242, 266, 303. Нет якорей, хотя точечные якоря дали бы больше пользы. Класс: correct (improvement).

**Формат ссылок findings:**

- Все markdown через `../../` — правильный формат.
- filesystems.md:25. Wikilink с якорем — правильный формат по §6.3.

**Внутренние якоря findings:**

- filesystems.md:222, 231 «page cache как буфер». Определение в разделе `## Page cache: файловые данные в оперативной памяти` (218). Используется в разделах 242 (O_DIRECT), 246 (Crash consistency), 295 (fsync), 317 (Итоги). Без якоря `[[filesystems#Page cache: файловые данные в оперативной памяти|page cache]]`. В финальном разделе (317–321) page cache упоминается дважды. Класс: correct.
- filesystems.md:293, 295 «ordered» — определён в разделе `### Режимы журналирования в ext4` (283), но отдельного заголовка у режима нет. Не внутренний якорь.
- filesystems.md:320 «writeback daemon». Определён в 230–235 («Запись: page cache как буфер»). В финале без якоря. Но концепция писателя хорошо объяснена именем. Класс: минорно.

**Wip-queue кандидаты:**

- «inotify» — не упоминается, но типичная тема. Не обязательно.
- «Delayed allocation» (311) — inline-расшифровка, достаточно.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- filesystems.md:220. «случайное чтение 4 КБ с HDD стоит ~10 мс, с SSD — ~100 мкс. Оперативная память отдаёт те же 4 КБ за ~100 нс» — классическая latency pyramid. Опора на `../../computer/data-path/memory-hierarchy.md` уже есть в Предпосылках через `storage.md`. Корректно.
- filesystems.md:301. «На HDD — 5-15 мс… На NVMe SSD с PLP — от 10 мкс» — снова latency numbers. Хорошо.

**Missing upward motivation:**

- filesystems.md:242–244. «PostgreSQL… shared_buffers… O_DIRECT» — отличная upward-связь.
- filesystems.md:303–305. «PostgreSQL… fsync WAL-файла… group commit» — отличная upward-связь.
- filesystems.md:321. Финальный мостик: «Вся эта инфраструктура работает, пока ядро решает…» — forward в серии. Нет upward-ссылок на реальные БД-системы: Cassandra, MongoDB, S3 — все опираются на POSIX fs или обходят её через O_DIRECT. Но это было бы выходом за рамки заметки. Корректно.

### scheduler.md

#### Фокус A: reference integration

**Integrated links findings:**

- scheduler.md:15 (Предпосылки). Три ссылки с inline-расшифровкой. Корректно.
- scheduler.md:36. «Планировщик передаёт процессор от одного потока к другому через [переключение контекста](processes.md) (context switch)» — первая встреча. Линк на processes.md. Якорь на `#Из чего состоит процесса` или `#Как появляются новые процессы: fork()` был бы точнее — но концепция context switch не имеет отдельного раздела в processes.md (упоминается в строке 33 без заголовка). Класс: correct (без якоря ок).
- scheduler.md:37. «На машине с [[linux/kernel/syscall-internals#kpti-двойные-таблицы-страниц|KPTI]]» — wikilink с якорем. Якорь slug-form. Правильно: `#KPTI: двойные таблицы страниц`. Класс: correct.
- scheduler.md:41. «Ядро помещает значения регистров общего назначения (rax, rbx, rcx, ..., r15), указатель инструкций (rip), указатель стека (rsp), регистр флагов (rflags) и регистры расширенного набора — FPU (Floating Point Unit), SSE, AVX — в структуру [[linux/foundations/processes#дескриптор-процесса-task_struct|task_struct]]» — wikilink с якорем. Якорь slug-form. Правильно: `#Дескриптор процесса: task_struct`. Класс: correct.
- scheduler.md:45. «Если оба потока работают в одном адресном пространстве (флаг [[linux/foundations/threads#linux-потоков-не-существует|`CLONE_VM`]] при создании)» — wikilink с якорем. Якорь slug-form: `#linux-потоков-не-существует`. Реальный заголовок `## Linux: потоков не существует`. Правильно: `#Linux: потоков не существует`. Класс: correct.
- scheduler.md:45 (два вхождения). «[[linux/foundations/virtual-memory#mmu-и-регистр-cr3|CR3]]», «[[linux/foundations/virtual-memory#tlb-кеш-трансляций|TLB]]» — оба slug-form. Правильно: `#MMU и регистр CR3` и `#TLB: кеш трансляций`. Класс: correct.
- scheduler.md:75. «Поток вызывает блокирующий системный вызов: `read()` на пустом [[linux/programming/sockets|сокете]]» — wikilink на sockets. Target — `../programming/sockets.md`, выход через `../`, по §6.5 должен быть markdown. Класс: correct (format).
- scheduler.md:91. «весь пласт инструментов для защиты от непредсказуемых прерываний в произвольный момент» — ссылка `[[linux/concurrency/synchronization#гонка-и-гонка-данных|синхронизации]]`. Якорь slug-form. Реальный `## Гонка и гонка данных`. Правильно: `#Гонка и гонка данных`. Класс: correct.
- scheduler.md:119. «хранит все готовые к исполнению (runnable) потоки в красно-чёрном дереве ([BST](../../algorithms-and-data-structures/non-linear/binary-search-tree.md), самобалансирующийся вариант)» — markdown с текстом «BST» и inline-пояснением. На самом деле CFS использует red-black tree specifically — и это отдельный класс алгоритмов, которого в репо нет. Ссылка на родительскую BST — компромисс, но приводит читателя к алгоритму без red-black specifics. Класс: correct (нужна специализированная заметка — см. wip).
- scheduler.md:268. «См. также: Ruby GVL timer thread» — upward, корректно.

**Якоря findings:**

- scheduler.md:37, 41, 45 (×3), 91. Все якоря — slug-form. Все — correct (нужна правка на точный текст заголовка).

**Формат ссылок findings:**

- scheduler.md:75. `[[linux/programming/sockets|сокете]]` — wikilink на target через `../`. По §6.5 должен быть markdown. Класс: correct (convert).
- Остальные wikilinks с якорями — формат правильный.
- scheduler.md:119 (BST). Markdown через `../../` без якоря — правильный формат. Якорь на конкретный раздел `#Самобалансирующиеся деревья` (или аналог) был бы точнее. Класс: correct (improvement).

**Внутренние якоря findings:**

- scheduler.md:105, 182. «CFS» определён в разделе `## CFS: Completely Fair Scheduler`, «EEVDF» — в `## EEVDF: наследник CFS`. Оба упоминаются в других разделах (46, 209, 212, 265). Внутренние якоря на эти заголовки при далёких упоминаниях — по §6.2 уместны. Класс: correct (минорно).
- scheduler.md:115–161 «vruntime» определён в `### vruntime: виртуальное время выполнения` (109). Упоминается в 119, 134, 138, 150–154, 158. Все в пределах раздела «CFS» — якоря не нужны.
- scheduler.md:112, 116 «vruntime» — используется в разделе EEVDF (184–190) без якоря назад на определение. Нужен `[[scheduler#vruntime: виртуальное время выполнения|vruntime]]`. Класс: correct.

**Wip-queue кандидаты:**

- **Red-black tree** (scheduler.md:119, virtual-memory.md:188) — два независимых потребителя, нет отдельной заметки. Ожидаемый слой: `algorithms-and-data-structures/non-linear/red-black-tree.md`. Зачем: CFS/EEVDF и VMA lookup используют это дерево как базовую структуру; читатель не видит, почему именно red-black (self-balancing, O(log n) с низкой константой, amortized rebalancing). Главный wip-кандидат.
- **PIT (programmable interrupt timer)** (scheduler.md:81) — inline-расшифровка, но механика таймерных прерываний — в `linux/kernel/interrupts.md`. Cross-link при первой встрече помог бы. Не wip.
- **NUMA** (scheduler.md:237) — inline-расшифровка. Есть заметка `linux/programming/memory-management.md#NUMA: неоднородная память`. Cross-link отсутствует. Класс: correct (должен быть anchor).

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- scheduler.md:41. «регистры расширенного набора — FPU (Floating Point Unit), SSE (Streaming SIMD Extensions), AVX (Advanced Vector Extensions) — в структуру task_struct. Регистры FPU/SSE/AVX — это расширенные регистровые файлы процессора для вещественной арифметики и SIMD-вычислений; каждый регистр AVX-512 занимает 512 бит…» — это ISA-тема. Без опоры на `../../computer/programmer-model/simd.md` (SIMD и векторные расширения) или `isa.md` (ISA) читатель получает SIMD как термин без ментальной модели. Как исправить: одна интегрированная ссылка на `../../computer/programmer-model/simd.md` при первом упоминании SIMD.
- scheduler.md:119–134. Красно-чёрное дерево, O(1) выбор минимума, O(log n) вставка/удаление — это алгоритмы. Опора на `../../algorithms-and-data-structures/non-linear/binary-search-tree.md` есть (inline-ссылка), но read-black specifically как red-black tree (с ротациями, цветами узлов) не раскрыт. Как исправить: либо создать `red-black-tree.md` (wip-кандидат), либо оставить ссылку на BST + одну фразу «почему red-black, а не AVL: меньше ротаций при вставке, что критично при 100 000 событий планировщика в секунду».
- scheduler.md:37, 228. Context switch и NUMA-задержки (~80 нс vs ~140 нс) — обе опираются на memory-hierarchy. Ссылки отсутствуют. Как исправить: cross-link на `../../computer/data-path/memory-hierarchy.md` при обсуждении стоимости.

**Missing upward motivation:**

- scheduler.md:155. «CFS не назначает интерактивным потокам специальный приоритет — механизм vruntime делает это автоматически». Это важно для Ruby/GIL: timer thread (`scheduler.md:268` в «См. также») гарантирует, что vruntime-based preemption вытесняет Ruby поток раз в ~100 мс. Но связь «preemption → GIL latency bumps в Ruby» не сделана. Как исправить: в «См. также» дополнить — «preemption каждые 4 мс — причина, почему Ruby/Puma latency имеет jitter порядка миллисекунд даже на однопоточной нагрузке».
- scheduler.md:225. «балансировщик учитывает топологию: миграция между ядрами одного физического процессора дешевле» — и потом NUMA-задача. Это прямое объяснение, почему PostgreSQL `numactl --interleave=all` (в задаче) работает. Хороший пример. Но upward-ссылка на PostgreSQL в `См. также» отсутствует. Класс: correct (improvement).

### permissions-and-capabilities.md

#### Фокус A: reference integration

**Integrated links findings:**

- permissions-and-capabilities.md:15 (Предпосылки). Три ссылки с inline-расшифровкой, все корректны.
- permissions-and-capabilities.md:19, 21 (несколько вхождений). «[Планировщик](scheduler.md)», «[процессы](processes.md)», «[файловые дескрипторы](file-descriptors.md)» — по одному линку на концепцию в каждом абзаце. Всё корректно по §6.2.
- permissions-and-capabilities.md:25. «[[linux/foundations/processes#дескриптор-процесса-task_struct|task_struct]]» — wikilink с якорем. Якорь slug-form. Правильно: `#Дескриптор процесса: task_struct`. Класс: correct.
- permissions-and-capabilities.md:46. «[`open()`](file-descriptors.md)» — markdown-ссылка с `()` в тексте linka. Формат странный, но работает. Target без якоря, хотя open() обсуждается в нескольких местах file-descriptors.md. Класс: correct (improvement, можно на якорь `#Откуда берётся дескриптор`).
- permissions-and-capabilities.md:226. «[[linux/containers/containers#capabilities-дробление-root-привилегий|Контейнеры]]» — wikilink с якорем. Якорь slug-form. Реальный заголовок `## Capabilities: дробление root-привилегий` (строка 214 containers.md). Правильно: `#Capabilities: дробление root-привилегий`. Класс: correct.

**Якоря findings:**

- permissions-and-capabilities.md:25. `#дескриптор-процесса-task_struct` — slug-form. Правильно: `#Дескриптор процесса: task_struct`. Класс: correct.
- permissions-and-capabilities.md:226. `#capabilities-дробление-root-привилегий` — slug-form. Правильно: `#Capabilities: дробление root-привилегий`. Класс: correct.

**Формат ссылок findings:**

- permissions-and-capabilities.md:25, 226. Wikilinks с якорями — формат правильный. Якоря неправильные.
- Остальные markdown-ссылки — правильный формат по §6.5.

**Внутренние якоря findings:**

- permissions-and-capabilities.md:27, 292 «Real UID и real GID». Определены в разделе `## Идентичность процесса` (23). Упоминаются в разделе «Сброс привилегий» (228) и «Полная картина» (290). Внутренние якоря на `[[permissions-and-capabilities#Идентичность процесса|RUID]]` в далёких разделах — по §6.2 полезны. Класс: correct (минорно).
- permissions-and-capabilities.md:292, 298. «capabilities», «EUID», «setuid/setgid» — определены в своих секциях, многократно используются в финальном разделе «Полная картина». Якоря избирательно. Класс: correct.

**Wip-queue кандидаты:**

- «SELinux», «AppArmor», «PAM», «ACL» (permissions-and-capabilities.md:306) — упомянуты как «тема отдельных заметок», но заметок пока нет. Ожидаемый слой: `linux/security/` (не существует в репо). Явные кандидаты для wip-queue. Но priority низкий: заметка сама говорит «тема отдельных заметок», что ок как forward-planning.

#### Фокус B: conceptual integration (V-shape)

**Missing downward mental links:**

- permissions-and-capabilities.md:83–98. Setuid bit, рубрика с восьмеричными правами (`4000`, `2000`, `1000`) — это биты на уровне inode. Без ссылки на `../../foundations/foundations.md` или `../../computer/programmer-model/abi-and-data-layout.md` (как байт хранится, как биты читаются) опор нет. Но концепция достаточно базовая, не нужна downward-связь.
- permissions-and-capabilities.md:60–73. Чтение inode, сравнение EUID — это алгоритм проверки прав. Хорошо читается как есть.

**Missing upward motivation:**

- permissions-and-capabilities.md:228–288. Паттерн Nginx master→workers с `setgid`+`setuid` — отличный пример, полностью покрывает упоминание. Upward-связь на реальные приложения (PostgreSQL postmaster+backends через setuid, Rails/Unicorn workers через `USER` в Docker) отсутствует. Но это уже поднялось бы выше слоя заметки (ОС vs приложение-уровень).
- permissions-and-capabilities.md:306. Финальный абзац про MAC, SELinux, AppArmor, ACL, PAM — правильное направление для будущих заметок, без лишних upward-ссылок.

## Общие корни

Три систематических паттерна пронизывают почти все файлы:

**1. Slug-form якоря повсюду, где есть `#anchor`.** Из 15 wikilink-ссылок с якорем — 12 содержат якорь в slug-форме (нижний регистр, дефисы, без двоеточий/скобок). Только 3 примера правильного формата: `#OOM killer: последняя линия защиты`, `#Динамический линкер: ld-linux`, `#exec(): замена программы` (все в `virtual-memory.md` и `processes.md`). Автор знает правильный формат, но большинство инстанций написаны по slug-привычке.

Список всех неправильных якорей по файлам:
- cpu-modes-and-syscalls.md:52, 101(×2)
- processes.md:35, 89, 259 (плюс markdown-нарушение)
- threads.md:26, 30, 42, 89
- file-descriptors.md:95, 235
- virtual-memory.md:90, 141, 174
- filesystems.md:25
- scheduler.md:37, 41, 45(×3), 91
- permissions-and-capabilities.md:25, 226

Правка — механическая: grep по `#[a-zа-я-]+` в wikilinks, замена на точный текст заголовка.

**2. Смешение wikilink и markdown для `../`-ссылок.** §6.5 прямо запрещает wikilink для ссылок с `../`-префиксом (Quartz резолвит от vault-root, но путь относительный). Нарушения:
- threads.md ссылается на sockets/signals — частично wikilink, частично markdown (смешение).
- file-descriptors.md:23, 222 — wikilink `[[linux/programming/sockets|сокет]]` для `../programming/` target.
- scheduler.md:75 — то же.
- processes.md:39 — `[[linux/programming/signals|сигнальные]]` (wikilink для target через `../programming/`).

Нужна нормализация к markdown для всех non-anchor ссылок на `../`-пути.

**3. Markdown-ссылка с якорем — единичный, но явный случай.** processes.md:259 — `[паттерне демонизации](../infrastructure/terminals.md#паттерн-демонизации)`. §6.3 категорично: «любая ссылка с якорем — wikilink». Плюс сам якорь slug-form.

**4. Отсутствующие internal anchors при повторных content-упоминаниях.** Определение в одном разделе + использование в далёком разделе без `[[file#Заголовок|термин]]`. Больше всего — в файлах с финальными «Сценарий целиком» (`processes.md:281`, `virtual-memory.md:324`) и в разделах, переиспользующих определения из первой половины файла.

**5. Downward-пробелы: `computer/programmer-model/` редко линкуется.** Регистры CPU (`rax`, `rsp`, `rbp`, `rip`), ABI calling convention, SIMD-регистры FPU/SSE/AVX, pipeline flush — появляются в `cpu-modes-and-syscalls.md`, `processes.md`, `scheduler.md`. Ни разу не линкуется `abi-and-data-layout.md`, `isa.md`, `simd.md`. Это реальный ментальный разрыв: термины вводятся как данность, хотя `computer/programmer-model/` их объясняет.

## Wip-queue кандидаты отдельной секцией

### Ожидаемый слой: algorithms-and-data-structures

**Red-black tree** — отдельная заметка `algorithms-and-data-structures/non-linear/red-black-tree.md`. Сейчас используется как «известная структура» в `scheduler.md:119` (CFS runqueue, EEVDF) и `virtual-memory.md:188` (VMA lookup, O(log n)). Обе ссылки ведут на parent-концепт `binary-search-tree.md`, что не раскрывает specific свойства red-black (self-balancing через цвета узлов и ограниченные ротации, amortized O(log n) с малой константой). Два независимых потребителя — по §9 structure-guide это порог для выделения shared-заметки. Зачем: читатель planner'а ОС должен понять, почему именно red-black, а не AVL, hash table или skip list.

### Ожидаемый слой: computer/ или отдельная security-ветка

**IBRS (Indirect Branch Restricted Speculation)** — упоминается в `cpu-modes-and-syscalls.md:101` как часть стоимости syscall после Spectre-митигаций. Inline-расшифровка есть, но полная механика — часть широкой темы Spectre/Meltdown/speculative execution. Ожидаемый слой: `linux/kernel/` (как дополнение к syscall-internals.md) или `computer/cpu/` (как специализация out-of-order-execution).

### Ожидаемый слой: linux/security/ (не существует)

**SELinux, AppArmor, PAM, ACL** — упомянуты в финальном абзаце `permissions-and-capabilities.md:306` как «тема отдельных заметок». Сам текст планирует их создание. Wip-кандидаты с низким priority (автор явно обозначил).

### Ожидаемый слой: linux/kernel/ (отдельная заметка)

**seccomp-BPF** — есть раздел в `containers.md` (строка 170), упомянутый в `CLAUDE.md` как «deferred refactor» (перенести в отдельную заметку при появлении второго потребителя). Не Integration-проблема, а структурная — отмечена автором.
