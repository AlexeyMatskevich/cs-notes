# Репликация

**Предпосылки:** [Broker, topic, partition, offset](00-what-is-kafka.md) (модель данных Kafka, consumer groups, partition key), [Репликация](../../../system-design/replication.md) (sync/async, replication lag, failover, кворум), [Консенсус](../../../system-design/03-consensus.md) (Raft, leader election, term).

Topic `order_events` разбит на 6 партиций по 3 broker'ам, каждая партиция — единственный экземпляр на диске одного сервера. Broker 0 вышел из строя — партиции 0 и 3 пропали. Producer не может в них писать, consumer'ы не могут из них читать, а все события, которые там хранились, потеряны навсегда. Две из шести партиций — это 33% данных и 33% пропускной способности. Пять consumer groups — seller read DB, Elasticsearch, ClickHouse, рекомендации, fraud detection — недосчитаются заказов, попавших в эти партиции.

Нужны копии. Каждая партиция должна существовать на нескольких broker'ах, чтобы при потере одного сервера данные и доступность сохранялись.

## Единица репликации — партиция, а не broker

В [Redis Sentinel](../../../databases/redis/distribution/01-sentinel.md) реплицируется master целиком: все данные копируются на replica-сервер. В [PostgreSQL](../../../databases/postgresql/distribution/00-replication.md) — аналогично: WAL-поток переносит все изменения primary на standby. Одна реплика = полная копия всего сервера.

Можно было бы устроить так же в Kafka: Broker 0 — master, Broker 1 — его реплика. Но представим, что Broker 0 умирает. Broker 1 принимает на себя все его партиции — и теперь обслуживает свои партиции (1, 4) как leader, и бывшие партиции Broker 0 (0, 3). Один сервер получает 66% всех записей кластера вместо 33%. При трёх broker'ах это ощутимо, при десятках — катастрофа: один выживший принимает нагрузку десяти упавших.

