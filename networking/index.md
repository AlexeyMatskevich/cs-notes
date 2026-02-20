# Компьютерные сети

**Предпосылки:** общая компьютерная грамотность (файл, программа, оперативная память).

Компьютерные сети — инфраструктура, на которой работает всё остальное: базы данных с репликацией, распределённые системы, веб-приложения, CDN, брокеры сообщений. Заметки организованы снизу вверх: от передачи битов по проводу до HTTP-запросов и инфраструктуры интернета.

## Порядок изучения

Зависимости идут строго снизу вверх: foundations → transport → application → infrastructure. Внутри каждой группы файлы пронумерованы по зависимостям.

### Foundations

Физический, канальный и сетевой уровни: как данные передаются между устройствами и сетями.

- [Ethernet и коммутация](foundations/00-ethernet-and-switching.md) — биты, сигналы, MAC-адреса, кадры, коммутаторы
- [IP и маршрутизация](foundations/01-ip-and-routing.md) — IP-адреса, подсети, роутеры, ARP, путь пакета
- [DHCP](foundations/02-dhcp.md) — автоматическая выдача сетевых параметров (DORA, lease, relay)
- [NAT](foundations/03-nat.md) — трансляция адресов (SNAT, DNAT, PAT, CGNAT, port forwarding)
- [IPv6](foundations/04-ipv6.md) — новое адресное пространство, SLAAC, dual-stack

### Transport

Транспортный уровень: доставка данных между приложениями.

- [UDP](transport/00-udp.md) — порты, сокеты, датаграммы, когда надёжность не нужна
- [TCP](transport/01-tcp.md) — соединение, handshake, seq/ack, окно, congestion control
- [TCP Tuning](transport/02-tcp-tuning.md) — Nagle, TCP_NODELAY, keep-alive, socket buffers, backlog

### Application

Прикладной уровень: протоколы, которые используют приложения.

- [DNS](application/00-dns.md) — иерархия доменов, резолвинг, кэширование, типы записей
- [HTTP](application/01-http.md) — запрос-ответ, методы, коды статуса, заголовки, cookies
- [TLS](application/02-tls.md) — шифрование, сертификаты, TLS-рукопожатие
- [Эволюция HTTP](application/03-http-evolution.md) — HTTP/1.0 → 1.1 → 2 → 3/QUIC
- [WebSocket](application/04-websockets.md) — upgrade, full-duplex, фреймы, heartbeat

### Infrastructure

Модели, протоколы маршрутизации и инфраструктурные технологии.

- [Эталонные модели: OSI и TCP/IP](infrastructure/00-reference-models.md) — уровни, инкапсуляция, PDU, принципы (песочные часы, end-to-end)
- [Протоколы маршрутизации](infrastructure/01-routing-protocols.md) — AS, OSPF, BGP, path selection
- [Firewalls](infrastructure/02-firewalls.md) — packet filter, stateful, зоны, DMZ
- [VPN](infrastructure/03-vpn.md) — туннелирование, IPSec, WireGuard, split tunneling
- [CDN](infrastructure/04-cdn.md) — edge-серверы, DNS-маршрутизация, инвалидация кэша

## Полный путь: от URL до страницы

Пользователь вводит `https://www.example.com/page` в браузер:

1. **Парсинг URL** — протокол (https), хост (www.example.com), путь (/page)
2. **DNS** — www.example.com → IP-адрес (возможно через CDN)
3. **TCP** — трёхстороннее рукопожатие с сервером
4. **TLS** — рукопожатие, установка шифрования
5. **HTTP-запрос** — `GET /page` через зашифрованное соединение
6. **Обработка на сервере** — роутинг, бизнес-логика, база данных
7. **HTTP-ответ** — HTML-страница
8. **Рендеринг** — парсинг HTML, загрузка CSS/JS/изображений (параллельные запросы), отрисовка

На каждом шаге работает свой уровень стека: DNS использует UDP, TCP обеспечивает надёжность, TLS — шифрование, HTTP — семантику запроса. Пакеты инкапсулируются при отправке и декапсулируются при получении.

## Как всё связано

**Надёжность vs скорость.** TCP гарантирует доставку ценой задержек (handshake, retransmission, congestion control). UDP жертвует надёжностью ради скорости. HTTP/3 (QUIC) — попытка получить надёжность TCP без его проблем (HOL blocking), работая поверх UDP.

**Безопасность vs латентность.** TLS добавляет RTT на рукопожатие. TLS 1.3 снижает это до 1 RTT, 0-RTT при повторном подключении. VPN добавляет ещё один уровень шифрования и маршрутизации.

**Централизация vs распределённость.** DNS — иерархическая распределённая система. CDN — распределённый кэш. BGP — децентрализованный обмен маршрутами. Каждый решает проблему масштаба по-своему.

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

- [Load Balancing](../system-design/05-load-balancing.md) — L4/L7 балансировка (использует TCP и HTTP)
- [API Design](../system-design/11-api-design.md) — REST, GraphQL, gRPC (построены на HTTP)
- [Caching](../system-design/07-caching.md) — CDN как уровень кэширования
- [Reliability Patterns](../system-design/06-reliability-patterns.md) — timeout, retry на уровне сети
