---
tags:
  - domain/programming
  - theme/data-representation
  - type/concept
aliases:
  - OOP
  - object-oriented programming
order: 8
---

# Объектно-ориентированное программирование

**Предпосылки:** [Функции](functions.md) (определение функции, параметры), [Коллекции](collections.md) (массивы, хеши), [Память](memory.md) (общие данные, изменение по ссылке).

<- [Память](memory.md) | [Наследование и полиморфизм](inheritance-and-polymorphism.md) ->

После заметки о [памяти](memory.md) уже понятно: один и тот же хеш можно передать в несколько [функций](functions.md) и изменить из любого места. Пока рядом одна сущность и пара правил, такая схема держится. Но в файле управления маркетплейсом быстро оказываются `seller`, `payout_request`, `listing`, `shipment`, `refund`, `coupon`, `invoice` и `support_case` — восемь хешей, у каждого свой набор полей и свои тридцать с лишним функций вокруг.

## Когда данные и операции живут отдельно

Вот срез одного такого файла — три хеша из восьми и пять функций из тридцати:

```ruby
seller = {
  "name" => "Alice Store",
  "verification_state" => "verified",
  "blocked" => false,
  "active" => true,
  "balance_cents" => 18_000
}

payout_request = {
  "amount_cents" => 12_000,
  "status" => "draft",
  "bank_account_connected" => true,
  "manual_hold" => false
}

listing = {
  "title" => "Desk lamp",
  "price_cents" => 9_000,
  "discount_cents" => 500,
  "status" => "draft",
  "stock" => 3
}

def seller_blocked?(seller)
  seller["blocked"] || !seller["active"]
end

def seller_can_withdraw?(seller)
  seller["verification_state"] == "verified" &&
    !seller_blocked?(seller) &&
    seller["balance_cents"] >= 10_000
end

def payout_ready?(seller, payout_request)
  seller_can_withdraw?(seller) &&
    payout_request["bank_account_connected"] &&
    !payout_request["manual_hold"] &&
    payout_request["amount_cents"] <= seller["balance_cents"]
end

def listing_publishable?(listing, seller)
  !seller_blocked?(seller) &&
    listing["status"] == "draft" &&
    listing["stock"] > 0 &&
    listing["price_cents"] > 0
end

# где-то ниже в файле:
seller["blocked"] = true
listing["price_cents"] = -1000
payout_request["manual_hold"] = true
```

Здесь весь срез перед глазами: три хеша, четыре функции. В реальном проекте те же сущности живут в `app/models/seller.rb`, `app/services/payout_eligibility.rb`, `app/jobs/daily_payout.rb`, `lib/billing/fees.rb`, полутора десятках контроллеров и админке. Структура каждого хеша утекла через двести с лишним функций, написанных в разные годы разными людьми.

Задача «добавить продавцу поле `risk_score` и учитывать его в проверке выплаты» превращается в grep по всему репозиторию. Находишь сто мест, где читают `seller["balance_cents"]`, аккуратно дописываешь проверку в пятидесяти из них. На ревью видны только твои файлы — не те пятьдесят других, которые уже ходят к полю напрямую, не зная о новом правиле. Пропущенный случай проявится через квартал на клиенте, для которого `risk_score` выставлен руками в `nil`: сравнение с числом уронит ночной отчёт, который никто не смотрит до следующей выплаты. Запускаемая версия среза — в [examples/08-loose-functions.rb](examples/08-loose-functions.rb); настоящая боль не в её длине, а в том, что таких файлов в проекте пятнадцать и ни один не знает о других.

## Класс и объект

Идея простая: собрать данные одной сущности и операции над ними в одно место, где снаружи видны только точки входа, а форма — внутренняя деталь.

```ruby
class Seller
  def initialize(name, verified, balance_cents)
    @name = name
    @verified = verified
    @balance_cents = balance_cents
  end

  def name
    @name
  end

  def can_withdraw?
    @verified && @balance_cents >= 10_000
  end

  def deposit!(amount)
    raise ArgumentError, "amount must be positive" if amount <= 0
    @balance_cents += amount
  end
end
```

`class Seller ... end` описывает тип объекта. Всё между `class` и `end` относится к продавцу как к сущности: и данные, и операции над ними.