В Kafka единица репликации — **отдельная партиция**. Количество копий задаёт **replication factor** при создании topic'а. Для `order_events` ставим replication factor = 3 — каждая партиция существует в трёх экземплярах (**репликах**). Из трёх реплик одна — **leader** (принимает записи), две — **follower'ы** (копируют данные с leader'а). Leader'ы равномерно распределены по кластеру:

```
                Broker 0         Broker 1         Broker 2
partition 0:    LEADER           follower         follower
partition 1:    follower         LEADER           follower
partition 2:    follower         follower         LEADER
partition 3:    LEADER           follower         follower
partition 4:    follower         LEADER           follower
partition 5:    follower         follower         LEADER
```

Каждый broker — leader для двух партиций и follower для четырёх. Запись равномерна: ~50 events/sec на каждый broker.

Broker 0 умирает. Партиция 0 получает нового leader'а — Broker 1. Партиция 3 — Broker 2. Теперь каждый из двух выживших — leader для трёх партиций: 75 events/sec вместо 50. Нагрузка распределилась поровну, ни один broker не захлебнулся.

Per-partition репликация даёт независимый failover для каждой партиции и равномерное распределение leader'ов после сбоя. Каждый broker одновременно и leader, и follower — простаивающих реплик нет.

## Leader принимает всё: и записи, и чтения

Leader принимает записи от producer'а — но кто обслуживает чтения? В PostgreSQL standby-реплика обслуживает read-запросы (hot standby). В Redis — `READONLY` на реплике. В Kafka follower **не обслуживает чтений** — consumer всегда читает с leader'а.

Причина — в природе данных. Consumer отслеживает позицию в партиции через [offset](00-what-is-kafka.md): «обработал до offset 7, дай с offset 8». Follower может отставать от leader'а — leader записал offset'ы 0–10, а follower скопировал только 0–7. Consumer читает с follower'а, получает записи до 7, коммитит offset = 7. На самом деле leader уже ушёл на 10. Consumer думает, что дочитал до конца, а 3 события пропущены.

Для PostgreSQL hot standby подобное отставание допустимо: SELECT-запрос вернул данные на секунду устаревшие — для отчёта нестрашно. Для Kafka consumer'а, который обрабатывает события строго последовательно и коммитит позицию, видеть неполный лог — это пропущенные события.

К тому же Kafka масштабирует чтение через партиции: нужен больший read throughput — добавь партиций и consumer'ов. Разгружать leader через read replicas не нужно.

С Kafka 2.4 появилось исключение: consumer может читать с follower'а в том же дата-центре (`replica.selector.class`). Цель — сократить cross-datacenter latency при мультирегиональных кластерах. Читать разрешается только с синхронизированных реплик, и видимость ограничена подтверждёнными записями — проблема неполного лога не возникает (как именно это работает, станет ясно после секций про ISR и high watermark). Но базовое правило остаётся: follower'ы существуют для durability, а не для масштабирования чтения.

## Как follower получает данные

Follower'ы существуют для durability — при гибели leader'а один из них займёт его место. Для этого follower должен непрерывно копировать данные с leader'а.

В PostgreSQL реплика получает WAL-поток — физический журнал изменений. В Redis — поток команд после начальной синхронизации через RDB. В обоих случаях механизм отделён от клиентского протокола.

В Kafka follower использует тот же механизм, что и обычный consumer: **fetch-запрос к leader'у с указанием offset'а**. Leader отвечает батчем записей. Follower записывает их в свой локальный лог и сдвигает позицию.

```
Leader (Broker 0, partition 0):
  offset: [0] [1] [2] [3] [4] [5] [6] [7]

Follower на Broker 1:
  offset: [0] [1] [2] [3] [4] [5]          ← fetch(offset=6) → leader
                                              получает [6] [7]
  offset: [0] [1] [2] [3] [4] [5] [6] [7]  ← догнал
```

Один протокол для consumer'ов и для репликации — не нужен отдельный механизм вроде WAL shipping.

## ISR: кто успевает за leader'ом

Follower отправляет fetch-запросы, но может отставать — медленный диск, GC-пауза, сетевая задержка. Kafka отслеживает, какие follower'ы «живы и успевают», через механизм **ISR — In-Sync Replicas** (синхронизированные реплики).

ISR — динамический список реплик партиции, которые «достаточно близко» к leader'у. Порог задаёт параметр `replica.lag.time.max.ms` (по умолчанию 30 секунд): если follower не догнал конец лога leader'а в течение этого интервала, он исключается из ISR. Follower может отправлять fetch-запросы каждую секунду, но если leader получает записи быстрее, чем follower успевает их копировать, — отставание растёт, и через 30 секунд follower вылетает из ISR.

В нормальном состоянии для partition 0 с replication factor = 3:

```
ISR(partition 0) = {Broker 0 (leader), Broker 1, Broker 2}
```

Broker 2 завис — не отправляет fetch-запросы и не догоняет лог. Через 30 секунд leader исключает его:

```
ISR(partition 0) = {Broker 0 (leader), Broker 1}
```

Broker 2 ожил, догнал leader'а по offset'ам — leader автоматически возвращает его в ISR. Всё без ручного вмешательства.

Сам по себе ISR не гарантирует durability — он лишь отслеживает, кто «примерно рядом». Гарантии зависят от того, когда producer считает запись подтверждённой, и от того, какая часть лога считается committed.

## High watermark: граница подтверждённых данных

Kafka разделяет записи на **committed** (подтверждённые) и **uncommitted** через **high watermark** (HW) — offset, до которого **все реплики в ISR** гарантированно имеют данные.

Leader записал offset'ы 0–10, follower A скопировал до 8, follower B — до 10. HW = 8 — минимум среди всех реплик в ISR. Записи на offset'ах 9 и 10 существуют на leader'е и одном follower'е, но ещё не подтверждены — они выше HW.

Consumer'ы видят только записи ниже high watermark. Если leader умрёт, новый leader (любая реплика из ISR) будет иметь все записи, которые consumer уже видел. Записи выше HW — «в процессе репликации», consumer их не получит до тех пор, пока все ISR-реплики не подтвердят.

High watermark — ключ к пониманию того, почему при выборе нового leader'а не нужно сравнивать offset'ы реплик (как это делает [Redis Sentinel](../../../databases/redis/distribution/01-sentinel.md), выбирая реплику с наибольшим replication offset). При `acks=all` producer получает подтверждение только после того, как все ISR-реплики записали событие — HW продвинулся. Всё, что ниже HW, одинаково на всех репликах в ISR — любая годится в leader'ы.

## acks: выбор producer'а

Follower'ы копируют данные с leader'а, ISR отслеживает, кто успевает, high watermark отмечает границу подтверждённого. Но когда producer может считать запись «надёжно сохранённой»? Ответ зависит от параметра **acks** (acknowledgments).

В отличие от [PostgreSQL](../../../databases/postgresql/distribution/00-replication.md), где режим репликации (синхронная/асинхронная) — в первую очередь настройка сервера (хотя `synchronous_commit` можно менять и на уровне отдельной транзакции), в Kafka гарантию durability выбирает **каждый producer для себя**.

### acks=0

Producer не ждёт никакого подтверждения — отправил по сети и пошёл дальше. Broker мог быть мёртв, сеть потеряла пакет — producer не узнает. Максимальный throughput, нулевые гарантии. Для потока метрик (CPU usage каждую секунду) допустимо: потеря одной точки из тысячи незаметна. Для `order_events` — неприемлемо.

### acks=1

Producer ждёт подтверждения от leader'а. Leader записал событие в свой локальный лог — ответил «ok». Follower'ы ещё не получили это событие.

```
Producer ──event──> Leader (Broker 0)
                    │ записал в лог
                    │ <── "ok" ──> Producer доволен
                    │
                    ├──fetch──> Follower (Broker 1)  ← ещё не получил
                    └──fetch──> Follower (Broker 2)  ← ещё не получил
```

Leader подтвердил, через 200ms Broker 0 умирает. Follower'ы не успели скопировать последнее событие. Новый leader выбирается из follower'ов — событие потеряно. Тот же сценарий, что при [асинхронной репликации в Redis](../../../databases/redis/distribution/01-sentinel.md): master подтвердил, упал до репликации.

При `acks=1` follower'ы в ISR могут отставать — ISR означает лишь «догнал конец лога leader'а в последние 30 секунд», а не «имеет абсолютно все данные leader'а прямо сейчас». Записи выше high watermark существуют только на leader'е и при его гибели теряются без возможности восстановления.

### acks=all

Producer ждёт, пока leader получит подтверждение от **всех реплик в ISR**. Leader записал к себе, дождался, пока follower'ы тоже записали, и только тогда ответил «ok».

```
Producer ──event──> Leader (Broker 0)
                    │ записал в лог
                    ├──fetch──> Follower (Broker 1) ── записал ── ok
                    ├──fetch──> Follower (Broker 2) ── записал ── ok
                    │
                    │ все ISR-реплики подтвердили
                    │ <── "ok" ──> Producer доволен
```

Broker 0 умирает — оба follower'а уже имеют событие. Потеря данных исключена. Аналог [синхронной репликации в PostgreSQL](../../../databases/postgresql/distribution/00-replication.md), где standby записывает в WAL до того, как primary ответит клиенту.

Цена — latency. При `acks=1` producer ждёт подтверждения от leader'а — сетевой round-trip (~1–5 ms). При `acks=all` — round-trip до leader'а + время на fetch каждого follower'а + подтверждение обратно, порядка десятков миллисекунд. Kafka записывает в page cache операционной системы, а не напрямую на диск — фактический flush на диск происходит асинхронно средствами ОС. Durability при этом обеспечивается репликацией: данные в page cache на трёх независимых серверах.

Для `order_events` с платёжными событиями — `acks=all`. Для потока кликов аналитики — можно `acks=1`.

### acks=all ждёт ISR, а не все реплики

Ключевой момент: `acks=all` означает «все реплики **в ISR**», а не «все реплики вообще». Один из follower'ов завис — GC-пауза, деградация диска. Если бы `acks=all` ждал абсолютно всех, один зависший follower парализовал бы запись во всю партицию. Хуже: этот follower — часть broker'а, который является follower'ом для множества партиций, так что зависание одного broker'а блокировало бы запись по всему кластеру.

ISR решает это: зависший follower исключается из ISR через `replica.lag.time.max.ms`, после чего `acks=all` ждёт подтверждения только от оставшихся. Запись продолжается без задержек.

## min.insync.replicas: порог безопасности

ISR может сжиматься. Один follower вылетел — ISR = 2, запись работает. Второй follower вылетел — ISR = 1 (только leader). `acks=all` теперь означает «подтверждение только от leader'а» — фактически то же, что `acks=1`. Данные существуют в одном экземпляре, durability потеряна.

Параметр **`min.insync.replicas`** запрещает запись, если ISR слишком мал. При `min.insync.replicas=2`:

```
ISR = {Broker 0, Broker 1, Broker 2}  → запись работает, acks=all ждёт троих
ISR = {Broker 0, Broker 1}            → запись работает, acks=all ждёт двоих
ISR = {Broker 0}                      → NotEnoughReplicasException, запись отклонена
```

Producer получает ошибку. Orders-сервис не может опубликовать событие. Это больно — но альтернатива хуже: принять событие в единственную копию, потерять при сбое Broker 0 и никогда не узнать об этом. Ошибку producer может обработать — показать пользователю «попробуйте позже», положить в локальную очередь для retry. Тихую потерю данных обработать невозможно.

Явный trade-off: availability (продолжать принимать записи) vs durability (гарантировать, что данные на нескольких серверах).

Стандартная production-конфигурация для критичных данных:

```
replication.factor = 3
min.insync.replicas = 2
acks = all
```

Три параметра работают вместе. `replication.factor=3` — три копии каждой партиции. `acks=all` — producer ждёт подтверждения от всех ISR-реплик. `min.insync.replicas=2` — в ISR должно быть минимум 2, иначе запись отклоняется. Система переживает потерю одного broker'а без потери данных и без остановки записи. Потеря двух из трёх — запись останавливается, но данные не теряются.

## Controller и выбор leader'а партиции

ISR сжался, leader умер — кто назначит нового? В кластере один из broker'ов выполняет роль **controller'а** — он отслеживает живых broker'ов, хранит метаданные об ISR и назначает leader'ов для партиций.

Partition leader election не требует [консенсуса](../../../system-design/03-consensus.md) между broker'ами. Controller просто берёт **первую живую реплику из ISR** и назначает её leader'ом. Одно решение одного узла, без голосования.

```
До отказа:
  partition 0: ISR = {Broker 0 (leader), Broker 1, Broker 2}
  partition 3: ISR = {Broker 0 (leader), Broker 2, Broker 1}

Broker 0 умер. Controller решает:
  partition 0: leader = Broker 1 (первый живой в ISR)
  partition 3: leader = Broker 2 (первый живой в ISR)
```

Почему не нужно сравнивать offset'ы реплик, как в [Redis Sentinel](../../../databases/redis/distribution/01-sentinel.md)? При `acks=all` все реплики в ISR имеют данные до high watermark — любая годится. При `acks=1` записи выше HW всё равно будут потеряны — сравнивать нечего.

Выбор leader'а партиции — простая операция, потому что ISR уже содержит ответ. Но выбор самого controller'а — другое дело.

### Controller election: ZooKeeper и KRaft

Исторически Kafka делегировала выбор controller'а **ZooKeeper** — отдельному кластеру из 3–5 серверов, реализующему протокол ZAB (решает ту же задачу, что и [Raft](../../../system-design/03-consensus.md), — distributed consensus). ZooKeeper хранил метаданные: живые broker'ы, ISR, конфигурации topic'ов. Controller — broker, который первым создал ephemeral node (временный узел, исчезающий при отключении broker'а) в ZooKeeper.

