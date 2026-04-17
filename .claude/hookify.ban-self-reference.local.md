---
name: ban-self-reference
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design|foundations|wip)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: (?i)[Вв] этой части мы прошли|[Сс]ледующий кусок пазла|[Дд]альше пройдём по структуре|[Вв] этом разделе мы рассмотрели|[Пп]одведём итог этой части|[Мм]ы (разобрали(?:сь)?|научились|поняли|узнали)|[Вв]ыше мы (дали|разобрали|обсудили|показали)
---

Самореференциальный комментарий о структуре документа. Тест из §0.1: сказуемое говорит о предмете или о тексте? Если о тексте — перефразируй так, чтобы фраза говорила о теме.
