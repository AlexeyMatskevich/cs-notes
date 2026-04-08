# Мультиплексирование ввода-вывода

> [!info]- Предпосылки
> [сокеты](03-sockets.md) (TCP-сервер, accept, `O_NONBLOCK`), [отображение памяти](01-memory-mapping.md) (mmap для shared memory между ядром и процессом), [синхронизация](../concurrency/00-synchronization.md) (futex как прецедент userspace fast path).

← [Сокеты](03-sockets.md) | [Управление памятью](05-memory-management.md) →

TCP-сервер принимает соединение через `accept()`, получает fd клиента, вызывает `read()` — и если клиент ещё ничего не отправил, поток блокируется. Один поток не может обслужить второго клиента, пока первый молчит. Очевидное решение — по потоку на соединение. Для 10 000 одновременных клиентов это 10 000 потоков. Каждый поток получает стек размером 8 МБ по умолчанию в Linux. Физически до первого обращения занята одна страница (4 КБ), но виртуальное адресное пространство зарезервировано целиком. 10 000 потоков — 80 ГБ виртуальных адресов. Переключение между ними обходится в 1-5 мкс на context switch, а планировщик при таком числе потоков тратит заметную долю CPU просто на выбор следующего кандидата.

Нужен способ мониторить тысячи файловых дескрипторов (fd) из одного потока, реагируя только на те, которые готовы к чтению или записи. Это задача мультиплексирования ввода-вывода (I/O multiplexing). За сорок лет ядро Unix/Linux прошло три поколения решений: `select`/`poll` — сканирование полного списка fd при каждом вызове, O(n) на каждую проверку; `epoll` — однократная регистрация fd и получение только готовых, O(ready); `io_uring` — отправка и получение результатов операций через разделяемую память без системных вызовов на горячем пути.

## select: первое поколение (1983, 4.2 BSD)

`select()` принимает три битовых множества (fd_set): для чтения, записи и исключительных состояний. Каждое множество — битовая карта фиксированного размера: бит с номером n установлен, если fd n интересует вызывающего.

```c
fd_set readfds;
FD_ZERO(&readfds);
FD_SET(listen_fd, &readfds);
FD_SET(client_fd, &readfds);

int nfds = (listen_fd > client_fd ? listen_fd : client_fd) + 1;
int ready = select(nfds, &readfds, NULL, NULL, &timeout);
```

Аргумент `nfds` — число, на единицу больше максимального fd в множестве. Ядро проходит биты от 0 до `nfds - 1`, проверяя состояние каждого. При возврате `select()` **модифицирует** переданные множества: биты, соответствующие неготовым fd, сбрасываются. Это означает, что перед каждым вызовом множества нужно перестраивать заново. При 1 000 fd это 1 000 вызовов `FD_SET` в цикле плюс сканирование 1 000 бит внутри ядра — и всё повторяется при каждом обороте event loop.

Три ограничения делают `select` непригодным для серверов с большим числом соединений. Размер `fd_set` определяется константой `FD_SETSIZE`, которая на Linux равна 1024. Сервер с 1025 соединениями не может использовать `select` без перекомпиляции с изменённой константой. Второе ограничение — линейное сканирование: ядро проверяет каждый бит от 0 до `nfds`, даже если из 10 000 fd данные пришли только в три. Третье — разрушение множеств при возврате, вынуждающее перестраивать их снова.

## poll: снятие лимита 1024

`poll()` заменяет битовые множества массивом структур `struct pollfd`:

```c
struct pollfd {
    int   fd;       /* дескриптор */
    short events;   /* какие события интересуют (POLLIN, POLLOUT) */
    short revents;  /* какие события произошли (заполняется ядром) */
};
```

Размер массива произвольный — ограничения `FD_SETSIZE` нет. Ядро не перезаписывает поле `events`, а заполняет отдельное `revents`, поэтому перестраивать массив не нужно.

Но главная проблема осталась: при каждом вызове `poll()` ядро проходит весь массив от первого до последнего элемента, проверяя состояние каждого fd. Для 10 000 соединений, из которых активны 50, ядро проверяет 10 000 структур и возвращает 50 готовых. Стоимость одного вызова `poll` с 10 000 fd — 50-100 мкс, и основная часть времени тратится на проверку дескрипторов, в которых ничего не произошло.

## epoll: регистрация и готовность

`epoll` разделяет две операции, которые `select` и `poll` совмещали в одном вызове: регистрацию интересующих fd и ожидание событий. Регистрация происходит один раз. Ожидание возвращает только готовые fd, не сканируя остальные.

