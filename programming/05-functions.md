# Функции

**Предпосылки:** [Условия и ввод/вывод](03-conditions-and-io.md) (`&&`, `!=`, `>=`), [Циклы](04-loops.md) (while, повторение действий).

<- [Циклы](04-loops.md) | [Коллекции](06-collections.md) ->

В приложении маркетплейса правило выплаты продавцу считают в нескольких частях программы: в кнопке вывода денег, в баннере и в ночной проверке. Правило изменилось: ручная блокировка теперь тоже должна останавливать выплату. Компьютер выполнит любую проверку, которую ему дадут. Трудность в другом: одна и та же логика быстро расползается по файлу под разными локальными именами и в разном порядке условий.

Проблема здесь уже не в длине кода как таковой. Проблема в том, что человек больше не может надёжно удерживать в голове все копии правила и замечать, где они начали расходиться.

Правильная логика в чистом виде выглядит так:

```ruby
can_request_payout =
  profile_verified &&
  bank_account_connected &&
  review_state != "hold" &&
  requested_amount >= 50 &&
  available_balance >= requested_amount
```

Вот [пример](examples/05-payout-eligibility-drift.rb). Его не нужно разбирать как упражнение на внимательность — достаточно посмотреть, как быстро одно короткое правило превращается в тяжёлый для чтения файл, где одинаковая проверка уже живёт в UI, тексте ошибок, API и ночной обработке.

> [!info]- Где правило уже разъехалось
> Разбирать такой файл построчно ради победы не нужно. Важно увидеть сам тип боли: даже в этом сокращённом фрагменте правило уже живёт в нескольких формах, и они начинают расходиться.
>
> - В `seller dashboard banner` полностью потерялась ручная блокировка: там есть профиль, банк, минимальная сумма и баланс, но нет `review_state != "hold"`.
> - В `create payout API` та же проблема, только в другой форме: условие разбито на несколько `if`, и новая часть правила туда просто не дошла.
> - В `finance sidebar` правило уже дрейфует ещё сильнее: там проверка на минимальную сумму стала `requested_amount > 50`, хотя в исходном правиле было `>= 50`.
> - В `finance CSV export` ручная блокировка есть, но потерялась проверка на минимальную сумму.
> - При этом `withdraw page button`, `withdraw page reason text`, `night payout queue` и `support tool` всё ещё держат полную версию правила. Именно поэтому такой файл неприятен: тут нет одной поломки, тут уже несколько почти одинаковых кусков, которые разъезжаются каждый по-своему.

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

Теперь вместо трёх копий формулы остаются три вызова:

```ruby
button_enabled = can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
banner_visible = can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
should_queue_payout = can_request_payout(profile_verified, bank_account_connected, review_state, requested_amount, available_balance)
```

Если правило снова изменится, править нужно одну функцию, а не каждую копию отдельно.

Это не специальный приём Ruby. Та же идея есть в разных языках: дать куску логики имя, передать входные данные и получить результат обратно.

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

result = can_request_payout(true, true, "clear", 120, 300)
puts result    # true
```

При вызове `can_request_payout(true, true, "clear", 120, 300)` первое `true` попадает в `profile_verified`, второе `true` — в `bank_account_connected`, строка `"clear"` — в `review_state`, `120` — в `requested_amount`, `300` — в `available_balance`. Последнее вычисленное выражение становится результатом функции.

Функция может возвращать и не число, а, например, строку:

```ruby
def greeting(name)
  "Hello, " + name
end
```

В Ruby результатом часто становится последнее вычисленное выражение. Во многих других языках результат возвращают явно через `return`, а иногда ещё и указывают его тип в заголовке функции. Но во всех случаях вопрос один и тот же: какие данные функция получает и что она обещает вернуть назад.

## Вызовы и стек

Стек (stack — «стопка»: последний положенный элемент снимается первым) подробно устроен в [заметке о памяти](07-memory.md), но главная идея нужна уже сейчас.

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

Когда `can_request_payout` вызывает `enough_balance`, программа временно переходит во вторую функцию, получает результат и возвращается назад. Этот порядок возврата важен: он же объясняет, где живут переменные внутри функции — разберём в [памяти](07-memory.md) — и как программа возвращается из ошибки — разберём в [обработке ошибок](11-errors-and-exceptions.md).

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

Функция убирает дублирование логики. Но что делать, когда программа работает не с одним запросом на выплату, а с тридцатью? Каждый запрос — это набор данных, и пока единственный способ их хранить — отдельные переменные.

## Sources

- Thomas, D. et al., 2023, *Programming Ruby 3.3*. Pragmatic Bookshelf.
- Abelson, H. & Sussman, G., 1996, *Structure and Interpretation of Computer Programs*. MIT Press.

---

<- [Циклы](04-loops.md) | [Коллекции](06-collections.md) ->
