---
tags:
  - domain/programming
  - theme/data-representation
  - type/concept
aliases:
  - functions
  - call stack
  - scope
order: 5
---

# Функции

**Предпосылки:** [Условия и ввод/вывод](conditions-and-io.md) (`&&`, `!=`, `>=`), [Циклы](loops.md) (while, повторение действий).

<- [Циклы](loops.md) | [Коллекции](collections.md) ->

В маркетплейсе одно правило — «можно ли продавцу запросить выплату» — проверяется во многих местах интерфейса: кнопка вывода денег, баннер на панели продавца, сайдбар у финансового менеджера, ночная очередь, отчёт. Правила таких проверок приходят от бизнеса и время от времени меняются: сегодня добавили условие «ручная блокировка тоже останавливает выплату», завтра поднимут минимальную сумму.

Ниже — три фрагмента из одного файла, которые живут в разных углах программы. Каждый решает одну и ту же задачу.

```ruby
# --- Withdraw page button ---
blocked_by_review = review_state == "hold"
enough_money_for_request = available_balance >= requested_amount
button_enabled =
  profile_verified &&
  bank_account_connected &&
  !blocked_by_review &&
  requested_amount >= 50 &&
  enough_money_for_request
```

```ruby
# --- Seller dashboard banner (seller_dashboard.rb) ---
identity_ok = profile_verified
payout_target_ready = bank_linked
min_passed = requested_amount >= 50
balance_ok = available_balance >= requested_amount
banner_visible =
  identity_ok &&
  payout_target_ready &&
  min_passed &&
  balance_ok
```

```ruby
# --- Finance sidebar (finance_controller.rb) ---
hold_cleared = review_status != "hold"
minimum_amount_passed = requested_amount > 50
available_now = available_balance >= requested_amount
sidebar_can_highlight =
  profile_verified &&
  bank_account_connected &&
  hold_cleared &&
  minimum_amount_passed &&
  available_now
```

В этих трёх фрагментах — одно и то же правило выплаты. Записано оно по-разному: разные локальные имена, разный порядок условий, а в двух местах правило уже расходится с оригиналом.

Сейчас блоки лежат рядом, с подсветкой — расхождение ловится за минуту, если заранее знаешь, что оно есть. В реальном коде всё иначе. Фрагменты живут в `seller_dashboard.rb`, `finance_controller.rb`, `withdraw_page.rb` и ещё четырёх файлах, никто не открывает их одновременно. Новое требование от бизнеса приходит как одна строка в тикете: «ручная блокировка теперь останавливает выплату». Обычный первый шаг разработчика — `grep review_state` по репозиторию. Он находит кнопку, но не находит сайдбар: там то же самое поле называется `review_status`. Банковская проверка записана в баннере как `bank_linked`, поиск по `bank_account_connected` туда не приходит. Правишь те места, что нашёл grep, diff выглядит чисто, ревьюер одобряет. Несоответствие всплывёт через квартал — на жалобе клиента или на финансовой сверке. К этому моменту ты уже не помнишь, что трогал эту логику, и будешь искать баг в других местах.

> [!info]- Где именно разошлось
> В `seller dashboard banner` нет проверки ручной блокировки вообще: ни `review_state`, ни `review_status` там не встречаются. Банковская проверка записана как `bank_linked`, а не `bank_account_connected` — поиск по главному имени сюда не попадает.
>
> В `finance sidebar` блокировка проверяется, но поле названо `review_status`, а не `review_state`: синонимы, разные по символам. Плюс минимальная сумма записана как `requested_amount > 50`, а в кнопке — `requested_amount >= 50`. Для суммы ровно 50 кнопка разрешит выплату, а сайдбар её скроет.

Полная версия с семью местами дрейфа — в [examples/05-payout-eligibility-drift.rb](examples/05-payout-eligibility-drift.rb). Файл рабочий, но настоящая боль не в длине: каждая копия правила жила своей жизнью, их писали разные люди в разное время, в разных файлах и с разной локальной лексикой. Поиск по коду рассчитывает, что одна концепция названа одним словом — а здесь не названа.

## Функция: один кусок логики с именем

Когда одна и та же логика нужна в нескольких местах, её выносят в функцию:

```ruby
def can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
  profile_verified &&
    bank_account_connected &&
    review_state != "hold" &&
    requested_amount >= 50 &&
    available_balance >= requested_amount
end
```