Интерфейс состоит из трёх системных вызовов.

**`epoll_create1(0)`** создаёт экземпляр epoll и возвращает fd, представляющий его. Внутри ядра экземпляр содержит две структуры: красно-чёрное дерево ([BST](../../algorithms-and-data-structures/non-linear/03-binary-search-tree.md), самобалансирующийся вариант) для хранения зарегистрированных fd и связанный список готовых fd (ready list).

**`epoll_ctl(epfd, op, fd, &event)`** добавляет (`EPOLL_CTL_ADD`), модифицирует (`EPOLL_CTL_MOD`) или удаляет (`EPOLL_CTL_DEL`) fd из дерева. Добавление в красно-чёрное дерево стоит O(log n) — для 10 000 fd это ~14 сравнений. При добавлении ядро устанавливает callback: когда сетевой стек помещает пакет в буфер приёма сокета, callback перемещает запись из дерева в ready list.

**`epoll_wait(epfd, events, maxevents, timeout)`** забирает из ready list до `maxevents` записей. Если список пуст — поток засыпает до появления событий или истечения таймаута. Стоимость вызова пропорциональна числу готовых fd, а не общему числу зарегистрированных.

```
                   epoll instance
              ┌──────────────────────┐
              │   red-black tree     │    Хранит все 10 000 fd
              │   (все fd)           │    Добавление: O(log n)
              │                      │
              │   ┌───┐ ┌───┐       │
              │   │fd3│ │fd7│ ...   │
              │   └─┬─┘ └───┘       │
              │     |                │
              │     | пакет пришёл   │
              │     v                │
              │   ready list         │    Только готовые fd
              │   fd3 -> fd88 ->    │    epoll_wait читает отсюда
              └──────────────────────┘
```

Сравнение: `poll` с 10 000 fd тратит 50-100 мкс на каждый вызов независимо от числа событий. `epoll_wait` при тех же 10 000 fd и 50 готовых — 1-3 мкс. Разница в 30-50 раз, и она растёт с увеличением числа соединений. Стоимость `epoll_create1` — порядка 1 мкс, `epoll_ctl` — 200-500 нс.

## Скелет event loop на epoll

Типичный однопоточный сервер, обслуживающий тысячи соединений:

```c
#include <sys/epoll.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#define MAX_EVENTS 64
#define PORT 8080

static void set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

int main(void) {
    int listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons(PORT),
        .sin_addr.s_addr = INADDR_ANY
    };
    bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr));
    listen(listen_fd, 128);
    set_nonblocking(listen_fd);

    int epfd = epoll_create1(0);
    struct epoll_event ev = { .events = EPOLLIN, .data.fd = listen_fd };
    epoll_ctl(epfd, EPOLL_CTL_ADD, listen_fd, &ev);

    struct epoll_event events[MAX_EVENTS];

    for (;;) {
        int n = epoll_wait(epfd, events, MAX_EVENTS, -1);

        for (int i = 0; i < n; i++) {
            if (events[i].data.fd == listen_fd) {
                /* новое соединение */
                for (;;) {
                    int client = accept(listen_fd, NULL, NULL);
                    if (client == -1) {
                        if (errno == EAGAIN) break; /* все принято */
                        break;
                    }
                    set_nonblocking(client);
                    ev.events = EPOLLIN | EPOLLET;
                    ev.data.fd = client;
                    epoll_ctl(epfd, EPOLL_CTL_ADD, client, &ev);
                }
            } else {
                /* данные от клиента */
                char buf[4096];
                for (;;) {
                    ssize_t cnt = read(events[i].data.fd, buf, sizeof(buf));
                    if (cnt == -1) {
                        if (errno == EAGAIN) break; /* всё прочитано */
                        close(events[i].data.fd);
                        break;
                    }
                    if (cnt == 0) {
                        /* клиент закрыл соединение */
                        close(events[i].data.fd);
                        break;
                    }
                    write(events[i].data.fd, buf, cnt); /* echo */
                }
            }
        }
    }
    return 0;
}
```

Один поток, один `epoll_wait`, тысячи соединений. Ключевые моменты: слушающий сокет регистрируется как `EPOLLIN` — событие означает, что в очереди есть новые соединения. Клиентские сокеты добавляются в epoll по мере принятия. Каждый готовый fd обрабатывается в неблокирующем режиме: `read()` вызывается в цикле до `EAGAIN`, что гарантирует полное вычитывание буфера.

