# Отображение памяти

<details>
<summary>Предпосылки</summary>

[виртуальная память](../foundations/05-virtual-memory.md) (страницы, page table, page fault, demand paging), [файловые системы](../foundations/06-filesystems.md) (page cache, inode).

</details>

← [Сигналы](00-signals.md) | [Файловый ввод-вывод](02-file-io.md) →

Аналитический сервис загружает файл размером 500 МБ с историей транзакций. Классический подход — системный вызов `read()`: ядро читает данные с диска в page cache, затем копирует их оттуда в буфер процесса в user space. На файл в 500 МБ это 500 МБ `memcpy` из ядра в пространство пользователя. Если сервис работает с несколькими такими файлами одновременно, двойной расход памяти (page cache + пользовательский буфер) и стоимость копирования становятся ощутимы.

`mmap()` (memory map — отображение памяти) устраняет копирование: вместо перекладывания данных из ядра в пользовательский буфер процесс получает виртуальные адреса, указывающие напрямую на страницы page cache. Данные существуют в физической памяти ровно в одной копии.

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

Когда процесс обращается к `data[0]`, процессор не находит физическую страницу в PTE и генерирует page fault. Обработчик page fault в ядре проверяет VMA, находит соответствующий файл и смещение, загружает 4 КБ страницу из файла в page cache (или берёт уже имеющуюся), вписывает физический адрес этой страницы в PTE и возвращает управление. Повторный доступ к `data[0]` — обычное чтение из памяти, порядка 1 нс.

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

Флаги `mmap()` определяют, что происходит при записи в отображённую область и откуда берётся физическая память. Три комбинации покрывают большинство задач.

### MAP_PRIVATE + файловый дескриптор: copy-on-write

Именно так работает загрузка исполняемых файлов. Когда ядро запускает программу через `execve()`, сегмент `.text` (машинный код) отображается как `MAP_PRIVATE | PROT_READ | PROT_EXEC`. Десять процессов, запустивших один и тот же бинарник, разделяют одни и те же физические страницы с кодом.

Запись в `MAP_PRIVATE`-отображение не затрагивает файл. Ядро применяет copy-on-write (CoW): при первой попытке записи создаётся приватная копия страницы, принадлежащая только этому процессу. Оригинал в page cache остаётся неизменным.

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

`MAP_SHARED` связывает запись в память с записью в файл. Изменённые страницы помечаются как «грязные» (dirty) в page cache, и ядро периодически сбрасывает их на диск (writeback). Явный вызов `msync()` гарантирует, что данные записаны до возврата.

Этот режим — основа работы баз данных, использующих mmap. LMDB (Lightning Memory-Mapped Database) отображает файл базы данных через `MAP_SHARED` — все читающие процессы разделяют одни и те же страницы page cache без копирования. PostgreSQL использует другой подход: shared memory через `MAP_ANONYMOUS|MAP_SHARED` для буферного кеша ([shared_buffers](../../databases/postgresql/durability/01-buffer-cache.md)), а не файловый mmap таблиц.

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

Два процесса, вызвавших `mmap(MAP_SHARED)` на один файл, видят изменения друг друга: оба работают с одними и теми же страницами page cache. Синхронизация между процессами — ответственность программиста (мьютексы, атомарные операции).

### MAP_ANONYMOUS: чистая память без файла

`MAP_ANONYMOUS` (или `MAP_ANON`) выделяет память, не связанную с файлом. Страницы инициализируются нулями, дескриптор не нужен (передаётся `-1`).

`malloc()` в glibc использует `mmap(MAP_ANONYMOUS | MAP_PRIVATE)` для аллокаций свыше 128 КБ (порог `MMAP_THRESHOLD`). Маленькие аллокации обслуживает `brk()`/`sbrk()`, но крупные блоки выгоднее выделять через `mmap`: при `munmap()` память сразу возвращается ядру, без фрагментации кучи.

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

Обработка ошибок различается принципиально. `read()` возвращает `-1` и устанавливает `errno` — стандартный путь. С `mmap` ошибка чтения с диска (bad sector, NFS timeout) приходит как сигнал `SIGBUS` при обращении к отображённой странице. Обработка `SIGBUS` требует `sigaction()` и `siglongjmp()` — код усложняется.

## mprotect(): изменение прав доступа

`mprotect()` (memory protect — защита памяти) изменяет права доступа к уже отображённым страницам. Границы должны быть выровнены по размеру страницы (4 КБ).

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

Guard page (страница-охранник) — страница с правами `PROT_NONE`, размещённая на границе стека потока. Любое обращение к ней вызывает `SIGSEGV`. Без guard page переполнение стека тихо перезаписывает соседнюю память — ошибку, которую трудно отладить.

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

`madvise()` (memory advise — совет по управлению памятью) не меняет поведение программы, но влияет на производительность. Ядро использует подсказки для настройки read-ahead и управления физическими страницами.

