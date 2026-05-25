# Codex styleguide review (task-mobr2q8s-stuskt, 4m 16s)

**Заметка автора отчёта:** первоначальный diff не включал новые `linux/foundations/virtual-memory/*.md` (они untracked), Codex добавил их в проход явно.

## 5 находок, все L1-L2

1. `linux/foundations/virtual-memory/translation.md:18` — «Обзор дал один виртуальный адрес…» — **§0.2 самореференция** — rewrite L2. Вход через отсылку к предыдущей заметке, не через предметный разрыв.
2. `linux/foundations/virtual-memory/tlb.md:18` — «Предыдущая заметка закончила арифметикой…» — **§0.2** — rewrite L2. Та же утечка: предложение говорит о документе, не о механизме.
3. `linux/foundations/virtual-memory/translation.md:170` — «Проследим трансляцию конкретного адреса.» — **§0.2** — rewrite L1. Инструкция по чтению документа вместо сценария.
4. `linux/foundations/virtual-memory/page-faults.md:143` — «Проследим цепочку вызовов…» — **§0.2** — rewrite L1. Самореферентная формула перед сценарием `malloc → touch → fork → write`.
5. `linux/programming/file-io.md` (LD_PRELOAD в `<details>` про stdbuf) — **§2 Читатель** — compress L1. Термин не в Предпосылках, не работает на локальный результат.

**По §1/§3 остальной проход чист** — результаты заметок и сквозные сценарии держатся.

## Применено

Все 5 правок применены. Новые входы в translation/tlb ссылаются на предмет (виртуальный адрес, трансляция через дерево) вместо метаоборотов про «обзор» и «предыдущую заметку». В translation.md:170 pivot заменён на прямой вопрос-переход к tlb. В page-faults.md:143 «проследим цепочку» → «последовательность malloc → touch → fork → write». LD_PRELOAD убран из stdbuf-решения.
