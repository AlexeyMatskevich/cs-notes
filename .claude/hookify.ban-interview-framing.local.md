---
name: ban-interview-framing
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: (?i)собеседовани[еяю]|интервью|подготовк[аеи] к интервью|interview prep
---

Запрещено interview/preparation framing. Notes — технический материал, не «подготовка к собеседованию». См. CLAUDE.md Content Rules.
