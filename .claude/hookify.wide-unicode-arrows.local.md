---
name: wide-unicode-arrows
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.md$
  - field: new_text
    operator: regex_match
    pattern: ▼|▲|►|◄|▶
---

Широкие Unicode-стрелки (▼▲►◄▶) рендерятся шире стандартного моноширинного символа и ломают выравнивание ASCII-диаграмм. Используй ASCII: v, ^, >, <. Стандартные стрелки →←↑↓ допустимы в прозе, но не внутри box-drawing диаграмм. См. CLAUDE.md Content Rules.
