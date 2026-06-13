# computer/ — очередь границ области (scope queue)

Концепции, которые курс `computer/` **упоминает, но сознательно НЕ объясняет** — они принадлежат другим доменам. Цель файла: сделать границу явной (не «тихая дыра» и не насильное определение внутри computer/). Для каждой — где дом и как computer/ её сейчас держит (cross-link / inline-gloss). Обнаружено при §2-проверке контракта предпосылок (2026-06-13).

## Дома, которые УЖЕ существуют (computer/ корректно линкует вверх по слою — §2 «ссылка вверх как контекст»)

- **Виртуальная / физическая адресация, страница, трансляция, TLB** → [`linux/foundations/virtual-memory.md`](../linux/foundations/virtual-memory.md). Потребители: `cache-internals` (индексация кеша по физ. адресу, TLB), `buses-and-dma` (DMA требует физ. адрес; scatter-gather по физ. страницам), `abi-and-data-layout` (штраф за пересечение границы страницы 4 КБ), `ram` (NUMA first-touch). Держится: якорные cross-link + inline-gloss «устройство работает с физическими адресами».
- **Процессы и потоки, переключение контекста** → [`linux/foundations/processes.md`](../linux/foundations/processes.md), [`linux/foundations/threads.md`](../linux/foundations/threads.md). Потребители: `ram` (NUMA: «данные потока»), `buses-and-dma`, `simd` (поток-параллелизм как контраст SIMD), `atomic-instructions`, `cache-coherency` (поток↔ядро). Держится: inline-gloss «поток исполняется на ядре» + cross-link.
- **Режимы CPU / режим ядра, прерывания ядра** → [`linux/foundations/cpu-modes-and-syscalls.md`](../linux/foundations/cpu-modes-and-syscalls.md), [`linux/kernel/interrupts.md`](../linux/kernel/interrupts.md). Потребители: `buses-and-dma` (MMIO, прерывания, MSI/NMI). Держится: cross-link.
- **Примитивы синхронизации (мьютекс, семафор), модель памяти, lock-free / ABA** → [`linux/concurrency/synchronization.md`](../linux/concurrency/synchronization.md), [`linux/concurrency/memory-ordering.md`](../linux/concurrency/memory-ordering.md), [`linux/concurrency/lock-free.md`](../linux/concurrency/lock-free.md). Потребители: `atomic-instructions` («поверх CAS строятся мьютексы…», ABA), `cache-coherency` (модель памяти, store buffer reordering). Держится: cross-link.
- **Прикладные БД-концепции (селективность, sequential/index scan, `random_page_cost`, WAL, буферный кеш, RAID)** → `databases/postgresql/…`, `system-design/…`. Потребители: `storage`, `flash-internals`. Держится: WAL/planner/buffer-cache — cross-link; RAID/селективность — inline-gloss (дома-ноты RAID в репо нет).

## Домов пока НЕТ (ждут написания — дублируются в [`layer-gaps.md`](layer-gaps.md))

- **Конечный автомат (FSM)** → ожидается `algorithms-and-data-structures/techniques/finite-state-machine.md`. Потребители: `cache-coherency` (MESI как state machine), `atomic-instructions` (состояния линии при CAS/LL-SC). Сейчас рамка FSM в нотах не объясняется; см. запись в `layer-gaps.md`.
- **LSM-tree / log-structured (как БД-приём)** → ожидается в `databases/`. Потребитель: `flash-internals` («FTL похож на log-structured merge tree»). Сейчас держится самодостаточным glossом «вместо обновления на месте — дозапись в конец»; голые имена LSM/WAL — кандидат на cross-link, когда дом появится.

## Действие
Все «дом существует» — закрыты cross-link/gloss, отдельной работы не требуют (это корректная §2-ссылка вверх по слою). «Дома нет» — берутся из `layer-gaps.md` при написании соответствующих нот; до тех пор computer/ держит их inline-glossом, не определяя.
