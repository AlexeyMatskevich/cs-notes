# Утверждённый план переработки — linux/foundations/

Baseline SHA: `ef8befef9c155c4874e820599f8c011996ec0a9a` (см. `baseline.ref`).

## Ответы пользователя на чекпоинте

1. **virtual-memory**: split на 3 файла (Root cause 1, стратегия A+variant — как у editor).
2. **permissions**: «делай как лучше». Решение: **B** (оставить в конце foundations, переписать мостик с scheduler в явный pivot «основная линия закрылась, параллельно ядро решает другой вопрос — кто имеет право»). Это дешевле каскада, сохраняет связку scheduler→permissions→containers, соответствует текущему `linux.md` «Порядок изучения».
3. **layer-gaps**: добавить все 4 (IBRS, autogroup, PR_SET_NO_NEW_PRIVS, cgroup v2) + red-black-tree от editor'а. В `wip/layer-gaps.md` как append-only журнал кандидатов.

## Что меняется

### L3-L5 structural (writer teammates)

**virtual-memory split** — L5, главная работа.
- Три заметки в новой подпапке `linux/foundations/virtual-memory/`:
  - `virtual-memory.md` (overview + общая концепция трансляции: 3 проблемы → виртуальные адреса → механизм целиком → краткая навигация по трём файлам)
  - `translation.md` — страницы, page table (PGD/PUD/PMD/PTE), MMU, CR3, address space layout (Text/Data/BSS/Heap/mmap/Stack)
  - `page-faults.md` — page fault (minor/major/illegal), demand paging, CoW, overcommit
  - `tlb.md` — TLB, PCID, TLB shootdown, IPI
- Обновить `linux.md` «Порядок изучения».
- Cascade: cross-links на `virtual-memory#X` во всех файлах репо (≥ 20 ссылок в postgresql/, redis/, ruby/internal/, linux/, computer/).

**cpu-modes-and-syscalls stdio relocate** — L3.
- Удалить из `cpu-modes-and-syscalls.md` разделы «Буферизация» и «Три режима буферизации stdio» и «Буферизация при чтении».
- Оставить один абзац-указатель «стоимость syscall делает буферизацию ключевой оптимизацией».
- Перенести содержимое в `linux/programming/file-io.md` (проверить, нет ли уже аналогичного материала — он **мог уже быть** в этой заметке).

### L2 compress (writer teammates)

**threads хвост** — M:N/N:1/горутины GMP → 1 абзац «1:1 упирается в стеки ядра; альтернатива — user-space потоки, см. Go/Ruby Fiber».
**scheduler хвост** — RT-политики, NUMA/affinity, perf sched → по 3-5 строк каждая с cross-link.
**filesystems ext4-specifics** — compress (не split): extent-деревья получают основное место (вытесняют классическую схему ext2/3 до минимума), три режима журналирования и ext4 vs XFS → коротко в `<details>` или удаляются.

### L1-L2 mechanical (main agent, один проход по всем 9 файлам)

Один agent проход по каждому файлу применяет все L1-L2 правки одновременно:

- **Slug-form якоря** (Root 2) — в `cpu-modes:52, 101×2`, `processes:35, 89, 259`, `threads:26, 30, 42, 89`, `file-descriptors:95, 235`, `virtual-memory:90, 141, 174` (до split), `filesystems:25`, `scheduler:37, 41, 45×3, 91`, `permissions:25, 226` + `processes:259` wikilink conversion (§6.3).
- **«Мы видели/создали/разобрали»** (Root 3) — `processes:150, 279`; `virtual-memory:25, 206, 326` (до split); `filesystems:321`; `scheduler:20-21`; `permissions:25, 46, 292`.
- **Factcheck L1** (Root 4) — `virtual-memory:234` Redis 10ГБ → 1 мс (правится до split); `permissions:178-184` 3 → 5 наборов capabilities (+ Bounding + Ambient).
- **Factcheck L2** — `cpu-modes:72` ~340→«более 450»; `cpu-modes:163` musl BUFSIZ 1024; `cpu-modes:119` vvar 1-10 мс; `processes:220` pid_max atribution; `threads:109` autogroup; `scheduler:142` sched_min_granularity 0.75 мс.
- **Forward-references inline-глоссы** (Root 5) — TLB в cpu-modes:101 (либо убрать, либо glossa), VMA position в virtual-memory:186.
- **CoW в processes сжать до functional gloss** (Root 5) — 1-2 предложения + wikilink на virtual-memory.
- **Naive-model рычаги** (Root 6) — 1-2 фразы во входе `processes`, `file-descriptors`, `filesystems`, `scheduler`, `permissions`, `threads`.
- **`<details>`-задачи самопроверки** (Root 7) — threads (counter++), file-descriptors (shared offset), virtual-memory (2 задачи: malloc(1GB) + CoW exit).
- **V-shape cross-links** (Root 8) — при первом содержательном использовании: регистры `rax/rsp/rbp/rip` → `computer/programmer-model/isa.md`; System V AMD64 ABI → `abi-and-data-layout.md`; SIMD → `simd.md`; pipeline flush → `computer/cpu/out-of-order-execution.md`; TLB↔cache → `computer/data-path/cache-internals.md`; latency pyramid в cpu-modes → `computer/data-path/memory-hierarchy.md`.
- **Upward motivation** — в `processes` добавить `См. также` (Redis BGSAVE, PostgreSQL per-connection, Unicorn/Puma preforking).
- **Permissions мостик** (Root 9 + B) — переписать переход с scheduler на явный pivot «основная линия закрылась, параллельно ядро решает другой вопрос».

## Владение работой

**Writer teammates (L3+, параллельно в worktree):**
- `writer-vm` — virtual-memory split на 4 файла (overview + 3 части) в новой подпапке.
- `writer-cpu` — cpu-modes stdio relocate + compress threads/scheduler/filesystems хвостов.

**Main agent (L1-L2 + каскад):**
- Проход по 7 «лёгким» файлам (what-is-os, processes, threads, file-descriptors, filesystems, scheduler, permissions). threads/scheduler/filesystems получают только L1-L2 механику; compress хвостов — у writer-cpu.
- После writer-teammates: каскадные обновления (`linux.md` Порядок изучения, prev/next, cross-links на virtual-memory#X во всех 20+ файлах), запись в `wip/layer-gaps.md`.

## Порядок

1. Главный agent создаёт `wip/layer-gaps.md` (независимо от фаз).
2. TeamDelete старой команды `linux-rework`, TeamCreate `linux-rework-v2`.
3. Запуск `writer-vm` + `writer-cpu` параллельно фоном.
4. Main agent идёт по 7 «лёгким» файлам в foreground (L1-L2 механика).
5. Writer teammates финишируют → main agent обновляет каскад.
6. Фаза 5: верификация (naive reader на изменённых файлах + regression).
