---
tags:
  - domain/networking
  - theme/networking
  - type/overview
aliases:
  - Computer Networks
  - Networking
order: 0
---

# Компьютерные сети

**Предпосылки:** общая компьютерная грамотность (файл, программа, оперативная память).

Компьютерные сети — инфраструктура, на которой работает всё остальное: базы данных с репликацией, распределённые системы, веб-приложения, [[networking/infrastructure/cdn|CDN]], брокеры сообщений. Заметки организованы снизу вверх: от передачи битов по проводу до [[networking/application/http|HTTP]]-запросов и инфраструктуры интернета.

## Порядок изучения

Зависимости идут строго снизу вверх: foundations → transport → application → infrastructure. Внутри каждой группы файлы пронумерованы по зависимостям.

### Foundations

Физический, канальный и сетевой уровни: как данные передаются между устройствами и сетями.

- [[networking/foundations/ethernet-and-switching|Ethernet и коммутация]] — биты, сигналы, MAC-адреса, кадры, коммутаторы
- [[networking/foundations/ip-and-routing|IP и маршрутизация]] — IP-адреса, подсети, роутеры, ARP, путь пакета
- [[networking/foundations/dhcp|DHCP]] — автоматическая выдача сетевых параметров (DORA, lease, relay)
- [[networking/foundations/nat|NAT]] — трансляция адресов (SNAT, DNAT, PAT, CGNAT, port forwarding)
- [[networking/foundations/ipv6|IPv6]] — новое адресное пространство, SLAAC, dual-stack

### Transport

Транспортный уровень: доставка данных между приложениями.

- [[networking/transport/udp|UDP]] — порты, сокеты, датаграммы, когда надёжность не нужна
- [[networking/transport/tcp|TCP]] — соединение, handshake, seq/ack, окно, congestion control
- [[networking/transport/tcp-tuning|TCP Tuning]] — Nagle, TCP_NODELAY, keep-alive, socket buffers, backlog

### Application

Прикладной уровень: протоколы, которые используют приложения.

- [[networking/application/dns|DNS]] — иерархия доменов, резолвинг, кэширование, типы записей
- [[networking/application/http|HTTP]] — запрос-ответ, методы, коды статуса, заголовки, cookies
- [[networking/application/tls|TLS]] — шифрование, сертификаты, TLS-рукопожатие
- [[networking/application/http-evolution|Эволюция HTTP]] — HTTP/1.0 → 1.1 → 2 → 3/QUIC
- [[networking/application/websockets|WebSocket]] — upgrade, full-duplex, фреймы, heartbeat

### Infrastructure

Модели, протоколы маршрутизации и инфраструктурные технологии.

- [[networking/infrastructure/reference-models|Эталонные модели: OSI и TCP/IP]] — уровни, инкапсуляция, PDU, принципы (песочные часы, end-to-end)
- [[networking/infrastructure/routing-protocols|Протоколы маршрутизации]] — AS, OSPF, BGP, path selection
- [[networking/infrastructure/firewalls|Firewalls]] — packet filter, stateful, зоны, DMZ
- [[networking/infrastructure/vpn|VPN]] — туннелирование, IPSec, WireGuard, split tunneling
- [[networking/infrastructure/cdn|CDN]] — edge-серверы, DNS-маршрутизация, инвалидация кэша

## Полный путь: от URL до страницы

Пользователь вводит `https://www.example.com/page` в браузер:

1. **Парсинг URL** — протокол (https), хост (www.example.com), путь (/page)
2. **[[networking/application/dns|DNS]]** — www.example.com → IP-адрес (возможно через [[networking/infrastructure/cdn|CDN]])
3. **[[networking/transport/tcp|TCP]]** — трёхстороннее рукопожатие с сервером
4. **[[networking/application/tls|TLS]]** — рукопожатие, установка шифрования
5. **[[networking/application/http|HTTP]]-запрос** — `GET /page` через зашифрованное соединение
6. **Обработка на сервере** — роутинг, бизнес-логика, база данных
7. **[[networking/application/http|HTTP]]-ответ** — HTML-страница
8. **Рендеринг** — парсинг HTML, загрузка CSS/JS/изображений (параллельные запросы), отрисовка

На каждом шаге работает свой уровень стека: [[networking/application/dns|DNS]] использует [[networking/transport/udp|UDP]], [[networking/transport/tcp|TCP]] обеспечивает надёжность, [[networking/application/tls|TLS]] — шифрование, [[networking/application/http|HTTP]] — семантику запроса. Пакеты инкапсулируются при отправке и декапсулируются при получении.

## Как всё связано

**Надёжность vs скорость.** [[networking/transport/tcp|TCP]] гарантирует доставку ценой задержек (handshake, retransmission, congestion control). [[networking/transport/udp|UDP]] жертвует надёжностью ради скорости. HTTP/3 (QUIC) — попытка получить надёжность [[networking/transport/tcp|TCP]] без его проблем (HOL blocking), работая поверх [[networking/transport/udp|UDP]].

**Безопасность vs латентность.** [[networking/application/tls|TLS]] добавляет RTT на рукопожатие. TLS 1.3 снижает это до 1 RTT, 0-RTT при повторном подключении. [[networking/infrastructure/vpn|VPN]] добавляет ещё один уровень шифрования и маршрутизации.

**Централизация vs распределённость.** [[networking/application/dns|DNS]] — иерархическая распределённая система. [[networking/infrastructure/cdn|CDN]] — распределённый кэш. BGP — децентрализованный обмен маршрутами. Каждый решает проблему масштаба по-своему.

## Карта знаний

```
УРОВЕНЬ          OSI              TCP/IP          КЛЮЧЕВЫЕ ПОНЯТИЯ
----------------------------------------------------------------------
7. Application   +                               DNS, HTTP, HTTPS,
6. Presentation  +-- Application  Application    REST, TLS, cookies,
5. Session       +                               WebSocket

4. Transport     --- Transport    Transport      TCP, UDP, порты,
                                                 сокеты, handshake,
                                                 ACK, окно, congestion

3. Network       --- Network      Internet       IP, маска, роутеры,
                                                 ARP, TTL, NAT, DHCP

2. Data Link     +                               MAC-адреса, кадры,
                 +-- Data Link    Network        Ethernet, коммутаторы,
1. Physical      +                Interface      биты, сигналы
```

## См. также

- [Load Balancing](../system-design/load-balancing.md) — L4/L7 балансировка (использует TCP и HTTP)
- [API Design](../system-design/api-design.md) — REST, GraphQL, gRPC (построены на HTTP)
- [Caching](../system-design/caching.md) — CDN как уровень кэширования
- [Reliability Patterns](../system-design/reliability-patterns.md) — timeout, retry на уровне сети
