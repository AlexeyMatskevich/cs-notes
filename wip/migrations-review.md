---
phase: review
status: round-2
topic: Database Migrations
---

# Review: Database Migrations (Round 2 — after 11 adversarial cycles)

## Структурный ревьюер ("structural")

Все 9 пунктов — **PASS**. Интеграция полная, навигация корректна, ссылки двунаправлены, логика существующих заметок не сломана.

## Чеклист-ревьюер ("checklist")

### FAIL (2)
1. **§1 — DDL/DML не раскрыты.** Аббревиатуры используются повсюду, нигде не определены.
2. **§1 — термины без определения:** «системный каталог» (00-safe:14,163), volatile/non-volatile используется до определения (00-safe:12, определение на строке 165), «backend-соединение» (index:22), «autocommit-соединение» (01-schema:92).

### CONCERN (2)
1. **§8 — Gate C** в 01-schema требует знания replication, не в предпосылках.
2. **§8 — каскадные обновления** — acid.md и postgresql/index.md не знают о migrations.

## Наивный читатель ("reader")

### Вердикт: CLEAR (0 BLOCKER, 9 CONCERN)

Серия читается хорошо. Дуга логичная. Мотивация закрывается.

### CONCERN (9)
| # | Файл | Строки | Проблема | Severity |
|---|------|--------|----------|----------|
| 1 | 00-safe | 12 (def 165) | volatile/non-volatile: forward reference ~150 строк | High |
| 2 | 00-safe | 14, 163 | «системный каталог» не определён | Medium |
| 3 | index + 00-safe + 01-schema | повсюду | DDL — аббревиатура не раскрыта | Medium |
| 4 | 00-safe + 01-schema | повсюду | DML — аббревиатура не раскрыта | Medium |
| 5 | 00-safe | 82 | VACUUM — ссылка без определения | Low |
| 6 | 00-safe | 258 | replication lag не определён | Low |
| 7 | 00-safe | 283 | expand-contract forward ref | Low |
| 8 | 01-schema | 117-127 | replica/primary за пределами предпосылок | Low |
| 9 | index | 22 | backend-соединение не раскрыт | Low |

### Отмеченные сильные стороны
- Трёхосевая классификация (блокировка × действие × длительность)
- "Мгновенный не значит корректный" (CURRENT_TIMESTAMP)
- Late-commit hazard → tail-sweep
- clock_timestamp() vs now()
- Четырёхчастная классификация DDL
- Nullable без DEFAULT для backfill

## Перекрёстные находки

- checklist → reader: DDL/DML, системный каталог, volatile forward ref, backend-соединение. Reader подтвердил все четыре.
- reader → checklist: VACUUM и replication lag — reader отметил как low concern.

## Codex Adversarial Review (параллельно, cycle 11)
- Type-change rename: всё ещё recurring finding (steps 5-8 backward compat)
- Unique-index recovery: DROP INVALID reopens duplicate race if writes not quiesced

## Сводка
- **BLOCKER: 0**
- **FAIL: 2** (DDL/DML; термины без определения при первом использовании)
- **CONCERN: 9** (deduplicated)
- Критичные: volatile forward ref (00-safe:12), DDL/DML (повсюду), системный каталог (00-safe:14)
