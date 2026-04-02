---
name: ban-cis-location-leak
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (algorithms|computer|databases|linux|messaging|networking|rails|ruby|system-design)/.*\.md$
  - field: new_text
    operator: regex_match
    pattern: (?i)Алмат[ыа]|Казахстан|Росси[ияю]|Москв[аыу]|Минск|Киев[ау]?|Ташкент|Бишкек|Астан[ау]|СНГ|UTC\+[56]|GMT\+[56]
---

Протечка локации автора. Notes используют только классические CS-примеры: города → San Francisco, New York, London, Tokyo. Компании → Amazon, Netflix, Twitter/X, Google. Люди → Alice, Bob, Charlie. Никаких ссылок на автора или его местоположение. См. CLAUDE.md Content Rules.
