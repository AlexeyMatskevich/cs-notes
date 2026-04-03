def delivery_label(method)
  if method["kind"] == "pickup"
    "Самовывоз"
  elsif method["kind"] == "courier"
    "Курьер"
  elsif method["kind"] == "express"
    "Экспресс"
  end
end

def delivery_price(method, order_total)
  if method["kind"] == "pickup"
    0
  elsif method["kind"] == "courier"
    300
  elsif method["kind"] == "express"
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

methods = [
  { "kind" => "pickup" },
  { "kind" => "courier" },
  { "kind" => "express" }
]

order_total = 2400

methods.each do |method|
  puts delivery_label(method) + ": " +
       delivery_price(method, order_total).to_s + ", " +
       delivery_eta(method)
end