## Level-triggered и edge-triggered

`epoll` поддерживает два режима уведомления о готовности fd.

**Level-triggered (LT, по уровню)** — режим по умолчанию. `epoll_wait` сообщает о fd, пока в его буфере есть данные. Если `read()` прочитал часть данных, а в буфере осталось ещё, следующий `epoll_wait` вернёт этот fd снова. Режим прощает ошибки: даже если программа прочитала не всё, она получит повторное уведомление. Redis использует LT — код проще, а для его нагрузочного профиля (короткие команды, маленькие пакеты) разница в производительности минимальна.

**Edge-triggered (ET, по фронту)** — уведомление приходит только при изменении состояния fd: из «не готов» в «готов». Если пришёл пакет и `epoll_wait` вернул fd, но программа прочитала не все данные, повторного уведомления не будет — до прихода следующего пакета. Программа обязана вычитать буфер до `EAGAIN` при каждом событии. Пропуск означает зависший fd, с которого данные никогда не прочитаются.

```
LT (level-triggered):                ET (edge-triggered):

  буфер fd:  [####____]                буфер fd:  [####____]
  read: 2 байта                        read: 2 байта
  буфер fd:  [##______]                буфер fd:  [##______]
  epoll_wait: fd готов (данные есть)    epoll_wait: fd НЕ возвращается
                                        (состояние не менялось)
```

ET включается флагом `EPOLLET` в `epoll_ctl`. nginx использует ET — при десятках тысяч соединений сокращение числа возвратов из `epoll_wait` экономит десятки микросекунд на каждом обороте event loop.

Дополнительный флаг `EPOLLONESHOT` снимает регистрацию fd после первого события. Это полезно в многопоточном event loop: без `EPOLLONESHOT` два потока могут одновременно получить событие для одного fd и начать `read()` параллельно, порождая гонку. С `EPOLLONESHOT` fd нужно перерегистрировать через `EPOLL_CTL_MOD` после обработки.

## timerfd: таймеры через файловый дескриптор

Серверу нужны не только сетевые события. Проверка тайм-аутов соединений, периодическая отправка keepalive-пакетов, отложенная повторная отправка — всё это таймеры. До `timerfd` таймеры реализовывались через аргумент timeout в `epoll_wait` или через `setitimer()` / сигнал `SIGALRM`. Оба варианта неудобны: timeout в `epoll_wait` один на весь вызов (нельзя назначить разные интервалы для разных задач), а сигналы прерывают системные вызовы и требуют нетривиальной обработки.

`timerfd_create()` создаёт fd, который становится читаемым, когда срабатывает таймер. Этот fd добавляется в epoll наравне с сокетами — event loop обрабатывает таймеры тем же кодом, что и сетевые события.

```c
#include <sys/timerfd.h>
#include <stdint.h>

int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK);

struct itimerspec ts = {
    .it_value    = { .tv_sec = 5, .tv_nsec = 0 },   /* первый тик через 5 с */
    .it_interval = { .tv_sec = 1, .tv_nsec = 0 }    /* затем каждую секунду */
};
timerfd_settime(tfd, 0, &ts, NULL);

/* добавляем в epoll */
struct epoll_event ev = { .events = EPOLLIN, .data.fd = tfd };
epoll_ctl(epfd, EPOLL_CTL_ADD, tfd, &ev);

/* в event loop при срабатывании: */
uint64_t expirations;
read(tfd, &expirations, sizeof(expirations));
/* expirations = сколько раз таймер сработал с момента последнего read */
```

Первый аргумент `timerfd_create` — источник времени. **`CLOCK_MONOTONIC`** отсчитывает время от произвольной точки (обычно загрузки системы) и никогда не прыгает назад. NTP-коррекция (NTP — Network Time Protocol, протокол сетевой синхронизации времени), ручной перевод часов, переход на летнее время — `CLOCK_MONOTONIC` ничего этого не видит. Для таймаутов и интервалов это единственный надёжный источник: если keepalive-таймер выставлен на 30 секунд, он сработает ровно через 30 секунд реального времени, даже если администратор в этот момент сдвинул системные часы на час назад.

**`CLOCK_REALTIME`** — системные часы (wall clock). Полезен для задач, привязанных к астрономическому времени: выполнить задачу в 03:00 UTC. Но подвержен прыжкам: NTP может сдвинуть часы на секунды или даже минуты, что приведёт к преждевременному или запоздалому срабатыванию таймера.

