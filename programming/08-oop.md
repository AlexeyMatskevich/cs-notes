# Объектно-ориентированное программирование

**Предпосылки:** [Коллекции](06-collections.md) (массивы, хеши), [Память](07-memory.md) (общие данные, изменение по ссылке).

<- [Память](07-memory.md) | [Наследование и полиморфизм](09-inheritance-and-polymorphism.md) ->

После заметки о памяти уже понятно: один и тот же хеш можно передать в несколько функций и изменить из любого места. Это работает, пока рядом одна сущность и несколько правил. Но в реальном backoffice в одном файле быстро оказываются `seller`, `payout_request`, `listing`, `shipment`, `refund`, `coupon`, `invoice` и `support_case`. У каждой структуры свои поля, свои проверки, свои статусы и свои прямые записи.

Вот [пример](examples/08-loose-functions.rb). Если хотите запустить его без установки Ruby, используйте web runner из [index](index.md). Его не нужно разбирать построчно. Достаточно посмотреть, как быстро один файл превращается в кашу из восьми хешей, тридцати с лишним функций и прямых записей в структуры.

<details>
<summary>Почему такой файл уже начинает разваливаться</summary>

Поля `seller` знают `seller_display_name`, `seller_blocked?`, `seller_can_withdraw?`, `seller_risk_badge`, `payout_ready?`, `listing_publishable?` и прямая запись `seller["blocked"] = true`. Поля `listing` текут в `listing_badge`, `listing_final_price_cents`, `listing_publishable?` и прямую запись `listing["price_cents"] = -1000`. То же происходит с `payout_request`, `shipment`, `refund`, `invoice` и `support_case`: форма данных уже расползлась по файлу и больше не выглядит локальной деталью.

</details>

## Когда данные и операции живут отдельно

Если `seller`, `payout_request`, `listing`, `shipment` и другие сущности лежат в хешах, а операции над ними разбросаны по отдельным функциям, то форма данных начинает течь по всему файлу. Любая новая правка требует вспоминать:

- какие поля есть у каждой структуры;
- какие функции их читают;
- какие функции их меняют;
- где есть прямой доступ без проверок.

Это неудобно не для выполнения программы, а для чтения и правки кода.

## Класс и объект

Класс собирает данные одной сущности и связанные с ними операции в одном месте:

```ruby
class Seller
  attr_reader :name, :country

  def initialize(name, country:, verification_state:, blocked:, active:, balance_cents:, rating:)
    @name = name
    @country = country
    @verification_state = verification_state
    @blocked = blocked
    @active = active
    @balance_cents = balance_cents
    @rating = rating
  end

  def display_name
    @name + " (" + @country + ")"
  end

  def blocked?
    @blocked || !@active
  end

  def can_withdraw?
    @verification_state == "verified" &&
      !blocked? &&
      @balance_cents >= 10_000
  end

  def risk_badge
    return "blocked" if blocked?
    return "watch" if @rating < 4.0
    "normal"
  end

  def suspend
    @blocked = true
  end
end
```

`class` описывает, какие данные хранит объект и что с ними можно делать. `initialize` запускается при создании объекта. `@name`, `@country`, `@verification_state`, `@blocked`, `@active`, `@balance_cents`, `@rating` — данные объекта. `display_name`, `blocked?`, `can_withdraw?`, `risk_badge`, `suspend` — его методы.

Создание и использование:

```ruby
seller = Seller.new(
  "Alice Store",
  country: "KZ",
  verification_state: "verified",
  blocked: false,
  active: true,
  balance_cents: 18_000,
  rating: 4.7
)

puts seller.display_name
puts seller.can_withdraw?
seller.suspend
puts seller.risk_badge
```

Теперь правила работы с продавцом собраны рядом с самими данными. Точно так же в большом коде отдельными классами обычно становятся `PayoutRequest`, `Listing`, `Shipment`, `Refund`, `Invoice` и другие сущности.

## Инкапсуляция

Инкапсуляция означает: объект сам контролирует, как его меняют.

В примере выше код снаружи не может просто так записать `@blocked = true` или подменить правило `can_withdraw?` в случайном месте файла. Изменение идёт через `suspend`, а чтение важных состояний — через `blocked?`, `can_withdraw?` и `risk_badge`.

Так код снаружи видит меньше деталей. Это снова снижает нагрузку на чтение: чтобы понять, как можно изменить продавца, достаточно посмотреть публичные методы класса.

## Коллекция объектов

Объекты удобно хранить и обрабатывать в коллекциях:

```ruby
sellers = [
  Seller.new("Alice Store", country: "KZ", verification_state: "verified", blocked: false, active: true, balance_cents: 18_000, rating: 4.7),
  Seller.new("North Goods", country: "PL", verification_state: "pending", blocked: false, active: true, balance_cents: 7_000, rating: 3.9)
]

sellers.each do |seller|
  puts seller.display_name + ": " + seller.risk_badge
end
```

Массив остаётся массивом, но теперь его элементы умеют сами отвечать за своё поведение.

Один класс решает проблему, пока все объекты подчиняются одним и тем же правилам. Следующий вопрос возникает тогда, когда объектов несколько видов: похожих, но не одинаковых.

## Sources

Как Ruby реализует классы и объекты на уровне интерпретатора — в [Объекты и классы](../ruby/internal/object-model/00-objects-and-classes.md).

- Dahl, O.-J. & Nygaard, K., 1966, *SIMULA: an ALGOL-based simulation language*. Communications of the ACM.
- Kay, A., 1993, *The Early History of Smalltalk*. ACM SIGPLAN Notices.
- Thomas, D. et al., 2023, *Programming Ruby 3.3*. Pragmatic Bookshelf.

---

<- [Память](07-memory.md) | [Наследование и полиморфизм](09-inheritance-and-polymorphism.md) ->