Проблема: ZooKeeper — отдельная инфраструктура, которую нужно деплоить, мониторить, обновлять. Для маленького кластера — overhead, для большого — bottleneck: все метаданные проходят через внешний сервис.

KRaft появился в Kafka 2.8 (2021) как ранний доступ и стал production-ready в версии 3.3 (2022). Controller'ы — выделенные broker'ы, которые выбирают leader'а **между собой по протоколу [Raft](../../../system-design/03-consensus.md)**: term'ы, голосование большинства, randomized election timeout. Метаданные хранятся в internal topic `__cluster_metadata`, реплицируемом по Raft. Внешних зависимостей нет.

Итого два уровня leader election в Kafka:

```
Controller election:       Raft (голосование, кворум, term'ы)
Partition leader election: Controller назначает из ISR (без голосования)
```

## Unclean leader election: крайний случай

Штатный failover: leader умер, controller выбирает нового из ISR. Но бывает, что ISR пуст — leader упал, а все follower'ы были исключены из ISR ранее из-за отставания. Ни одна реплика не имеет полных данных. Партиция полностью недоступна.

Параметр `unclean.leader.election.enable` (по умолчанию `false` с Kafka 0.11.0) определяет, что делать. Если `true` — controller назначит leader'ом follower'а **вне ISR**, заведомо отставшего. Часть событий потеряна, но партиция снова принимает записи.