**`CLOCK_BOOTTIME`** — как `CLOCK_MONOTONIC`, но включает время в режиме suspend (sleep/hibernate). Если ноутбук был усыплён на час, `CLOCK_MONOTONIC` не заметит этого часа, а `CLOCK_BOOTTIME` — учтёт. Для серверов, работающих на физических машинах без suspend, разницы нет.

## signalfd: сигналы в event loop

[signalfd](00-signals.md) превращает сигнал в fd, совместимый с epoll. Сигнал (`SIGTERM`, `SIGINT`) перестаёт прерывать процесс в произвольном контексте и вместо этого появляется как событие `EPOLLIN` в event loop — наравне с сетевыми сокетами и таймерами. Ключевой момент: без `sigprocmask(SIG_BLOCK)` перед созданием signalfd сигнал по-прежнему доставляется через обычный обработчик, а не через fd. Подробности механизма, код и ограничения — в [заметке о сигналах](00-signals.md).

## eventfd: уведомление между потоками

В многопоточном сервере рабочий поток завершает вычисление и должен сообщить потоку event loop, что результат готов. Классический способ — `pipe()`: записать байт в write-конец, event loop увидит готовность read-конца в epoll. Но pipe создаёт два fd и буфер ядра на 64 КБ для каждого уведомления.

`eventfd` — облегчённая альтернатива: один fd, один 8-байтовый счётчик в ядре.

```c
#include <sys/eventfd.h>

int efd = eventfd(0, EFD_NONBLOCK);
epoll_ctl(epfd, EPOLL_CTL_ADD, efd, &(struct epoll_event){
    .events = EPOLLIN, .data.fd = efd
});

/* рабочий поток — уведомление: */
uint64_t val = 1;
write(efd, &val, sizeof(val));  /* счётчик += 1 */

/* поток event loop — приём: */
uint64_t val;
read(efd, &val, sizeof(val));   /* val = накопленное значение, счётчик -> 0 */
```

`write()` атомарно прибавляет записанное значение к счётчику. `read()` атомарно считывает текущее значение и обнуляет счётчик. Если счётчик > 0, fd считается готовым для чтения — epoll вернёт его. Один `eventfd` заменяет pipe, занимая один fd вместо двух и не выделяя 64 КБ буфера.

Итого: `timerfd`, `signalfd`, `eventfd` — три механизма, превращающих таймеры, сигналы и межпоточные уведомления в файловые дескрипторы. Все три добавляются в один epoll-экземпляр, и event loop обрабатывает все типы событий единообразно — одним вызовом `epoll_wait`.

## io_uring: устранение системных вызовов

`epoll` устранил сканирование O(n), но не убрал системные вызовы. Каждая операция ввода-вывода — отдельный syscall: `epoll_wait` сообщает о готовности fd, затем программа вызывает `read()`, `write()`, `accept()`, `send()`. Сервер, обрабатывающий 100 000 IOPS (I/O Operations Per Second, операций ввода-вывода в секунду), совершает минимум 200 000-300 000 системных вызовов в секунду: `epoll_wait` + операция на каждое событие. Каждый syscall — это переход в режим ядра (~100-200 нс), сохранение и восстановление регистров, проверка прав.

io_uring, добавленный в ядро 5.1 (2019, автор — Jens Axboe), решает эту проблему принципиально: ядро и пользовательский процесс обмениваются запросами и результатами через два кольцевых буфера в разделяемой памяти (shared memory, отображённой через [mmap](01-memory-mapping.md)). Отправка запроса — запись 64 байт в память. Получение результата — чтение 16 байт из памяти. Системный вызов нужен только для уведомления ядра о новых записях, а в режиме SQPOLL не нужен вообще.

### Архитектура: SQ и CQ

```
            userspace                         kernel
   ┌──────────────────────┐         ┌──────────────────────┐
   │                      │  mmap   │                      │
   │   SQ (Submission     │ <-----> │   SQ consumer        │
   │        Queue)        │         │   (обрабатывает SQE) │
   │                      │         │                      │
   │   ┌──────┬──────┐   │         │                      │
   │   │ SQE  │ SQE  │...│         │                      │
   │   │ 64 B │ 64 B │   │         │                      │
   │   └──────┴──────┘   │         │                      │
   │         |            │         │         |            │
   │         | submit     │         │         | complete   │
   │         v            │         │         v            │
   │   CQ (Completion     │ <-----> │   CQ producer        │
   │        Queue)        │         │   (пишет CQE)        │
   │                      │         │                      │
   │   ┌──────┬──────┐   │         │                      │
   │   │ CQE  │ CQE  │...│         │                      │
   │   │ 16 B │ 16 B │   │         │                      │
   │   └──────┴──────┘   │         │                      │
   └──────────────────────┘         └──────────────────────┘
```