`def initialize(...)` — специальный метод, который Ruby вызывает при создании нового объекта. Значения `name`, `verified`, `balance_cents` приходят снаружи, а `@name`, `@verified`, `@balance_cents` становятся состоянием конкретного продавца. Префикс `@` помечает переменную как поле объекта: она живёт вместе с объектом и доступна его методам, но не видна снаружи напрямую.

Метод — это та же функция, но привязанная к объекту: вместо первого параметра `seller` у него неявный получатель, и вместо `seller["balance_cents"]` он обращается к `@balance_cents`.

Такой ход встречается не только в Ruby. В Java и C# данные и методы тоже собирают в `class`. В Rust ту же роль играет пара `struct` + `impl`: поля лежат в структуре, а связанные операции описываются рядом.

`Seller.new(...)` создаёт новый объект и вызывает `initialize`. Точка в `seller.name` означает «вызвать метод `name` у объекта `seller`»:

```ruby
seller = Seller.new("Alice Store", true, 9_000)

puts seller.name
puts seller.can_withdraw?   # false

seller.deposit!(2_000)
puts seller.can_withdraw?   # true
```

Правило вывода денег и изменение баланса теперь живут рядом с самими деньгами. Внешнему коду не нужно знать, в каком поле лежит баланс, какой флаг проверять перед выплатой и какие другие функции читают ту же структуру. IDE «найти использования» для `deposit!` или `can_withdraw?` возвращает все точки, где баланс проверяется и меняется. Новый разработчик видит `seller.deposit!(amount)` — и за этим вызовом уже нельзя «случайно» записать отрицательное число в баланс: проверка живёт внутри объекта, а не в одной из пятидесяти функций, которые кто-то когда-то написал на соседней странице кода.

## Инкапсуляция

Инкапсуляция (от лат. capsula — «коробочка») означает: объект сам контролирует, как его меняют.

Строку `seller["balance_cents"] = seller["balance_cents"] + 2000` в мире хешей мог написать кто угодно и где угодно — проверку никто не гарантировал. У объекта такой строки попросту нет: поле `@balance_cents` снаружи не видно, и единственный способ его изменить — пройти через `deposit!`, который сам проверит аргумент. Мутация, которая раньше была разбросана по файлу, теперь сходится в одной точке.

Чтобы понять, как можно работать с продавцом, достаточно посмотреть список методов класса. Всё, чего там нет, снаружи и не произойдёт.

Класс окупается тогда, когда у сущности есть и данные, и правила обращения с ними. Если данные просто проходят через функции без собственного поведения — хеша достаточно.

## Коллекция объектов

Объекты удобно хранить и обрабатывать в [коллекциях](collections.md). В примере ниже `.each` обходит массив, вызывая для каждого элемента блок кода между `do` и `end`. Имя `|seller|` — параметр блока: на каждом шаге он указывает на текущий элемент массива:

```ruby
sellers = [
  Seller.new("Alice Store", true, 18_000),
  Seller.new("North Goods", false, 7_000)
]

sellers.each do |seller|
  if seller.can_withdraw?
    puts seller.name + ": payout ready"
  else
    puts seller.name + ": payout blocked"
  end
end
```

Массив остаётся массивом, но его элементы умеют сами отвечать за своё поведение.

Класс `Seller` держится, пока все продавцы подчиняются одним правилам. Но как только появляются способы доставки — самовывоз, курьер, экспресс, каждый со своей ценой и сроком — одного класса уже не хватит. Тогда на сцену выходят [наследование и полиморфизм](inheritance-and-polymorphism.md).

## Sources

Как Ruby реализует классы и объекты на уровне интерпретатора — в [Объекты и классы](../ruby/internal/object-model/objects-and-classes.md).

- Dahl, O.-J. & Nygaard, K., 1966, *SIMULA: an ALGOL-based simulation language*. Communications of the ACM.
- Kay, A., 1993, *The Early History of Smalltalk*. ACM SIGPLAN Notices.
- Thomas, D. et al., 2023, *Programming Ruby 3.3*. Pragmatic Bookshelf.

---

<- [Память](memory.md) | [Наследование и полиморфизм](inheritance-and-polymorphism.md) ->
