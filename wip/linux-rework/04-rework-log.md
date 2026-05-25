# Rework log — linux/foundations/

Baseline: `ef8befef9c155c4874e820599f8c011996ec0a9a`. Итог: 26 файлов, +247 / -681 строк.

## Структурные изменения (L3-L5)

**virtual-memory split на 4 файла в новой подпапке** `linux/foundations/virtual-memory/`:
- `virtual-memory.md` (overview, 1031w) — 3 проблемы → механизм целиком → навигация
- `translation.md` (2683w) — страницы, page table, MMU, CR3, адресное пространство
- `tlb.md` (1558w) — TLB как кеш, PCID, TLB shootdown
- `page-faults.md` (2835w) — page fault, demand paging, CoW, overcommit
Старый `virtual-memory.md` удалён. +2 самопроверки в page-faults.md.

**cpu-modes stdio relocate** в `linux/programming/file-io.md`:
- Удалены «Буферизация» + 3 режима stdio + `<details>` tail -f | grep.
- В cpu-modes оставлен мостик-указатель.
- В file-io добавлена секция «Буферизация stdio» + `<details>` + правильные BUFSIZ.

**Compress хвостов**:
- `threads` — M:N/GMP/горутины: 28 строк → 6-строчный абзац.
- `scheduler` — RT-политики (25+11) / NUMA+affinity (28) / perf sched (19) → 6+5+3 строки.
- `filesystems` — ext4 vs XFS удалено; адресация блоков 35 → 3 абзаца с extent первым; journal modes → `<details>`.

## L1-L2 механика (main agent + writer-cpu)

- **Slug-form якоря → точный текст заголовка** в wikilinks: processes ×3, threads ×4, cpu-modes ×3, scheduler ×6, virtual-memory/* new, permissions ×2. Всего ~20 правок.
- **Markdown с якорем → wikilink** (§6.3): processes:259 demонизации, filesystems:187 minor page fault.
- **Самореферентные обороты §0.2**: processes ×2, virtual-memory split удалил оригинал, filesystems ×1, scheduler ×1, permissions ×3.
- **Factcheck L1**:
  - virtual-memory/page-faults Redis BGSAVE 10 ГБ: 100 мкс → ~1 мс (арифметика).
  - permissions: 3 → 5 наборов capabilities (+ Bounding как ключ Docker / + Ambient Linux 4.3 как механизм передачи в не-setcap бинарники).
- **Factcheck L2**:
  - cpu-modes: ~340 syscalls → «более 450»; vvar тик 1-10 мс; musl BUFSIZ 1024.
  - processes: pid_max атрибуция (PID_MAX_LIMIT ядра, не systemd выбор).
  - threads: autogroup упомянут в контексте 10-потоков-vs-cgroups.
  - scheduler: sched_min_granularity 0.75 мс mainline default.
  - filesystems: half-MD4 — «MD4 с меньшим числом раундов» (не «усечённый для коротких строк»).
- **Forward-references → inline-глоссы**: TLB в cpu-modes убран (оставлено «промахи кешей»), CoW в processes сжат до 1 абзаца с wikilink на page-faults.
- **V-shape cross-links вниз** добавлены: регистры CPU → `computer/programmer-model/isa.md` (processes, threads); System V AMD64 ABI → `abi-and-data-layout.md` (cpu-modes); pipeline flush → `out-of-order-execution.md`; SIMD → `simd.md` (scheduler); latency pyramid → `memory-hierarchy.md` (cpu-modes).
- **Naive-model рычаги во входе**: processes (fork как не-старт-с-нуля), threads («поток = лёгкий процесс» наполовину правда), scheduler («CPU поровну» контрпример), permissions («root / обычный мало»), file-descriptors (`<details>` shared offset — prediction-style).
- **`<details>` самопроверки** добавлены: threads (counter++), file-descriptors (shared offset), virtual-memory/page-faults (malloc(1 GB) + CoW exit).
- **«Вернёмся к веб-серверу»**: 3× в threads разнообразлены.
- **«См. также»**: processes получил секцию (Redis BGSAVE, PostgreSQL per-connection, Ruby/Unicorn preforking).
- **Permissions мостик**: был «scheduler не проверяет права», стал явный pivot «основная линия закрылась, параллельно ядро решает другой вопрос».

## Каскадные обновления путей

Обновлено через `perl -i -pe` по 13+ файлам (все ссылки с якорями `virtual-memory#X` → `virtual-memory/<subfile>#X`):

- `linux/foundations/*.md` (processes, threads, scheduler, filesystems, file-descriptors, what-is-os, permissions) — якоря + prev/next + markdown-path updates
- `linux/concurrency/lock-free.md` — page fault link
- `linux/programming/*.md` (memory-mapping, memory-management, signals, ipc, file-io) — V-shape/path updates
- `linux/infrastructure/*.md` (boot, elf-and-linking) — MMU/page-table/demand-paging links
- `linux/kernel/memory-management.md` — 4 якоря на virtual-memory subfiles
- `linux/containers/namespaces-and-cgroups.md` — memory references
- `computer/data-path/*.md` (cache-internals, buses-and-dma) — TLB и Виртуальные адреса upward-ссылки
- `ruby/internal/*.md` (concurrency, gc) — подхвачены perl'ом

Обновлён `linux/linux.md`: «Порядок изучения → Ядро курса» получил расширение virtual-memory как подсерию из 4 пунктов.

## Layer-gaps (5 концепций добавлены в `wip/layer-gaps.md`)

- **red-black-tree** (algorithms/non-linear) — CFS/EEVDF runqueue + VMA lookup, 2 потребителя в foundations = §9 порог сработал.
- **spectre-meltdown-mitigations** (linux/kernel) — детали KPTI/IBRS/retpoline, расчёт стоимости syscall.
- **autogroup-scheduler** — дефолт 2.6.38+ ломает «N потоков = N x CPU».
- **no-new-privs-sandbox** — закрывает vuln-path в sandbox-модели permissions.
- **cgroup-v2** — современный дефолт, containers/scheduler опираются без явной заметки.

## Не тронуто

- `what-is-os.md` — одна минорная правка (добавлена inline-гласса для «драйверы» в диаграмме ядра). По линзам корректен.
- `linux.canvas` — не обновлён под split (Obsidian-канвас, можно перерисовать вручную; но статус canvas отражает логику до split, не критично).

## Что осталось для будущих раундов

- Создание заметок из layer-gaps (red-black-tree первая в очереди по приоритету).
- Canvas `linux.canvas` в foundations block отражает старую структуру (один узел virtual-memory) — обновить под подпапку.
- Фаза 7 (Codex styleguide + factcheck на diff) — опциональна, не запущена.
