def delivery_label(method)
  if method["kind"] == "pickup"
    "Самовывоз"
  elsif method["kind"] == "courier"
    "Курьер"
  elsif method["kind"] == "express"
    "Экспресс"
  end
end

# order_total.rb — поле переименовали в прошлом квартале,
# старые функции ещё читают через "kind", новые — через "type"
def delivery_price(method, order_total)
  if method["type"] == "pickup"
    0
  elsif method["type"] == "courier"
    300
  elsif method["type"] == "express"
    700
  end
end

def delivery_eta(method)
  if method["kind"] == "pickup"
    "сегодня"
  elsif method["kind"] == "courier"
    "2 дня"
  elsif method["kind"] == "express"
    "завтра"
  end
end

# рабочие записи несут оба ключа — миграция не завершена
methods = [
  { "kind" => "pickup",  "type" => "pickup" },
  { "kind" => "courier", "type" => "courier" },
  { "kind" => "express", "type" => "express" }
]

order_total = 2400

methods.each do |method|
  puts delivery_label(method) + ": " +
       delivery_price(method, order_total).to_s + ", " +
       delivery_eta(method)
end
