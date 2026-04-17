---
name: md-link-same-dir-subfolder
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design|foundations|wip)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: \]\([a-z][^:/)]*/[^)]+\.md[^)]*\)
---

Markdown-ссылка в подпапку текущего каталога без `../`-префикса. Quartz-резолвер интерпретирует такой path как абсолютный от vault-root, а не относительный — итоговый URL ведёт в несуществующий маршрут. Используй wikilink с полным vault-путём: `[[computer/data-path/cache-coherency|когерентность кешей]]` вместо `[когерентность кешей](data-path/cache-coherency.md)`. См. structure-guide.md §6.5.