`def` (define — «определить») начинает определение функции. `can_request_payout` — имя функции. `profile_verified`, `bank_account_connected`, `review_state`, `requested_amount`, `available_balance` — параметры: входные данные, с которыми она работает.

Теперь вместо трёх копий формулы в разных углах программы остаются три вызова:

```ruby
button_enabled      = can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
banner_visible      = can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
sidebar_can_highlight = can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
```

Если правило изменится — «ручная блокировка теперь тоже останавливает выплату» — править нужно одну функцию. Теперь `grep can_request_payout` находит одно определение и все вызовы. Ревьюер смотрит не на семь открытых файлов для сверки, а на один diff. Новый разработчик через год увидит одну `can_request_payout` и не узнает, что раньше правило расползалось по семи местам под разными именами — расползаться больше нечему, искать больше не нужно.

Пять параметров в заголовке подряд — уже ощутимо, и с каждым новым условием правила станет хуже. Когда параметров становится много, их собирают в один объект с именованными полями; это разбирается в [коллекциях](collections.md).

Функция — не специальный приём Ruby. Та же идея есть в разных языках: дать куску логики имя, передать входные данные и получить результат обратно.

```text
Ruby:       def greeting(name) ... end
JavaScript: function greeting(name) { ... }
Go:         func greeting(name string) string { ... }
```

Синтаксис меняется, но смысл один и тот же: функция собирает шаги в один повторно используемый блок.

## Параметры и результат

Функция получает значения через параметры и возвращает результат:

```ruby
def can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
  profile_verified &&
    bank_account_connected &&
    review_state != "hold" &&
    requested_amount >= 50 &&
    available_balance >= requested_amount
end

seller_review_state = "clear"
result = can_request_payout(true, true, seller_review_state, 120, 300)
puts result    # true
```

При вызове `can_request_payout(true, true, "clear", 120, 300)` первое `true` попадает в `profile_verified`, второе `true` — в `bank_account_connected`, строка `"clear"` — в `review_state`, `120` — в `requested_amount`, `300` — в `available_balance`. Последнее вычисленное выражение становится результатом функции.

Функция может возвращать и не логическое значение, а, например, строку:

```ruby
def greeting(name)
  "Hello, " + name
end
```

В Ruby результатом часто становится последнее вычисленное выражение. Во многих других языках результат возвращают явно через `return`, а иногда ещё и указывают его тип в заголовке функции. Но во всех случаях вопрос один и тот же: какие данные функция получает и что она обещает вернуть назад.

## Вызовы и стек

[Стек](memory.md) (stack — «стопка»: последний положенный элемент снимается первым) подробно устроен в заметке о памяти, но главная идея нужна уже сейчас.

Функции могут вызывать другие функции:

```ruby
def enough_balance(requested_amount, available_balance)
  available_balance >= requested_amount
end

def can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
  profile_verified &&
    bank_account_connected &&
    review_state != "hold" &&
    requested_amount >= 50 &&
    enough_balance(requested_amount, available_balance)
end
```

Когда `can_request_payout` вызывает `enough_balance`, программа временно переходит во вторую функцию, получает результат и возвращается назад. Этот порядок возврата важен: он же объясняет, где живут переменные внутри функции — разберём в [памяти](memory.md) — и как программа возвращается из ошибки — разберём в [обработке ошибок](errors-and-exceptions.md).

## Область видимости

Переменные внутри функции живут отдельно от внешнего кода:

```ruby
def can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
  minimum_amount_passed = requested_amount >= 50
  profile_verified &&
    bank_account_connected &&
    review_state != "hold" &&
    minimum_amount_passed &&
    available_balance >= requested_amount
end

can_request_payout(true, true, "clear", 120, 300)
puts minimum_amount_passed    # ошибка: переменной здесь нет
```

Это защищает код от случайных пересечений. Читателю не нужно помнить все временные переменные всей программы сразу — достаточно знать параметры и результат конкретной функции.

Функция убирает дублирование логики. Но что делать, когда программа работает не с одним запросом на выплату, а с тридцатью? Каждый запрос — это набор данных, и пока единственный способ их хранить — отдельные [переменные](variables-and-types.md). Для хранения нескольких значений вместе нужны [коллекции](collections.md).

## Sources

- Thomas, D. et al., 2023, *Programming Ruby 3.3*. Pragmatic Bookshelf.
- Abelson, H. & Sussman, G., 1996, *Structure and Interpretation of Computer Programs*. MIT Press.

---

<- [Циклы](loops.md) | [Коллекции](collections.md) ->
