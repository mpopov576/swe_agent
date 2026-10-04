def reserve(stock, item, quantity):
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    available = stock.get(item, 0)
    stock[item] = available - quantity
    return available >= quantity