**SQ (Submission Queue)** — кольцевой буфер, куда процесс помещает запросы. Каждый запрос — структура SQE (Submission Queue Entry) размером 64 байта: тип операции (`IORING_OP_READ`, `IORING_OP_ACCEPT`, `IORING_OP_SEND`, ...), fd, буфер, смещение, пользовательские данные для идентификации.

**CQ (Completion Queue)** — кольцевой буфер, откуда процесс забирает результаты. Каждый результат — CQE (Completion Queue Entry) размером 16 байт: код возврата операции (аналог возвращаемого значения `read()` / `write()`) и пользовательские данные из соответствующего SQE.

Оба кольца отображены в адресное пространство процесса через mmap. Процесс записывает SQE в SQ и продвигает tail-указатель. Ядро читает SQE по head-указателю и продвигает его. Для CQ — зеркально: ядро записывает CQE и продвигает tail, процесс читает по head. Синхронизация — через атомарные операции на указателях; блокировки не нужны.

**`io_uring_enter()`** — единственный системный вызов. Он уведомляет ядро, что в SQ есть новые записи, и опционально ждёт завершения указанного числа операций. Один вызов `io_uring_enter` может отправить пакет из десятков операций — вместо десятков отдельных syscall.

### Пример: echo-сервер на liburing

Библиотека `liburing` (Jens Axboe) оборачивает низкоуровневый mmap и атомарные указатели в удобный API:

```c
#include <liburing.h>
#include <netinet/in.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>

#define ENTRIES 256
#define PORT 8080

enum { OP_ACCEPT, OP_READ, OP_WRITE };

struct request {
    int type;
    int fd;
    char buf[4096];
};

int main(void) {
    struct io_uring ring;
    io_uring_queue_init(ENTRIES, &ring, 0);

    int listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons(PORT),
        .sin_addr.s_addr = INADDR_ANY
    };
    bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr));
    listen(listen_fd, 128);

    /* первый accept */
    struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    struct request *req = calloc(1, sizeof(*req));
    req->type = OP_ACCEPT;
    req->fd = listen_fd;
    io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0);
    io_uring_sqe_set_data(sqe, req);
    io_uring_submit(&ring);

    for (;;) {
        struct io_uring_cqe *cqe;
        io_uring_wait_cqe(&ring, &cqe);

        struct request *r = io_uring_cqe_get_data(cqe);
        int res = cqe->res;

        if (r->type == OP_ACCEPT && res >= 0) {
            int client_fd = res;

            /* следующий accept */
            sqe = io_uring_get_sqe(&ring);
            io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0);
            io_uring_sqe_set_data(sqe, r);

            /* read от нового клиента */
            sqe = io_uring_get_sqe(&ring);
            struct request *rr = calloc(1, sizeof(*rr));
            rr->type = OP_READ;
            rr->fd = client_fd;
            io_uring_prep_read(sqe, client_fd, rr->buf, sizeof(rr->buf), 0);
            io_uring_sqe_set_data(sqe, rr);

        } else if (r->type == OP_READ && res > 0) {
            /* echo: отправить обратно */
            sqe = io_uring_get_sqe(&ring);
            r->type = OP_WRITE;
            io_uring_prep_write(sqe, r->fd, r->buf, res, 0);
            io_uring_sqe_set_data(sqe, r);

        } else if (r->type == OP_WRITE) {
            /* после записи — снова читаем */
            sqe = io_uring_get_sqe(&ring);
            r->type = OP_READ;
            io_uring_prep_read(sqe, r->fd, r->buf, sizeof(r->buf), 0);
            io_uring_sqe_set_data(sqe, r);

        } else {
            /* ошибка или закрытие соединения */
            close(r->fd);
            free(r);
            io_uring_cqe_seen(&ring, cqe);
            continue;
        }

        io_uring_cqe_seen(&ring, cqe);
        io_uring_submit(&ring);
    }
    return 0;
}
```

