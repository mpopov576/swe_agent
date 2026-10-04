from inventory import reserve


def test_successful_reservation():
    stock = {"book": 5}
    assert reserve(stock, "book", 2) is True
    assert stock == {"book": 3}
