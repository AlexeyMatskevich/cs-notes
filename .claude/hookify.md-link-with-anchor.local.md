---
name: md-link-with-anchor
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design|foundations)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: \[[^\]]+\]\([^)]*\.md#[^)]+\)
---

Markdown-ссылка с якорем. В этом репо такие ссылки обязаны быть wikilink'ами, потому что парсеры markdown ломаются на якорях с пробелами, двоеточиями и кириллицей. Используй формат `[[path/to/file#Точный текст заголовка|видимый текст]]`. Якорь — ровно то, что стоит после `##`/`###` в целевом файле (оригинальный регистр, пробелы, двоеточия, скобки), не slug. См. structure-guide.md §6.3 и §6.5.
