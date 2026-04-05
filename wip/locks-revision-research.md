---
phase: research
status: draft
topic: Ревизия databases/postgresql/concurrency/03-locks.md
files: []
---

# Ревизия: 03-locks.md

## Проблема

`databases/migrations/00-safe-schema-changes.md` и `01-schema-evolution.md` зависят от `03-locks.md` как предпосылки, но locks-заметка не покрывает концепции, которые миграции активно используют.

## Что миграции используют, а locks не объясняет

### SET как механизм сессии
Миграции строят целую секцию на `SET lock_timeout` / `SET statement_timeout`: взаимодействие между ними, session-scoped поведение, ensure/finally для сброса, отдельное соединение. В locks: одна строка `SET lock_timeout = '5s'` в примере, без объяснения что такое SET, что значит "session-level", как настройка живёт и сбрасывается.

### lock_timeout
Locks: показывает команду и комментарий "не получил lock за 5 секунд — отмена". Не объясняет: что именно ограничивает (только ожидание блокировки, не выполнение), как связан со statement_timeout, что происходит при срабатывании (ошибка, не silent retry).

### statement_timeout
Отсутствует в locks полностью. Миграции объясняют: покрывает общее время (включая ожидание блокировки), должен быть > lock_timeout, антипаттерн `= '0'`. Эти знания строятся на понимании, которого в предпосылке нет.

### SHARE ROW EXCLUSIVE и ROW SHARE
Мы добавили в таблицу table-level locks (строки 70-74), но без объяснения совместимости. Читатель видит "SHARE ROW EXCLUSIVE" в миграциях (FK NOT VALID) и находит его в таблице locks, но не знает с чем он конфликтует. Матрица совместимости в locks покрывает только row-level locks (FOR KEY SHARE → FOR UPDATE), для table-level — нет.

### VALIDATE CONSTRAINT
Добавлен в таблицу (SHARE UPDATE EXCLUSIVE), но поведение "конфликтует с VACUUM и другим DDL" — не объяснено в locks. Миграции полагаются на это знание.

## Что в locks хорошо и трогать не нужно

- Row-level locks: 4 режима, матрица совместимости, FOR UPDATE — хорошо
- Очередь блокировок: T1 SELECT → T2 ALTER TABLE → T3 SELECT — отличный пример
- Advisory locks: session vs transaction scope — достаточно
- Deadlock: пример + решение (порядок обновления) — хорошо
- Автоматические блокировки при записи — хорошо

## Что нужно добавить/расширить

1. **SET и session-level параметры** — что такое SET, session vs transaction scope (SET LOCAL), как сбрасывается (конец сессии, явный SET, закрытие соединения). Это фундамент для lock_timeout/statement_timeout.

2. **lock_timeout** — расширить из одной строки в абзац: что ограничивает, когда срабатывает (только на фазе ожидания), что происходит (ошибка, retry strategy на стороне приложения).

3. **statement_timeout** — добавить: что покрывает (общее время от прихода команды), взаимодействие с lock_timeout (должен быть строго больше), антипаттерн blanket `= '0'`.

4. **Матрица совместимости table-level locks** — сейчас только список "операция → lock". Нужна хотя бы упрощённая матрица или пояснение: "ACCESS EXCLUSIVE конфликтует со всем, SHARE UPDATE EXCLUSIVE конфликтует с собой и выше, ROW EXCLUSIVE совместим с ROW EXCLUSIVE но не с SHARE".

5. **SHARE ROW EXCLUSIVE** — пояснить: конфликтует с ROW EXCLUSIVE (DML), то есть кратковременно блокирует writes. Это критично для понимания FK NOT VALID в миграциях.

## Масштаб изменений

Расширение существующей заметки, не переписывание. Секции "Автоматические блокировки", "Row-level locks", "Advisory locks", "Deadlock" не трогаем. Расширяем секцию "Table-level locks" и добавляем новую секцию "Настройки защиты" (SET, lock_timeout, statement_timeout).

## Каскадные последствия

После расширения locks:
- `00-safe-schema-changes.md` — можно убрать inline-объяснение statement_timeout/lock_timeout interaction (оно будет в предпосылке). Или оставить как applied context — решить при draft.
- `01-schema-evolution.md` — pg_stat_activity.xact_start уже cross-linked
- `index.md` миграций — "session-level SET" станет покрытым предпосылкой

## Связанные файлы

- Предпосылки locks: `00-mvcc.md`, `02-isolation-levels.md`
- Зависят от locks: `04-patterns.md`, `05-common-mistakes.md`, `databases/migrations/*`