**MADV_SEQUENTIAL** сообщает ядру: доступ будет последовательным. Ядро увеличивает окно read-ahead и освобождает уже прочитанные страницы. Для нашего аналитического сервиса, если обработка идёт от начала к концу файла, `MADV_SEQUENTIAL` сокращает количество page fault'ов.

**MADV_RANDOM** — обратная подсказка: доступ непредсказуем. Ядро отключает read-ahead, не тратя ресурсы на предзагрузку страниц, которые не понадобятся. Индексные файлы, хеш-таблицы — типичный случай.

**MADV_WILLNEED** запускает асинхронную предзагрузку указанного диапазона в page cache. Аналог `posix_fadvise(POSIX_FADV_WILLNEED)`, но для отображённых регионов.

**MADV_DONTNEED** — самая сильная подсказка: ядро немедленно освобождает физические страницы региона. Виртуальные адреса остаются валидными, но при следующем обращении данные загружаются заново (для файлового отображения) или обнуляются (для `MAP_ANONYMOUS`).

jemalloc (аллокатор памяти в Firefox, FreeBSD, Redis) использует `MADV_DONTNEED` для возврата неиспользуемых страниц ядру без вызова `munmap()`. Это дешевле, чем пересоздавать отображение: VMA остаётся на месте, только физические страницы освобождаются.

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

`MAP_SHARED` с файловым дескриптором работает для межпроцессного обмена, но требует файл на диске. POSIX (Portable Operating System Interface) shared memory предоставляет альтернативу: разделяемый объект в tmpfs (`/dev/shm`), существующий только в оперативной памяти. Shared memory — один из нескольких механизмов [межпроцессного взаимодействия](06-ipc.md); сравнение с семафорами, очередями сообщений и передачей fd — в отдельной заметке.

`shm_open()` (shared memory open — открыть объект разделяемой памяти) создаёт именованный объект и возвращает файловый дескриптор. Дальше работа идёт по привычной схеме: `ftruncate()` задаёт размер, `mmap(MAP_SHARED)` отображает в адресное пространство.

Сценарий: два процесса обмениваются массивом счётчиков. Объём — 100 МБ. Через pipe или Unix socket это потребует сериализации, копирования в ядро и обратно. Через shared memory оба процесса работают с одними и теми же физическими страницами напрямую.

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

Мьютекс с атрибутом `PTHREAD_PROCESS_SHARED` размещается в самой разделяемой памяти — оба процесса обращаются к одному и тому же `pthread_mutex_t`. Без синхронизации одновременная запись и чтение приводят к гонкам данных и неопределённому поведению.

Компиляция требует линковки с `librt`: `gcc writer.c -o writer -lrt -lpthread`.

Объект `/myshm` существует в `/dev/shm` до явного вызова `shm_unlink("/myshm")` или перезагрузки системы. Утечка объектов в `/dev/shm` — частая ошибка: если процесс завершился аварийно, объект остаётся. На production-серверах стоит проверять `/dev/shm` на наличие забытых объектов.

## munmap() и очистка

`munmap()` удаляет отображение: VMA удаляется, PTE инвалидируются, физические страницы возвращаются ядру (если на них нет других ссылок). Для `MAP_SHARED` грязные страницы остаются в page cache после `munmap()` и будут записаны на диск через writeback — но момент записи не определён. Для гарантии durability нужен `msync(MS_SYNC)` перед `munmap()`.

Типичные ошибки при работе с отображениями:

Использование `data` после `munmap()` — use-after-unmap. В отличие от `free()`, где повторное обращение может какое-то время «работать» (память остаётся в адресном пространстве), после `munmap()` доступ к региону немедленно вызывает `SIGSEGV`.

`close(fd)` не отменяет отображение. `mmap()` привязывается к inode файла, а не к дескриптору. Закрытие дескриптора после `mmap()` — нормальная практика, отображение продолжает работать.

Неправильный размер в `munmap()`: если `mmap()` отобразил 500 МБ, а `munmap()` вызван с размером 256 МБ, вторая половина отображения останется до завершения процесса. Утечка виртуального адресного пространства.

## Когда mmap недостаточно: контроль над записью

`mmap` устраняет копирование kernel-user и даёт прямой доступ к page cache. Но контроль над записью ограничен: грязные страницы сбрасываются ядром в произвольный момент (writeback), а `msync()` не гарантирует порядок записи между разными страницами. Для базы данных, которой нужно записать WAL-запись (WAL — Write-Ahead Log, журнал предзаписи) строго до страницы данных — с гарантией порядка и точным моментом `fsync()` — необходим прямой файловый ввод-вывод с контролем флагов `O_SYNC`, `O_DSYNC` и `O_DIRECT`.

## Sources

- Michael Kerrisk, 2010, *The Linux Programming Interface* — Chapter 49: Memory Mappings
- `man 2 mmap`, `man 2 mprotect`, `man 2 madvise`, `man 3 shm_open`

---

← [Сигналы](00-signals.md) | [Файловый ввод-вывод](02-file-io.md) →
