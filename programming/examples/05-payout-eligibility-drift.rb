profile_verified = true
bank_account_connected = true
review_state = "hold"
requested_amount = 120
available_balance = 300

puts "=== Withdraw page button ==="
blocked_by_review = review_state == "hold"
enough_money_for_request = available_balance >= requested_amount
button_enabled =
  profile_verified &&
  bank_account_connected &&
  !blocked_by_review &&
  requested_amount >= 50 &&
  enough_money_for_request
if button_enabled
  puts "Withdraw"
else
  puts "Unavailable"
end
puts ""

puts "=== Withdraw page reason text ==="
if !profile_verified
  reason_text = "Verify your profile first"
elsif !bank_account_connected
  reason_text = "Connect a bank account"
elsif review_state == "hold"
  reason_text = "Payouts are paused while the account is under review"
elsif requested_amount < 50
  reason_text = "Minimum payout amount is 50"
elsif available_balance < requested_amount
  reason_text = "Requested amount is higher than available balance"
else
  reason_text = "Ready for payout"
end
puts reason_text
puts ""

puts "=== Seller dashboard banner ==="
identity_ready = profile_verified
payout_target_ready = bank_account_connected
amount_ok_for_banner = requested_amount >= 50
balance_ok_for_banner = available_balance >= requested_amount
banner_visible =
  identity_ready &&
  payout_target_ready &&
  amount_ok_for_banner &&
  balance_ok_for_banner
if banner_visible
  puts "You can withdraw funds today"
else
  puts "Banner hidden"
end
puts ""

puts "=== Create payout API ==="
request_allowed = true
if !profile_verified
  request_allowed = false
end
if !bank_account_connected
  request_allowed = false
end
if requested_amount < 50
  request_allowed = false
end
if available_balance < requested_amount
  request_allowed = false
end
if request_allowed
  puts "201 payout created"
else
  puts "422 payout unavailable"
end
puts ""

puts "=== Finance sidebar ==="
hold_cleared = review_state != "hold"
minimum_amount_passed = requested_amount > 50
available_now = available_balance >= requested_amount
sidebar_can_highlight =
  profile_verified &&
  bank_account_connected &&
  hold_cleared &&
  minimum_amount_passed &&
  available_now
puts sidebar_can_highlight
puts ""

puts "=== Night payout queue ==="
risk_cleared = review_state != "hold"
queue_amount_ok = requested_amount >= 50
queue_balance_ok = available_balance >= requested_amount
should_queue_payout =
  profile_verified &&
  bank_account_connected &&
  risk_cleared &&
  queue_amount_ok &&
  queue_balance_ok
if should_queue_payout
  puts "queued"
else
  puts "skipped"
end
puts ""

puts "=== Finance CSV export ==="
export_profile_ready = profile_verified
export_bank_ready = bank_account_connected
export_hold_cleared = review_state != "hold"
export_fits_balance = available_balance >= requested_amount
export_row_ready =
  export_profile_ready &&
  export_bank_ready &&
  export_hold_cleared &&
  export_fits_balance
puts export_row_ready
puts ""

puts "=== Support tool ==="
manual_review_is_clear = review_state != "hold"
requested_sum_ok = requested_amount >= 50
enough_balance_for_case = available_balance >= requested_amount
support_allows_manual_payout =
  manual_review_is_clear &&
  requested_sum_ok &&
  enough_balance_for_case &&
  profile_verified &&
  bank_account_connected
puts support_allows_manual_payout
