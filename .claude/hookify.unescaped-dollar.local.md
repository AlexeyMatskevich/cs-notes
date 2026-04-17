---
name: unescaped-dollar
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design|foundations|wip)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: (?<!\\)\$\d
---

Неэкранированный `$` перед цифрой в прозе. В Quartz включён KaTeX-плагин, и пара `$...$` в прозе интерпретируется как inline-математика — денежные суммы вроде `$5–10 за мегабайт ... $3–5 за гигабайт` ломают рендеринг: текст между двумя `$` превращается в искажённую «формулу». Экранируй как `\$5`, `\$3`. Исключения — `$` внутри fenced code block (```` ``` ````) и inline code (`` ` ``): в них KaTeX не лезет. SQL-параметры `$1`, `$2` и awk-выражения в прозе, обёрнутые в backticks, безопасны. См. structure-guide.md §8.5.
