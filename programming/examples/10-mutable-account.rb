class Account
  attr_reader :name, :balance

  def initialize(name, balance)
    @name = name
    @balance = balance
  end

  def deposit!(amount)
    @balance = @balance + amount
  end

  def withdraw!(amount)
    @balance = @balance - amount
  end
end

def apply_salary(account)
  account.deposit!(200)
end

def apply_bonus(account)
  account.deposit!(80)
end

def charge_service(account)
  account.withdraw!(150)
end

def settle_subscription(account)
  account.withdraw!(650)
  charge_service(account)
end

def monthly_processing(account)
  apply_salary(account)
  apply_bonus(account)
  settle_subscription(account)
end

account = Account.new("Alice", 500)
monthly_processing(account)

puts account.name + ": " + account.balance.to_s
