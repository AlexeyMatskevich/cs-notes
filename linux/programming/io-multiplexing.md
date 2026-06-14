---
tags:
  - domain/linux
  - theme/networking
  - theme/performance
  - type/concept
aliases:
  - I/O Multiplexing
  - epoll
  - io_uring
order: 17
---

# Мультиплексирование ввода-вывода

> [!info]- Предпосылки
> [сокеты](sockets.md) (TCP-сервер, accept, `O_NONBLOCK`), [отображение памяти](memory-mapping.md) (mmap для shared memory между ядром и процессом).

← [Сокеты](sockets.md) | [Управление памятью](memory-management.md) →

TCP-сервер принимает соединение через `accept()`, получает [fd](../foundations/file-descriptors.md) клиента, вызывает `read()` — и если клиент ещё ничего не отправил, поток блокируется. Один поток не может обслужить второго клиента, пока первый молчит. Очевидное решение — по [потоку](../foundations/threads.md) на соединение. Но 10 000 одновременных клиентов означают 10 000 потоков: десятки гигабайт виртуальных адресов под стеки и постоянное [[linux/foundations/scheduler#Переключение контекста|переключение контекста]] между ними. Конкретная цена одного потока и одного context switch разобрана в заметке о потоках — здесь важно лишь то, что при таком масштабе модель «поток на соединение» упирается в потолок задолго до того, как заканчивается работа.

Нужен способ мониторить тысячи [файловых дескрипторов](../foundations/file-descriptors.md) (fd) из одного потока, реагируя только на те, которые готовы к чтению или записи. Это задача мультиплексирования ввода-вывода (I/O multiplexing). За сорок лет ядро Unix/Linux прошло три поколения решений: `select`/`poll` — сканирование полного списка fd при каждом вызове, стоимость растёт линейно с числом fd (O(n)); `epoll` — однократная регистрация fd и получение только готовых, стоимость зависит только от числа сработавших событий (O(ready)); `io_uring` — отправка и получение результатов операций через разделяемую память без системных вызовов на горячем пути.

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

Аргумент `nfds` — число, на единицу больше максимального fd в множестве. Ядро проходит биты от 0 до `nfds - 1`, проверяя состояние каждого. При возврате `select()` **модифицирует** переданные множества: биты, соответствующие неготовым fd, сбрасываются. Это означает, что перед каждым вызовом множества нужно перестраивать заново. При 1 000 fd это 1 000 вызовов `FD_SET` в цикле плюс сканирование 1 000 бит внутри ядра — и всё повторяется при каждом обороте event loop (один проход цикла, который ждёт события и обрабатывает готовые fd).

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

Хочется платить только за активные fd. А для этого ядру нужно знать список интересующих дескрипторов заранее, чтобы не перестраивать его при каждом вызове и чтобы было куда складывать события по мере их прихода.

## epoll: регистрация и готовность

`epoll` разделяет две операции, которые `select` и `poll` совмещали в одном вызове: регистрацию интересующих fd и ожидание событий. Регистрация происходит один раз. Ожидание возвращает только готовые fd, не сканируя остальные.

Интерфейс состоит из трёх системных вызовов.

**`epoll_create1(0)`** создаёт экземпляр epoll и возвращает [fd](../foundations/file-descriptors.md), представляющий его. Внутри ядра экземпляр содержит две структуры: [[linux/foundations/scheduler#Красно-чёрное дерево|красно-чёрное дерево]] для хранения всех зарегистрированных fd (быстрая индексация по fd — тот же механизм, что и у планировщика CFS) и связанный список готовых fd (ready list).

**`epoll_ctl(epfd, op, fd, &event)`** добавляет (`EPOLL_CTL_ADD`), модифицирует (`EPOLL_CTL_MOD`) или удаляет (`EPOLL_CTL_DEL`) запись о fd в дереве — вставка и поиск за O(log n). При добавлении ядро устанавливает callback: когда сетевой стек помещает пакет в буфер приёма сокета, callback добавляет ссылку на эту запись в ready list. Сама запись остаётся в дереве до явного `EPOLL_CTL_DEL` — один и тот же объект одновременно живёт и в дереве (индекс для модификаций), и в ready list (очередь готовых событий), пока fd не снят с регистрации.

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
              │     | при приходе    │
              │     | пакета ядро    │
              │     | добавляет      │
              │     | ссылку в       │
              │     v                │
              │   ready list         │    Ссылки на готовые fd
              │   fd3 -> fd88 ->     │    epoll_wait читает отсюда
              └──────────────────────┘
```

Сравнение: `poll` с 10 000 fd тратит 50-100 мкс на каждый вызов независимо от числа событий. `epoll_wait` при тех же 10 000 fd и 50 готовых — 1-3 мкс. Разница в 30-50 раз, и она растёт с увеличением числа соединений. На практике такое ускорение напрямую превращается в возможность держать больше одновременных соединений на одном ядре и в снижение хвостовых задержек p99 (99-й перцентиль задержки, для худшего 1% запросов): процесс не тратит время на бесплодный обход чужих дескрипторов перед тем, как обработать пришедший пакет. Стоимость `epoll_create1` — порядка 1 мкс, `epoll_ctl` — 200-500 нс.

## Скелет event loop на epoll

Собираем сервер, который обслуживает тысячи соединений из одного потока. Логика такая: на старте мы регистрируем слушающий сокет и уходим в `epoll_wait`. Когда приходит подключение, листенер сигналит о готовности, мы принимаем клиента и регистрируем его fd. Когда клиент присылает данные, epoll возвращает уже клиентский fd, мы читаем буфер до конца и отвечаем. Всё это — один поток и один цикл:

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
                    ev.events = EPOLLIN | EPOLLET; /* EPOLLET — edge-triggered */
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

Один поток, один `epoll_wait`, тысячи соединений. Ключевые моменты: слушающий сокет регистрируется как `EPOLLIN` — событие означает, что в очереди есть новые соединения. Клиентские сокеты добавляются в epoll по мере принятия. `EAGAIN` — это код возврата «сейчас данных нет, попробуй позже»: на неблокирующем сокете вместо того, чтобы усыпить поток, `read()` / `accept()` возвращает ошибку `EAGAIN`, и мы выходим из внутреннего цикла. Поэтому `read()` вызывается в цикле до `EAGAIN` — это гарантирует полное вычитывание буфера и необходимо в режиме [[io-multiplexing#Edge-triggered (ET)|edge-triggered]] (флаг `EPOLLET`).

## Level-triggered и edge-triggered

`epoll` поддерживает два режима уведомления о готовности fd.

### Level-triggered (LT)

Режим по умолчанию (по уровню). `epoll_wait` сообщает о fd, пока в его буфере есть данные. Если `read()` прочитал часть данных, а в буфере осталось ещё, следующий `epoll_wait` вернёт этот fd снова. Режим прощает ошибки: даже если программа прочитала не всё, она получит повторное уведомление.

### Edge-triggered (ET)

Уведомление приходит только при изменении состояния fd (по фронту): из «не готов» в «готов». Если пришёл пакет и `epoll_wait` вернул fd, но программа прочитала не все данные, повторного уведомления не будет — до прихода следующего пакета. Программа обязана вычитать буфер до `EAGAIN` при каждом событии. Пропуск означает зависший fd, с которого данные никогда не прочитаются.

```
LT (level-triggered):                ET (edge-triggered):

  буфер fd:  [####____]                буфер fd:  [####____]
  read: 2 байта                        read: 2 байта
  буфер fd:  [##______]                буфер fd:  [##______]
  epoll_wait: fd готов (данные есть)    epoll_wait: fd НЕ возвращается
                                        (состояние не менялось)
```

[[linux/programming/io-multiplexing#Edge-triggered (ET)|ET]] включается флагом `EPOLLET` в `epoll_ctl`. Причина выигрыша проста: при [[linux/programming/io-multiplexing#Level-triggered (LT)|LT]] одно и то же непрочитанное сообщение возвращается из `epoll_wait` столько раз, сколько раундов event loop прошло до того, как его прочитают; при ET — ровно один раз, пока программа не вычитает буфер до `EAGAIN`. На десятках тысяч соединений это экономит десятки микросекунд на каждом обороте цикла. Практическое правило: ET — когда профилировщик показывает заметную долю времени в `epoll_wait` на повторных уведомлениях и когда сервер обрабатывает длинные объёмы за одно событие; LT — когда логика проще в ручном управлении (прочитал одну запись — вернулся) или когда пакеты короткие и разница незаметна. Redis идёт по LT-пути, libevent поддерживает оба режима через `EV_ET`.

Дополнительный флаг `EPOLLONESHOT` отключает fd в epoll после первого события — дескриптор остаётся зарегистрированным, но перестаёт генерировать уведомления, пока программа не реактивирует его через `EPOLL_CTL_MOD`. Это полезно в многопоточном event loop: без `EPOLLONESHOT` два потока могут одновременно получить событие для одного fd и начать `read()` параллельно, порождая гонку.

## Таймеры, сигналы и уведомления как файловые дескрипторы

Реальный event loop обрабатывает не только сетевые сокеты. Ему нужны таймеры, реакция на сигналы (например, `SIGTERM` при graceful shutdown), уведомления от рабочих потоков о готовых результатах. Традиционно всё это — отдельные механизмы со своими интерфейсами: `setitimer`, обработчики сигналов, pipe'ы для межпоточного wake-up. Linux предлагает другой подход: превратить каждый из этих источников событий в файловый дескриптор, после чего `epoll_wait` обрабатывает их единообразно, одним вызовом и одним кодом. Три таких «fd-адаптера» — `timerfd`, `signalfd` и `eventfd`.

### timerfd: таймеры через файловый дескриптор

Серверу нужны таймеры: проверка тайм-аутов соединений, периодическая отправка keepalive-пакетов, отложенная повторная отправка. До `timerfd` таймеры реализовывались через аргумент timeout в `epoll_wait` или через `setitimer()` / сигнал [SIGALRM](signals.md). Оба варианта неудобны: timeout в `epoll_wait` один на весь вызов (нельзя назначить разные интервалы для разных задач), а сигналы прерывают системные вызовы и требуют нетривиальной обработки.

`timerfd_create()` создаёт [fd](../foundations/file-descriptors.md), который становится читаемым, когда срабатывает таймер. Этот fd добавляется в epoll наравне с сокетами — event loop обрабатывает таймеры тем же кодом, что и сетевые события.

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

Первый аргумент `timerfd_create` — источник времени. Для таймаутов и интервалов нужен **`CLOCK_MONOTONIC`**: он отсчитывает время от произвольной точки, никогда не прыгает назад от ручного перевода часов или ступенчатой NTP-коррекции (плавные подстройки через `adjtime` он видит, но они не создают скачков). Если keepalive-таймер выставлен на 30 секунд, он сработает через ~30 секунд реального времени, даже если администратор сдвинул системные часы. Существуют и другие источники (`CLOCK_REALTIME` для привязки к астрономическому времени, `CLOCK_BOOTTIME` для учёта времени в suspend), но для серверных таймеров `CLOCK_MONOTONIC` — дефолт.

### signalfd: сигналы в event loop

Сигнал — это асинхронное уведомление, которое ядро доставляет процессу: `SIGTERM` от `kill`, `SIGINT` от Ctrl+C, `SIGCHLD` при завершении дочернего процесса. Обычно сигнал прерывает текущий поток в произвольный момент и передаёт управление зарегистрированному обработчику; в обработчике нельзя вызывать почти ничего (подробности в [заметке о сигналах](signals.md)) — отсюда классическая боль при graceful shutdown.

[[linux/programming/signals#signalfd(): сигналы как файловые дескрипторы|signalfd]] превращает сигнал в [fd](../foundations/file-descriptors.md), совместимый с epoll: вместо прерывания в обработчике процесс читает сигналы через `read()` из своего event loop, как данные с сокета. Сигнал нужно предварительно заблокировать в обычном канале доставки — иначе он по-прежнему будет прерывать процесс напрямую. Механика блокировки, код и ограничения — в той же заметке о сигналах.

### eventfd: уведомление между потоками

В многопоточном сервере рабочий поток завершает вычисление и должен сообщить потоку event loop, что результат готов. Классический способ — `pipe()`: записать байт в write-конец, event loop увидит готовность read-конца в epoll. Но pipe занимает два fd и держит собственный буфер в ядре (64 КБ по умолчанию) — избыточно для единственного «тик-тик-проснись» байта.

`eventfd` — облегчённая альтернатива: один [fd](../foundations/file-descriptors.md), один 8-байтовый счётчик в ядре.

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
uint64_t count;
read(efd, &count, sizeof(count)); /* count = накопленное значение, счётчик -> 0 */
```

`write()` атомарно прибавляет записанное значение к счётчику. `read()` атомарно считывает текущее значение и обнуляет счётчик. Если счётчик > 0, fd считается готовым для чтения — epoll вернёт его. Суммирование здесь атомарно — неделимо, без переслаивания одновременных записей ([атомарные операции](../../computer/atomic-instructions.md)) — и это решает типичную проблему pipe-wakeup: пятьдесят рабочих потоков, завершившие задачу одновременно, схлопываются в одну запись со значением 50, а event loop получит ровно одно событие — без thundering herd (лавина одновременных пробуждений) и без риска переполнения pipe-буфера.

## io_uring: устранение системных вызовов

`epoll` устранил сканирование O(n), но не убрал системные вызовы. На каждое событие приходится минимум два syscall: `epoll_wait`, чтобы узнать о готовности fd, и следом `read()` / `write()` / `accept()` / `send()`, чтобы выполнить саму операцию. Сервер на 100 000 IOPS (I/O Operations Per Second, операций ввода-вывода в секунду) совершает 200 000-300 000 системных вызовов в секунду, и каждый — это [[linux/foundations/cpu-modes-and-syscalls#Цена системного вызова|переход в режим ядра]] ценой 100-500 нс с сохранением и восстановлением регистров и проверкой прав.

io_uring, добавленный в ядро 5.1 (2019, автор — Jens Axboe), решает эту проблему принципиально: ядро и пользовательский процесс обмениваются запросами и результатами через два кольцевых буфера (ring buffer — очередь на фиксированном массиве, где запись и чтение идут по кругу через независимые head- и tail-указатели, без сдвигов элементов) в разделяемой памяти (shared memory, отображённой через [mmap](memory-mapping.md)). Отправка запроса — запись 64 байт в память. Получение результата — чтение 16 байт из памяти. Системный вызов нужен только для уведомления ядра о новых записях, а в режиме SQPOLL не нужен вообще.

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

#### SQ (Submission Queue)

Кольцевой буфер, куда процесс помещает запросы.

#### SQE (Submission Queue Entry)

Каждый запрос — структура SQE размером 64 байта: тип операции (`IORING_OP_READ`, `IORING_OP_ACCEPT`, `IORING_OP_SEND`, ...), [fd](../foundations/file-descriptors.md), буфер, смещение, пользовательские данные для идентификации.

#### CQ (Completion Queue)

Кольцевой буфер, откуда процесс забирает результаты.

#### CQE (Completion Queue Entry)

Каждый результат — структура CQE размером 16 байт: код возврата операции (аналог возвращаемого значения `read()` / `write()`) и пользовательские данные из соответствующего [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]].

Оба кольца отображены в адресное пространство процесса через mmap. Процесс записывает [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]] в [[linux/programming/io-multiplexing#SQ (Submission Queue)|SQ]] и продвигает tail-указатель. Ядро читает SQE по head-указателю и продвигает его. Для [[linux/programming/io-multiplexing#CQ (Completion Queue)|CQ]] — зеркально: ядро записывает [[linux/programming/io-multiplexing#CQE (Completion Queue Entry)|CQE]] и продвигает tail, процесс читает по head. Синхронизация — это [lock-free](../concurrency/lock-free.md) паттерн с атомарными операциями на head/tail-указателях колец, без взаимных блокировок между userspace и ядром.

**`io_uring_enter()`** — единственный системный вызов. Он уведомляет ядро, что в [[linux/programming/io-multiplexing#SQ (Submission Queue)|SQ]] есть новые записи, и опционально ждёт завершения указанного числа операций. Один вызов `io_uring_enter` может отправить пакет из десятков операций — вместо десятков отдельных syscall.

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

В отличие от epoll-версии, здесь нет отдельных `accept()`, `read()`, `write()` — все операции отправляются как [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]] и завершаются как [[linux/programming/io-multiplexing#CQE (Completion Queue Entry)|CQE]]. `io_uring_submit()` — обёртка вокруг `io_uring_enter()`, один syscall на пакет операций. `io_uring_wait_cqe()` считывает CQE из completion ring.

Один пакет проходит через эту машину состояний так. На старте сервер кладёт в [[linux/programming/io-multiplexing#SQ (Submission Queue)|SQ]] первый `accept` и блокируется на `wait_cqe`. Клиент подключается — ядро возвращает [[linux/programming/io-multiplexing#CQE (Completion Queue Entry)|CQE]] с `type == ACCEPT` и новым `client_fd`; обработчик сразу ставит в SQ два [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]]: следующий `accept` для нового клиентского подключения и `read` на только что полученный `client_fd`. Когда данные приходят, на `client_fd` выпадает CQE с `type == READ` — обработчик ставит `write` с теми же данными. После CQE `type == WRITE` он снова ставит `read`, и цикл замыкается. Каждое состояние дескриптора — отдельный SQE; между ними код не возвращается в ядро и не блокируется ни на одном syscall, кроме финального `wait_cqe`.

### SQPOLL: нулевые системные вызовы

`io_uring_submit` — это всё ещё один системный вызов на пакет операций. Можно ли убрать и его? Режим `IORING_SETUP_SQPOLL` при создании кольца поднимает отдельный [[linux/foundations/threads#Предел 1:1 и user-space потоки|поток ядра]], который непрерывно опрашивает [[linux/programming/io-multiplexing#SQ (Submission Queue)|SQ]] на наличие новых записей. Процесс записывает [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]] в память — поток ядра подхватывает их без `io_uring_enter()`. Результаты появляются в [[linux/programming/io-multiplexing#CQ (Completion Queue)|CQ]] — процесс читает их из памяти. На горячем пути — ноль системных вызовов.

```c
struct io_uring_params params = { .flags = IORING_SETUP_SQPOLL };
io_uring_queue_init_params(ENTRIES, &ring, &params);
```

Цена SQPOLL — одно ядро CPU полностью занято polling-потоком. Если за настраиваемый интервал `sq_thread_idle` (типично задаётся приложением порядка сотен миллисекунд) новых [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]] не появилось, поток ядра засыпает и ставит флаг `IORING_SQ_NEED_WAKEUP`. Userspace обязан его заметить и разбудить поток вызовом `io_uring_enter` — liburing делает это автоматически внутри `io_uring_submit`, но «магии» здесь нет, просто библиотека берёт проверку флага на себя. Для серверов с постоянной нагрузкой (десятки тысяч IOPS) выделение одного ядра на polling окупается: устраняется jitter от syscall и context switch.

### io_uring как интерфейс ко всему ядру

Набор операций не ограничен парой `read`/`write`. Каждая операция кодируется отдельным `IORING_OP_*`: `accept`, `connect`, `send`, `recv`, `sendmsg`, `recvmsg`, `fsync`, `fallocate`, `openat`, `close`, `statx` — и этот список продолжает расти с каждой версией ядра. Любые два [[linux/programming/io-multiplexing#SQE (Submission Queue Entry)|SQE]] можно сцепить флагом `IOSQE_IO_LINK`: следующий запрос стартует только после завершения текущего, а при ошибке цепочка обрывается (для безусловного продолжения есть `IOSQE_IO_HARDLINK`). Цепочка «прочитай из файла, затем запиши в сокет» оформляется как два связанных SQE без возврата в userspace между ними. Практически это превращает io_uring из «альтернативы epoll» в общий асинхронный интерфейс ко всему, что ядро умеет делать через системные вызовы, — сетевые сокеты лишь часть картины.

## epoll и io_uring: когда что использовать

epoll работает с ядра 2.6 (2003) и поддерживается на любом Linux-сервере. API проще: три вызова, понятная модель «уведомление о готовности → операция». Для большинства сетевых серверов, где event loop большую часть времени ждёт пакеты, epoll достаточен, и дополнительная сложность io_uring не окупается.

io_uring даёт выигрыш тогда, когда именно системные вызовы становятся узким местом. Два характерных сценария. Первый — хвостовые задержки (tail latency) на сетевых серверах с очень высоким QPS (запросов в секунду): экономия одного-двух syscall на запрос сокращает p99 на единицы процентов, а в высококонкурентных нагрузках и больше. Второй — блочный ввод-вывод на NVMe (Non-Volatile Memory Express, PCIe-протокол для флэш-накопителей с задержкой операции 10-20 мкс): при такой задержке 100-500 нс syscall overhead превращаются в заметные проценты потерь на каждой операции, а для обычных файлов epoll в принципе неприменим — файл всегда «готов» с точки зрения epoll, и нативно асинхронную работу дают только libaio и io_uring. Переход с epoll на io_uring в таких системах обычно даёт заметное снижение хвостовых задержек и рост пропускной способности; конкретные цифры сильно зависят от железа, профиля нагрузки и версии ядра.

Минимальная версия ядра для io_uring — 5.1 (май 2019, Jens Axboe), но полноценная сетевая поддержка подтягивалась отдельно: `IORING_OP_ACCEPT` в 5.5, `IORING_OP_RECV` / `SEND` в 5.6. SQPOLL до 5.11 требовал root, в 5.11 ограничение ослаблено до `CAP_SYS_NICE`, а с 5.13 снято совсем.

Цепочка развития: блокирующий ввод-вывод (один fd — один поток) → `select`/`poll` (один поток, но O(n) сканирование) → `epoll` (уведомление только о готовых fd, O(ready)) → `io_uring` (операции через разделяемую память, 0 syscalls на горячем пути).

## См. также

- [[ruby/internal/concurrency#Fiber::Scheduler: перехват блокирующих операций|Ruby Fiber scheduler]] — Async gem и falcon реализуют `Fiber::SchedulerInterface` поверх `io_uring`/`epoll`: миллионы fiber'ов на одном потоке кооперативно ждут I/O

## Sources

- Michael Kerrisk, 2010, *The Linux Programming Interface* — Chapter 63: Alternative I/O Models: https://man7.org/tlpi/
- Jens Axboe, 2019, *Efficient IO with io_uring*: https://kernel.dk/io_uring.pdf
- `man 7 epoll`: https://man7.org/linux/man-pages/man7/epoll.7.html
- `man 2 io_uring_enter`: https://man7.org/linux/man-pages/man2/io_uring_enter.2.html
- `man 2 timerfd_create`: https://man7.org/linux/man-pages/man2/timerfd_create.2.html
- `man 2 signalfd`: https://man7.org/linux/man-pages/man2/signalfd.2.html
- `man 2 eventfd`: https://man7.org/linux/man-pages/man2/eventfd.2.html

---

← [Сокеты](sockets.md) | [Управление памятью](memory-management.md) →
