---
tags:
  - domain/linux
  - theme/memory
  - type/concept
aliases:
  - Memory Mapping
  - mmap
order: 14
---

# Отображение памяти

> [!info]- Предпосылки
> [виртуальная память](../foundations/virtual-memory.md) (страницы, page table, page fault, demand paging), [файловые системы](../foundations/filesystems.md) (page cache, inode).

← [Сигналы](signals.md) | [Файловый ввод-вывод](file-io.md) →

Сигналы решают задачу асинхронного уведомления — ядро может прервать процесс и заставить его отреагировать. Но процессу нужно не только реагировать на события, но и эффективно работать с данными: загружать файлы, обмениваться памятью с другими процессами, управлять правами доступа к регионам памяти. Стандартный `read()` копирует данные из ядра в пользовательский буфер — при больших объёмах это узкое место.

Аналитический сервис загружает файл размером 500 МБ с историей транзакций. Классический подход — системный вызов `read()`: ядро читает данные с диска в page cache, затем копирует их оттуда в буфер процесса в user space. На файл в 500 МБ это 500 МБ `memcpy` из ядра в пространство пользователя. Если сервис работает с несколькими такими файлами одновременно, двойной расход памяти (page cache + пользовательский буфер) и стоимость копирования становятся ощутимы.

`mmap()` (memory map — отображение памяти) устраняет копирование: вместо перекладывания данных из ядра в пользовательский буфер процесс получает виртуальные адреса, указывающие напрямую на страницы [[linux/foundations/filesystems#Page cache: файловые данные в оперативной памяти|page cache]]. Данные существуют в физической памяти ровно в одной копии.

## Как работает mmap

Вызов `mmap()` не читает файл. Ядро выполняет два действия: выделяет диапазон виртуальных адресов в адресном пространстве процесса и создаёт VMA (Virtual Memory Area — структура `vm_area_struct` в ядре, описывающая один непрерывный регион с правами доступа и привязкой к файлу). Page table entries (PTE) не создаются в этот момент — они появятся при первом обращении к каждой странице через page fault (demand paging). Ни одного байта с диска не прочитано — вызов возвращается за микросекунды.

```c
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>

int fd = open("transactions.dat", O_RDONLY);
size_t size = 500 * 1024 * 1024; // 500 MB

char *data = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);
if (data == MAP_FAILED) {
    perror("mmap");
    return 1;
}
close(fd); // дескриптор больше не нужен: отображение держит ссылку на inode
```

Когда процесс обращается к `data[0]`, процессор не находит физическую страницу в PTE и генерирует page fault. Обработчик page fault в ядре проверяет VMA, находит соответствующий файл и смещение, загружает 4 КБ страницу из файла в page cache (или берёт уже имеющуюся), вписывает физический адрес этой страницы в PTE и возвращает управление. Повторный доступ к `data[0]` — обычное чтение из памяти, [[computer/data-path/memory-hierarchy#Иерархия: от регистров до оперативной памяти|~1 нс при попадании в L1-кэш процессора, из RAM — порядка 60–100 нс]].

```text
mmap():                          Первый доступ к data[100]:

process virtual memory           process virtual memory
┌──────────────────────┐         ┌──────────────────────┐
│ ...                  │         │ ...                  │
│ data[0..4095]  ------│--x PTE  │ data[0..4095]  ------│--> page cache
│ data[4096..8191] ----│--x      │ data[4096..8191] ----│--x PTE absent
│ ...                  │         │ ...                  │
└──────────────────────┘         └──────────────────────┘
                                          |
 x = PTE marked absent            page fault --> kernel
                                  loads page from disk
                                  into page cache,
                                  updates PTE
```

Этот механизм — demand paging: страницы загружаются только при обращении. Файл в 500 МБ, из которого реально читается 10 МБ, занимает в физической памяти не больше 10 МБ.

## Три варианта отображения

Сценарий с 500 МБ был про чтение. Но приложению нужно и писать — иногда в тот же файл, иногда в память без файла вообще. Три комбинации флагов `mmap()` отвечают трём разным потребностям: читать файл без изменения оригинала, писать через page cache на диск, и выделять память без файла.

### MAP_PRIVATE + файловый дескриптор: copy-on-write

Именно так работает загрузка исполняемых файлов. Когда ядро запускает программу через `execve()` (системный вызов замены образа процесса), сегмент `.text` (машинный код) отображается как `MAP_PRIVATE | PROT_READ | PROT_EXEC`. Десять процессов, запустивших один и тот же бинарник, разделяют одни и те же физические страницы с кодом.

Запись в `MAP_PRIVATE`-отображение не затрагивает файл. Ядро применяет [[linux/foundations/virtual-memory#Copy-on-write: fork() без копирования|copy-on-write]] (CoW, копирование при записи): при первой попытке записи создаётся приватная копия страницы, принадлежащая только этому процессу. Оригинал в page cache остаётся неизменным.

```c
// Чтение конфигурационного файла с возможностью локальных модификаций
int fd = open("config.dat", O_RDONLY);
struct stat st;
fstat(fd, &st);

char *cfg = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, 0);
close(fd);

// Чтение — напрямую из page cache, без копирования
printf("version: %.4s\n", cfg);

// Запись — CoW: ядро создаёт приватную копию страницы
cfg[0] = 'X'; // изменяется только локальная копия, файл на диске не затронут

munmap(cfg, st.st_size);
```

### MAP_SHARED + файловый дескриптор: запись в файл

`MAP_SHARED` связывает запись в память с записью в файл. Изменённые страницы помечаются как «грязные» (dirty) в page cache, и ядро периодически сбрасывает их на диск (writeback, отложенная запись). Явный вызов `msync()` гарантирует, что данные записаны до возврата.

Этот режим — основа работы баз данных, использующих mmap. LMDB (Lightning Memory-Mapped Database) отображает файл базы данных через `MAP_SHARED` — все читающие процессы разделяют одни и те же страницы page cache без копирования. PostgreSQL использует другой подход: shared memory через `MAP_ANONYMOUS|MAP_SHARED` (по умолчанию) для буферного кеша ([[databases/postgresql/durability/buffer-cache#Shared Buffers — общий кеш для всех процессов|shared_buffers]]), а не файловый mmap таблиц.

```c
int fd = open("shared_data.dat", O_RDWR);
struct stat st;
fstat(fd, &st);

int *counters = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
close(fd);

counters[0] += 1; // запись попадает в page cache -> на диск при writeback

msync(counters, st.st_size, MS_SYNC); // принудительный сброс на диск
munmap(counters, st.st_size);
```

Два процесса, вызвавших `mmap(MAP_SHARED)` на один файл, видят изменения друг друга: оба работают с одними и теми же страницами page cache. Синхронизация между процессами — ответственность программиста ([[linux/concurrency/synchronization#Мьютекс|мьютекс]] (`pthread_mutex_t`) — примитив взаимного исключения; атомарные операции).

### MAP_ANONYMOUS: чистая память без файла

`MAP_ANONYMOUS` (или `MAP_ANON`) выделяет память, не связанную с файлом. Страницы инициализируются нулями, дескриптор не нужен (передаётся `-1`).

`malloc()` в [[linux/infrastructure/elf-and-linking#Динамическая линковка: разделяемые библиотеки|glibc]] использует `mmap(MAP_ANONYMOUS | MAP_PRIVATE)` для аллокаций свыше 128 КБ (порог `MMAP_THRESHOLD` — начальное значение; glibc динамически поднимает его при обработке освобождаемых блоков). Маленькие аллокации обслуживает `brk()`/`sbrk()`, но крупные блоки выгоднее выделять через `mmap`: при `munmap()` память сразу возвращается ядру, без фрагментации кучи.

```c
// Выделение 1 МБ анонимной памяти
size_t len = 1024 * 1024;
void *buf = mmap(NULL, len, PROT_READ | PROT_WRITE,
                 MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
if (buf == MAP_FAILED) {
    perror("mmap anon");
    return 1;
}

memset(buf, 0xAB, len); // страницы реально выделяются при первой записи
munmap(buf, len);        // память возвращена ядру немедленно
```

## mmap против read(): когда что выбирать

Для аналитического сервиса, который обращается к случайным смещениям в файле транзакций — `mmap` выигрывает. Нет промежуточного буфера, повторные обращения к одной странице стоят ~1 нс (данные уже в page cache, PTE валиден). Базы данных, индексные файлы, memory-mapped B-tree — типичные применения.

Для последовательной обработки — построчного чтения лога — `read()` может оказаться быстрее. Ядро применяет read-ahead: при последовательном чтении автоматически подгружает следующие 128 КБ (32 страницы по умолчанию). У `mmap` каждый page fault — переключение в ядро (порядка 1-3 мкс), и при строго последовательном проходе эти page fault'ы суммируются. `read()` обрабатывает read-ahead единым блоком.

Обработка ошибок различается принципиально. `read()` возвращает `-1` и устанавливает `errno` — стандартный путь. С `mmap` ошибка чтения с диска (bad sector, NFS timeout) приходит как [[linux/programming/signals#Установка обработчика: sigaction()|сигнал `SIGBUS`]] — сигнал аппаратной ошибки шины, отличный от `SIGSEGV` (нарушение защиты памяти). Типичный перехват: обработчик через [[linux/programming/signals#Установка обработчика: sigaction()|`sigaction()`]], внутри — `siglongjmp()` в точку восстановления. Путь ошибки заметно сложнее, чем проверка `errno` после `read()`.

До сих пор права доступа к отображению фиксировались в момент вызова `mmap()`. Но иногда их нужно менять уже после — и это отдельная задача.

## mprotect(): изменение прав доступа

`mprotect()` (memory protect — защита памяти) изменяет права доступа к уже отображённым страницам. Границы должны быть выровнены по размеру страницы (4 КБ на x86-64).

```c
#include <sys/mman.h>

// Выделяем страницу с правами чтения и записи
size_t page = 4096;
void *mem = mmap(NULL, page, PROT_READ | PROT_WRITE,
                 MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);

// Делаем страницу только для чтения
mprotect(mem, page, PROT_READ);
// Запись теперь вызовет SIGSEGV
```

### Guard pages: обнаружение переполнения стека

Без защиты стека переполнение молча перезаписывает соседнюю область памяти — ошибку крайне трудно отладить: данные оказываются повреждены задолго до того, как программа начинает вести себя неправильно. Guard page (страница-охранник) — страница с правами `PROT_NONE`, размещённая на границе стека потока. Любое обращение к ней вызывает `SIGSEGV`, немедленно указывая на источник проблемы.

```c
// Стек потока с guard page
size_t stack_size = 64 * 1024; // 64 KB
size_t guard_size = 4096;      // 1 page

char *region = mmap(NULL, guard_size + stack_size,
                    PROT_READ | PROT_WRITE,
                    MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);

// Первая страница — guard: запрещаем любой доступ
mprotect(region, guard_size, PROT_NONE);

// Стек начинается сразу после guard page
char *stack_bottom = region + guard_size;
// Если стек дорастёт до guard page -> SIGSEGV вместо тихой порчи данных
```

`pthread_create()` создаёт guard page автоматически (размер настраивается через `pthread_attr_setguardsize()`).

### JIT-компиляция: W^X

JIT-компилятор (JIT — Just-In-Time, компиляция «на лету»; V8, LuaJIT, YJIT в Ruby) генерирует машинный код в runtime. Политика W^X (Write XOR Execute) запрещает одновременное наличие прав на запись и исполнение — защита от эксплуатации уязвимостей. `mprotect()` переключает права:

```c
size_t page = 4096;
// Шаг 1: выделяем память с правами на запись
char *code = mmap(NULL, page, PROT_READ | PROT_WRITE,
                  MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);

// Шаг 2: записываем машинный код (x86-64: mov eax, 42; ret)
code[0] = 0xB8;                    // mov eax, imm32
code[1] = 0x2A; code[2] = 0x00;   // 42
code[3] = 0x00; code[4] = 0x00;
code[5] = 0xC3;                    // ret

// Шаг 3: убираем запись, добавляем исполнение
mprotect(code, page, PROT_READ | PROT_EXEC);

// Шаг 4: вызываем сгенерированный код
int (*fn)(void) = (int (*)(void))code;
printf("result: %d\n", fn()); // 42

munmap(code, page);
```

Без `mprotect()` пришлось бы выделять память сразу с `PROT_READ | PROT_WRITE | PROT_EXEC`, что нарушает W^X.

## madvise(): подсказки ядру

Ядро не знает, как именно приложение будет обращаться к отображённой области — идёт ли проход от начала к концу или случайные скачки по файлу. По умолчанию оно применяет усреднённые эвристики (тот же read-ahead), которые для одних паттернов работают хорошо, а для других тратят память впустую. `madvise()` (memory advise — совет по управлению памятью) позволяет сообщить ядру фактический паттерн доступа — это не меняет поведение программы, но влияет на производительность.

**MADV_SEQUENTIAL** сообщает ядру: доступ будет последовательным. Ядро увеличивает окно read-ahead и освобождает уже прочитанные страницы. Для нашего аналитического сервиса, если обработка идёт от начала к концу файла, `MADV_SEQUENTIAL` сокращает количество page fault'ов.

**MADV_RANDOM** — обратная подсказка: доступ непредсказуем. Ядро отключает read-ahead, не тратя ресурсы на предзагрузку страниц, которые не понадобятся. Индексные файлы, хеш-таблицы — типичный случай.

**MADV_WILLNEED** запускает асинхронную предзагрузку указанного диапазона в page cache. Аналог `posix_fadvise(POSIX_FADV_WILLNEED)`, но для отображённых регионов.

**MADV_DONTNEED** — самая сильная подсказка: ядро немедленно освобождает физические страницы региона. Виртуальные адреса остаются валидными, но при следующем обращении данные загружаются заново (для файлового отображения) или обнуляются (для `MAP_ANONYMOUS`).

jemalloc (аллокатор памяти во FreeBSD, Redis; Firefox использует форк `mozjemalloc`) использует `MADV_DONTNEED` для возврата неиспользуемых страниц ядру без вызова `munmap()`. Это дешевле, чем пересоздавать отображение: VMA остаётся на месте, только физические страницы освобождаются.

```c
char *data = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);

// Последовательная обработка от начала до конца
madvise(data, size, MADV_SEQUENTIAL);

for (size_t i = 0; i < size; i += 4096) {
    process_page(data + i);
}

// Обработка завершена — освобождаем физическую память
madvise(data, size, MADV_DONTNEED);
// VMA существует, но физические страницы освобождены
```

## POSIX shared memory: разделяемая память между процессами

`MAP_SHARED` с файловым дескриптором работает для межпроцессного обмена, но требует файл на диске. POSIX (Portable Operating System Interface) shared memory предоставляет альтернативу: разделяемый объект в tmpfs (`/dev/shm`), существующий только в оперативной памяти. Shared memory — один из нескольких механизмов [межпроцессного взаимодействия](ipc.md); сравнение с семафорами, очередями сообщений и передачей fd — в отдельной заметке.

`shm_open()` (shared memory open — открыть объект разделяемой памяти) создаёт именованный объект и возвращает [[linux/foundations/file-descriptors#файловые-дескрипторы|файловый дескриптор]]. Дальше работа идёт по привычной схеме: `ftruncate()` задаёт размер, `mmap(MAP_SHARED)` отображает в адресное пространство.

Сценарий: два [процесса](../foundations/processes.md) обмениваются массивом счётчиков. Объём — 100 МБ. Через pipe или [[linux/programming/sockets#Unix domain sockets: локальный обмен без сетевого стека|Unix socket]] это потребует сериализации, копирования в ядро и обратно. Через shared memory оба процесса работают с одними и теми же физическими страницами напрямую.

### Процесс-писатель

```c
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <pthread.h>

typedef struct {
    pthread_mutex_t lock;
    int counters[1024];
} shared_data_t;

int main(void) {
    // Создать объект разделяемой памяти
    int fd = shm_open("/myshm", O_CREAT | O_RDWR, 0600);
    ftruncate(fd, sizeof(shared_data_t));

    shared_data_t *shm = mmap(NULL, sizeof(shared_data_t),
                               PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);

    // Инициализация мьютекса с атрибутом PSHARED
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
    pthread_mutex_init(&shm->lock, &attr);
    pthread_mutexattr_destroy(&attr);

    memset(shm->counters, 0, sizeof(shm->counters));

    // Запись данных
    for (int i = 0; i < 100; i++) {
        pthread_mutex_lock(&shm->lock);
        shm->counters[i % 1024] += 1;
        pthread_mutex_unlock(&shm->lock);
    }

    munmap(shm, sizeof(shared_data_t));
    return 0;
}
```

### Процесс-читатель

```c
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <pthread.h>

typedef struct {
    pthread_mutex_t lock;
    int counters[1024];
} shared_data_t;

int main(void) {
    int fd = shm_open("/myshm", O_RDWR, 0);
    shared_data_t *shm = mmap(NULL, sizeof(shared_data_t),
                               PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);

    pthread_mutex_lock(&shm->lock);
    printf("counter[0] = %d\n", shm->counters[0]);
    pthread_mutex_unlock(&shm->lock);

    munmap(shm, sizeof(shared_data_t));
    // Объект живёт в /dev/shm до явного удаления
    // shm_unlink("/myshm"); — вызывает тот, кто владеет жизненным циклом
    return 0;
}
```

[[linux/concurrency/synchronization#Мьютекс|Мьютекс]] с атрибутом `PTHREAD_PROCESS_SHARED` размещается в самой разделяемой памяти — оба процесса обращаются к одному и тому же `pthread_mutex_t`. Без синхронизации одновременная запись и чтение приводят к гонкам данных и неопределённому поведению.

Компиляция требует линковки: `gcc writer.c -o writer -lrt -lpthread` (флаг `-lrt` нужен до glibc 2.34; в новых версиях `shm_open` живёт в libc и линковка с `-lrt` больше не обязательна).

Объект `/myshm` существует в `/dev/shm` до явного вызова `shm_unlink("/myshm")` или перезагрузки системы. Утечка объектов в `/dev/shm` — частая ошибка: если [процесс](../foundations/processes.md) завершился аварийно, объект остаётся. На production-серверах стоит проверять `/dev/shm` на наличие забытых объектов.

## munmap() и очистка

`munmap()` удаляет отображение: VMA удаляется, PTE инвалидируются, физические страницы возвращаются ядру (если на них нет других ссылок). Для `MAP_SHARED` грязные страницы остаются в page cache после `munmap()` и будут записаны на диск через writeback — но момент записи не определён. Для гарантии durability нужен `msync(MS_SYNC)` перед `munmap()`.

Типичные ошибки при работе с отображениями:

Использование `data` после `munmap()` — use-after-unmap. В отличие от `free()`, где повторное обращение может какое-то время «работать» (память остаётся в адресном пространстве), после `munmap()` доступ к региону немедленно вызывает `SIGSEGV`.

`close(fd)` не отменяет отображение. `mmap()` привязывается к inode файла, а не к дескриптору. Закрытие дескриптора после `mmap()` — нормальная практика, отображение продолжает работать.

Неправильный размер в `munmap()`: если `mmap()` отобразил 500 МБ, а `munmap()` вызван с размером 256 МБ, вторая половина отображения останется до завершения процесса. Утечка виртуального адресного пространства.

## Когда mmap недостаточно: контроль над записью

`mmap` устраняет копирование kernel-user и даёт прямой доступ к page cache. Но контроль над записью ограничен: грязные страницы сбрасываются ядром в произвольный момент (writeback), а `msync()` не гарантирует порядок записи между разными страницами. Для базы данных, которой нужно записать [WAL-запись](../../databases/postgresql/durability/wal.md) (WAL — Write-Ahead Log, журнал предзаписи) строго до страницы данных — с гарантией порядка и точным моментом `fsync()` — необходим прямой файловый ввод-вывод с контролем флагов [[linux/programming/file-io#O_SYNC и O_DSYNC: гарантия записи на диск|`O_SYNC`/`O_DSYNC`]] (синхронная запись с гарантией диска) и [[linux/programming/file-io#O_DIRECT: запись мимо page cache|`O_DIRECT`]] (обход page cache).

## Sources

- Michael Kerrisk, 2010, *The Linux Programming Interface* — Chapter 49: Memory Mappings: https://man7.org/tlpi/
- `man 2 mmap`: https://man7.org/linux/man-pages/man2/mmap.2.html
- `man 2 mprotect`: https://man7.org/linux/man-pages/man2/mprotect.2.html
- `man 2 madvise`: https://man7.org/linux/man-pages/man2/madvise.2.html
- `man 3 shm_open`: https://man7.org/linux/man-pages/man3/shm_open.3.html

---

← [Сигналы](signals.md) | [Файловый ввод-вывод](file-io.md) →
