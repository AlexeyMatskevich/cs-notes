---
name: ban-metalanguage
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: (?i)нарратив|нить повествования|мостик(?!ов)|послойное раскрытие|граф зависимостей|конечный эффект|сквозной сценарий|обучающая архитектура|нарративный вход|нулевой вход
---

Метатермин из styleguide.md обнаружен в тексте заметки. Эти слова описывают процесс написания, а не предмет. Перефразируй предметным языком — текст должен говорить о теме, а не о том, как она объясняется. См. styleguide.md §0.2.