Когда старый leader вернётся, он обнаружит, что его записи (выше high watermark нового leader'а) конфликтуют с новой историей. Kafka решает это жёстко: старый leader **обрезает (truncate) свой лог** до HW нового leader'а и начинает реплицировать с него как обычный follower. Никакого merge, никакого разрешения конфликтов — новый leader является единственным источником истины.

```
Старый leader: [0] [1] [2] [3] [4] [5]  ← 4 и 5 потеряны навсегда
Новый leader:  [0] [1] [2] [3]

Старый leader вернулся:
  Обрезал лог до [0] [1] [2] [3]
  Продолжил fetch с нового leader'а
```

Truncation происходит не только при unclean election. При `acks=1` leader может подтвердить запись producer'у, но умереть до того, как follower'ы успеют её скопировать. Новый leader выбирается из ISR штатно (clean election), но его лог заканчивается раньше. Когда старый leader вернётся как follower, он обрежет свои записи выше HW нового leader'а — та же механика truncation.

Для `order_events` — `unclean.leader.election.enable=false`. Лучше временно не принимать заказы, чем потерять платёжные события и не знать об этом.

## Деградация broker'а: ISR ≠ leader election

Broker 2 не умер, но деградирует — диск замедлился. Последствия зависят от роли broker'а в каждой партиции.

Для партиций, где Broker 2 — **follower**: fetch-запросы к leader'ам замедляются, через `replica.lag.time.max.ms` leader исключает эти реплики из ISR. ISR сжимается с 3 до 2. Leader'ы не меняются, producer ничего не замечает — запись идёт через здоровых leader'ов на Broker 0 и Broker 1.

Для партиций, где Broker 2 — **leader**: broker жив, остаётся leader'ом. Follower'ы на здоровых broker'ах успешно делают fetch. ISR не меняется. Но записи замедляются — медленный диск leader'а тормозит producer'ов.

Kafka **не снимает leadership с медленного, но живого broker'а** автоматически. ISR отслеживает только follower'ов: «успевает ли follower догонять лог leader'а». Для leader'а аналогичной метрики нет — пока broker отвечает на heartbeat'ы, controller считает его живым leader'ом.

Это операционная задача. **Preferred replica election** (`auto.leader.rebalance.enable=true`, по умолчанию) возвращает leadership к «предпочтительным» broker'ам после восстановления — но не реагирует на медленных leader'ов. Для ручного вмешательства есть `kafka-reassign-partitions` — администратор явно перемещает leadership, чтобы вывести broker на обслуживание или разгрузить его.

## Sources

- Narkhede, Shapira, Palino, 2017, *Kafka: The Definitive Guide*. O'Reilly
- Kreps, 2013, *The Log: What every software engineer should know about real-time data's unifying abstraction*. <https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying>
- Apache Kafka Documentation. <https://kafka.apache.org/documentation/>
