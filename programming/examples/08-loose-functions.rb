seller = {
  "name" => "Alice Store",
  "country" => "KZ",
  "verification_state" => "verified",
  "blocked" => false,
  "active" => true,
  "rating" => 4.7,
  "balance_cents" => 18_000
}

payout_request = {
  "amount_cents" => 12_000,
  "status" => "draft",
  "bank_account_connected" => true,
  "manual_hold" => false,
  "last_error" => ""
}

listing = {
  "title" => "Desk lamp",
  "price_cents" => 9_000,
  "discount_cents" => 500,
  "status" => "draft",
  "stock" => 3,
  "category" => "home"
}

shipment = {
  "state" => "new",
  "express" => false,
  "packed" => true,
  "shipped_at" => nil,
  "carrier" => "dhl"
}

refund = {
  "reason" => "damaged",
  "amount_cents" => 4_000,
  "delivery_refund_cents" => 500,
  "status" => "processing",
  "approved" => false
}

coupon = {
  "code" => "SPRING",
  "percent_off" => 0.10,
  "active" => true,
  "minimum_cents" => 3_000,
  "expires_in_days" => 5
}

invoice = {
  "subtotal_cents" => 20_000,
  "commission_cents" => 2_400,
  "paid" => false,
  "overdue_days" => 3,
  "country" => "KZ"
}

support_case = {
  "priority" => "normal",
  "status" => "open",
  "seller_message_count" => 4,
  "buyer_message_count" => 2,
  "escalated" => false
}

def seller_display_name(seller)
  seller["name"] + " (" + seller["country"] + ")"
end

def coupon_applicable?(coupon, subtotal_cents)
  coupon["active"] &&
    coupon["expires_in_days"] > 0 &&
    subtotal_cents >= coupon["minimum_cents"]
end

def payout_ready?(seller, payout_request)
  seller_can_withdraw?(seller) &&
    payout_request["bank_account_connected"] &&
    !payout_request["manual_hold"] &&
    payout_request["status"] == "draft" &&
    payout_request["amount_cents"] <= seller["balance_cents"]
end

def listing_badge(listing)
  listing["status"] + " / " + listing["category"]
end

def shipment_eta_label(shipment)
  if shipment["express"]
    "tomorrow"
  elsif shipment["shipped_at"]
    "3 days"
  else
    "not shipped"
  end
end

def invoice_total_cents(invoice)
  invoice["subtotal_cents"] + invoice["commission_cents"]
end

def refund_badge(refund)
  refund["reason"] + " / " + refund["status"]
end

def support_case_urgent?(support_case)
  support_case["escalated"] || support_case["priority"] == "high"
end

def seller_risk_badge(seller)
  return "blocked" if seller_blocked?(seller)
  return "watch" if seller["rating"] < 4.0
  "normal"
end

def coupon_discount_cents(coupon, subtotal_cents)
  return 0 unless coupon_applicable?(coupon, subtotal_cents)
  (subtotal_cents * coupon["percent_off"]).to_i
end

def listing_final_price_cents(listing, coupon)
  base_price = listing["price_cents"] - listing["discount_cents"]
  base_price - coupon_discount_cents(coupon, base_price)
end

def payout_fee_cents(payout_request)
  return 0 if payout_request["amount_cents"] >= 50_000
  300
end

def mark_shipped!(shipment)
  shipment["shipped_at"] = "2026-04-03"
  shipment["state"] = "in_transit"
end

def refund_total_cents(refund)
  refund["amount_cents"] + refund["delivery_refund_cents"]
end

def mark_invoice_paid!(invoice)
  invoice["paid"] = true
end

def support_owner_label(support_case)
  support_case["status"] + " / " + support_case["priority"]
end

def seller_blocked?(seller)
  seller["blocked"] || !seller["active"]
end

def payout_badge(payout_request)
  payout_request["status"]
end

def listing_publishable?(listing, seller)
  !seller_blocked?(seller) &&
    listing["status"] == "draft" &&
    listing["stock"] > 0 &&
    listing["price_cents"] > 0
end

def shipment_badge(shipment)
  shipment["carrier"] + " / " + shipment["state"]
end

def refund_closable?(refund)
  refund["approved"] && refund["status"] == "processing"
end

def invoice_collectable?(invoice)
  !invoice["paid"] && invoice["overdue_days"] < 30
end

def close_case!(support_case)
  support_case["status"] = "closed"
end

def seller_can_withdraw?(seller)
  seller["verification_state"] == "verified" &&
    !seller_blocked?(seller) &&
    seller["balance_cents"] >= 10_000
end

def deactivate_coupon!(coupon)
  coupon["active"] = false
end

def queue_payout!(payout_request)
  payout_request["status"] = "queued"
end

def archive_listing!(listing)
  listing["status"] = "archived"
end

def shipment_refundable?(shipment)
  shipment["state"] != "delivered"
end

def approve_refund!(refund)
  refund["approved"] = true
end

def invoice_badge(invoice)
  return "paid" if invoice["paid"]
  return "overdue" if invoice["overdue_days"] > 0
  "open"
end

def support_badge(support_case)
  support_case["seller_message_count"].to_s + ":" + support_case["buyer_message_count"].to_s
end

puts "=== Overview ==="
puts seller_display_name(seller)
puts seller_risk_badge(seller)
puts payout_ready?(seller, payout_request)
puts listing_badge(listing)
puts listing_final_price_cents(listing, coupon)
puts shipment_eta_label(shipment)
puts refund_badge(refund)
puts refund_total_cents(refund)
puts invoice_total_cents(invoice)
puts support_owner_label(support_case)
puts ""

queue_payout!(payout_request)
mark_shipped!(shipment)
approve_refund!(refund)
mark_invoice_paid!(invoice)
close_case!(support_case)

seller["blocked"] = true
listing["price_cents"] = -1000
payout_request["manual_hold"] = true
support_case["priority"] = "high"

puts "=== After changes ==="
puts payout_badge(payout_request)
puts payout_ready?(seller, payout_request)
puts listing_publishable?(listing, seller)
puts shipment_badge(shipment)
puts shipment_refundable?(shipment)
puts refund_closable?(refund)
puts invoice_collectable?(invoice)
puts invoice_badge(invoice)
puts support_case_urgent?(support_case)
puts support_badge(support_case)
