# Объектно-ориентированное программирование

**Предпосылки:** [Коллекции](06-collections.md) (массивы, хеши), [Память](07-memory.md) (общие данные, изменение по ссылке).

<- [Память](07-memory.md) | [Наследование и полиморфизм](09-inheritance-and-polymorphism.md) ->

После заметки о памяти уже понятно: один и тот же хеш можно передать в несколько функций и изменить из любого места. Это работает, пока рядом одна сущность и несколько правил. Но в программе управления заказами и продавцами в одном файле быстро оказываются `seller`, `payout_request`, `listing`, `shipment`, `refund`, `coupon`, `invoice` и `support_case`. У каждой структуры свои поля, свои проверки, свои статусы и свои прямые записи.

Вот [пример](examples/08-loose-functions.rb). Его не нужно разбирать построчно — достаточно посмотреть, как быстро один файл превращается в кашу из восьми хешей, тридцати с лишним функций и прямых записей в структуры.

<details>
<summary>Какие функции знают о каких полях</summary>

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

Этот код вводит несколько новых конструкций Ruby. Разберём каждую.

**`class Seller ... end`** описывает тип объекта. Всё между `class` и `end` принадлежит этому типу: и данные, и операции над ними.

**`def initialize(name, country:, ...)`** — метод, который Ruby вызывает автоматически при создании объекта. Аргументы вроде `country:` — именованные: при вызове нужно писать `country: "US"`, а не надеяться на правильный порядок. Это удобнее позиционных параметров из [Функций](05-functions.md), когда параметров много.

**`@name`, `@country`, `@blocked`, ...** — переменные экземпляра. Префикс `@` означает, что переменная принадлежит конкретному объекту и доступна из любого его метода. Обычные переменные (без `@`) живут только внутри одного метода, как мы уже видели в [области видимости](05-functions.md).

**`attr_reader :name, :country`** создаёт методы для чтения: после этой строки код снаружи может вызвать `seller.name` и получить значение `@name`. Без `attr_reader` доступ к `@name` извне невозможен. `:name` здесь — символ (symbol), неизменяемое имя; он указывает, для какой переменной создать метод чтения.

**`display_name`, `blocked?`, `can_withdraw?`, `risk_badge`, `suspend`** — методы объекта. Знак `?` в конце имени — Ruby-соглашение для методов, которые отвечают на вопрос да/нет и возвращают `true` или `false`.

`Seller.new(...)` создаёт новый объект и вызывает `initialize` с переданными аргументами. Точка в `seller.display_name` означает «вызвать метод `display_name` у объекта `seller`» — это dot-нотация, общий способ обращения к методам объекта:

```ruby
seller = Seller.new(
  "Alice Store",
  country: "US",
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

Инкапсуляция (от лат. capsula — «коробочка») означает: объект сам контролирует, как его меняют.

В примере выше код снаружи не может просто так записать `@blocked = true` или подменить правило `can_withdraw?` в случайном месте файла. Изменение идёт через `suspend`, а чтение важных состояний — через `blocked?`, `can_withdraw?` и `risk_badge`.

Так код снаружи видит меньше деталей. Это снова снижает нагрузку на чтение: чтобы понять, как можно изменить продавца, достаточно посмотреть публичные методы класса.

Класс окупается тогда, когда у сущности есть данные **и** правила работы с ними. Если данные просто передаются из функции в функцию без собственного поведения — хеша достаточно.

## Коллекция объектов

Объекты удобно хранить и обрабатывать в коллекциях. В примере ниже `.each` обходит массив, вызывая для каждого элемента блок кода между `do` и `end`. Имя `|seller|` — параметр блока: на каждом шаге он указывает на текущий элемент массива:

```ruby
sellers = [
  Seller.new("Alice Store", country: "US", verification_state: "verified", blocked: false, active: true, balance_cents: 18_000, rating: 4.7),
  Seller.new("North Goods", country: "PL", verification_state: "pending", blocked: false, active: true, balance_cents: 7_000, rating: 3.9)
]

sellers.each do |seller|
  puts seller.display_name + ": " + seller.risk_badge
end
```

Массив остаётся массивом, но теперь его элементы умеют сами отвечать за своё поведение.

Класс `Seller` работает, пока все продавцы подчиняются одним правилам. Но что делать, если в системе появляются способы доставки — самовывоз, курьер, экспресс — каждый со своей ценой и сроком?

## Sources

Как Ruby реализует классы и объекты на уровне интерпретатора — в [Объекты и классы](../ruby/internal/object-model/00-objects-and-classes.md).

- Dahl, O.-J. & Nygaard, K., 1966, *SIMULA: an ALGOL-based simulation language*. Communications of the ACM.
- Kay, A., 1993, *The Early History of Smalltalk*. ACM SIGPLAN Notices.
- Thomas, D. et al., 2023, *Programming Ruby 3.3*. Pragmatic Bookshelf.

---

<- [Память](07-memory.md) | [Наследование и полиморфизм](09-inheritance-and-polymorphism.md) ->
