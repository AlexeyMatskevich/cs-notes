---
name: ban-prompt-leakage
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|programming|rails|ruby|system-design|foundations|wip)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: (?i)[Чч]тобы читателю|[Чч]тобы было проще понять|[Дд]ля лучшего понимания|[Пп]о просьбе|[Кк]ак вы просили|[Вв] этой сессии|[Дд]ля наглядности рассмотрим|[Чч]тобы закрепить понимание
---

Протечка авторского намерения или промпта. Эти фразы объясняют зачем автор что-то написал, а не почему предмет так устроен. Причинность должна быть предметной: «чтобы обеспечить durability, база пишет журнал» (ок) vs «чтобы читателю было проще, дадим оценку» (протечка). См. styleguide.md §0.2.
