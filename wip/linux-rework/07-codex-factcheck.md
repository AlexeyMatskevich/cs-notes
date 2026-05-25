# Codex factcheck review (task-mobr33tj-z5jyxu, 7m 42s)

## 3 находки

### L1: Ambient capabilities formula (permissions-and-capabilities.md:190-198)

**Claim в тексте:** `new_ambient = ambient (сохраняется, если не нарушены правила)` без явной оговорки, когда именно ambient сбрасывается.

**Что говорит man 7 capabilities:** `P'(ambient) = (file is privileged) ? 0 : P(ambient)`. «Privileged» = setuid, setgid или назначенные file capabilities. При запуске privileged-файла ambient сбрасывается в ноль — это защита, чтобы setuid-binary не унаследовал посторонние capabilities.

**Почему важно:** это центральная модель privilege transitions через execve. Как написано, читатель может ожидать, что ambient переживает любой execve — классическая ловушка с wrapper-бинарями, setuid-помощниками и container entrypoints.

**Источник:** https://www.man7.org/linux/man-pages/man7/capabilities.7.html, «Ambient (since Linux 4.3)» + «Transformation of capabilities during execve()».

### L2: task_struct vs struct cred (permissions-and-capabilities.md:178)

**Claim в тексте:** «У каждого потока хранятся пять наборов в `task_struct`».

**Что говорит kernel.org:** credentials (UID, GID, capability sets) живут в refcounted `struct cred`; task_struct только указывает на неё через `task_struct->cred`. Это важно для модели fork/exec — при fork cred разделяется, пока setuid/execve не создаст новую.

**Источник:** https://www.kernel.org/doc/html/latest/security/credentials.html, «Task Credentials».

### L2: kernel stack size (threads.md:192)

**Claim в тексте:** «kernel-stack 16 КБ на поток… для 100 000 соединений это уже 1.6 ГБ только на стеки ядра».

**Что говорит kernel docs:** Codex сослался на 404 URL (docs.kernel.org/6.3/x86/kernel-stacks.html — страница не существует). По исходникам `arch/x86/include/asm/page_64_types.h`: на x86-64 defconfig `THREAD_SIZE = 4 × PAGE_SIZE = 16 КБ` (без KASAN), с `CONFIG_KASAN` удваивается до 32 КБ; на 32-битных архитектурах — 8 КБ (2 × PAGE_SIZE). Утверждение «16 КБ» корректно для x86-64 defconfig, но нужно version scoping.

**Почему важно:** арифметика зависит от архитектуры/конфига. Качественный вывод (упор в RAM ограничивает число потоков) остаётся верным.

## Применено

1. **Permissions.md**: в разделе «Наборы capabilities» добавлена фраза про `struct cred` и его взаимоотношение с `task_struct`. Раздел «Ambient» переписан: формула `execve` заменена на корректную из man 7 capabilities, в том числе `P'(ambient) = privileged-файл ? 0 : P(ambient)`; добавлено объяснение, когда ambient сбрасывается.
2. **Threads.md**: раздел «Предел 1:1» получил version scoping — kernel stack 16 КБ на x86-64 defconfig (с явной ссылкой на `THREAD_SIZE = 4 × PAGE_SIZE`), 32 КБ с KASAN, 8 КБ на 32-битных архитектурах. Арифметика 1.6 ГБ привязана к x86-64 defconfig.

## Остальное из priority list — корректно

Codex явно отметил как чистые на запрошенном уровне точности:
- syscall latency (order of magnitude)
- CFS/EEVDF/autogroup/file-capability versioning (даты и номера ядер)
- `PID_MAX_LIMIT` атрибуция ядру
- BUFSIZ значения (glibc 8192, musl 1024, FreeBSD 4096)
- ext4 ordered journaling default
- half-MD4 формулировка
- Модель 1:1 с Go goroutine 2 KB stack