В отличие от epoll-версии, здесь нет отдельных `accept()`, `read()`, `write()` — все операции отправляются как SQE и завершаются как CQE. `io_uring_submit()` — обёртка вокруг `io_uring_enter()`, один syscall на пакет операций. `io_uring_wait_cqe()` считывает CQE из completion ring.

### SQPOLL: нулевые системные вызовы

Режим `IORING_SETUP_SQPOLL` при создании кольца поднимает отдельный поток ядра (kernel thread), который непрерывно опрашивает SQ на наличие новых записей. Процесс записывает SQE в память — поток ядра подхватывает их без `io_uring_enter()`. Результаты появляются в CQ — процесс читает их из памяти. На горячем пути — ноль системных вызовов.

```c
struct io_uring_params params = { .flags = IORING_SETUP_SQPOLL };
io_uring_queue_init_params(ENTRIES, &ring, &params);
```

Цена SQPOLL — одно ядро CPU полностью занято polling-потоком. Если поток ядра не обнаруживает новых SQE в течение настраиваемого интервала (`sq_thread_idle`, по умолчанию ~1 с), он засыпает, и для пробуждения потребуется `io_uring_enter()`. Для серверов с постоянной нагрузкой (десятки тысяч IOPS) выделение одного ядра на polling окупается: устраняется jitter от syscall и context switch.

### Связанные операции

io_uring поддерживает флаг `IOSQE_IO_LINK` на SQE: следующий SQE выполняется только после успешного завершения текущего. Это позволяет выразить цепочки вроде «прочитай из файла, затем запиши в сокет» как два SQE, не возвращаясь в userspace между ними. Ядро само выполняет второй шаг после первого — userspace узнает о результатах, когда оба CQE появятся в completion ring.

### Поддерживаемые операции

io_uring заменяет не только `read`/`write`, но и практически весь набор операций ввода-вывода: `accept`, `connect`, `send`, `recv`, `sendmsg`, `recvmsg`, `fsync`, `fallocate`, `openat`, `close`, `statx`. Каждая операция — отдельный код `IORING_OP_*`. По сути, io_uring — это асинхронный интерфейс ко всему ядру, а не только к сетевым сокетам.

## epoll и io_uring: когда что использовать

epoll работает с ядра 2.6 (2004) и поддерживается на любом Linux-сервере. API проще: три вызова, понятная модель «уведомление о готовности → операция». Для большинства серверов (до 50 000-100 000 соединений, до 100 000 IOPS) epoll достаточен, и дополнительная сложность io_uring не окупается.

io_uring даёт выигрыш, когда узким местом становятся системные вызовы: NVMe-хранилища (NVMe — Non-Volatile Memory Express) с задержкой 10-20 мкс на операцию (200 нс syscall overhead = 1-2% потерь при каждой операции), серверы с > 100 000 IOPS, приложения, чувствительные к хвостовым задержкам (tail latency). В бенчмарках (fio, ядро 5.10) io_uring с SQPOLL достигает 400 000 IOPS на NVMe, epoll в аналогичном сценарии — около 200 000 IOPS. Разница объясняется именно устранением syscall overhead и batch-обработкой.

Минимальная версия ядра для io_uring — 5.1, но полноценная сетевая поддержка (`IORING_OP_ACCEPT`, `IORING_OP_RECV`) появилась в 5.5-5.6. SQPOLL требует `CAP_SYS_NICE` или ядро 5.12+.

Цепочка развития: блокирующий ввод-вывод (один fd — один поток) → `select`/`poll` (один поток, но O(n) сканирование) → `epoll` (уведомление только о готовых fd, O(ready)) → `io_uring` (операции через разделяемую память, 0 syscalls на горячем пути).

## Sources

- Michael Kerrisk, 2010, *The Linux Programming Interface* — Chapter 63: Alternative I/O Models: https://man7.org/tlpi/
- Jens Axboe, 2019, *Efficient IO with io_uring*: https://kernel.dk/io_uring.pdf
- `man 7 epoll`: https://man7.org/linux/man-pages/man7/epoll.7.html
- `man 2 io_uring_enter`: https://man7.org/linux/man-pages/man2/io_uring_enter.2.html
- `man 2 timerfd_create`: https://man7.org/linux/man-pages/man2/timerfd_create.2.html
- `man 2 signalfd`: https://man7.org/linux/man-pages/man2/signalfd.2.html
- `man 2 eventfd`: https://man7.org/linux/man-pages/man2/eventfd.2.html

---

← [Сокеты](03-sockets.md) | [Управление памятью](05-memory-management.md) →
