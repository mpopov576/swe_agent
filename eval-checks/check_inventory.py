import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv.pop(1)).resolve()))

from inventory import reserve


class InventoryChecks(unittest.TestCase):
    def test_success(self):
        stock = {"book": 5, "pen": 8}
        self.assertIs(reserve(stock, "book", 2), True)
        self.assertEqual(stock, {"book": 3, "pen": 8})

    def test_exact_stock(self):
        stock = {"book": 3}
        self.assertIs(reserve(stock, "book", 3), True)
        self.assertEqual(stock, {"book": 0})

    def test_insufficient_stock(self):
        stock = {"book": 2, "pen": 8}
        self.assertIs(reserve(stock, "book", 3), False)
        self.assertEqual(stock, {"book": 2, "pen": 8})

    def test_missing_item(self):
        stock = {"pen": 8}
        self.assertIs(reserve(stock, "book", 1), False)
        self.assertEqual(stock, {"pen": 8})

    def test_zero_stock(self):
        stock = {"book": 0}
        self.assertIs(reserve(stock, "book", 1), False)
        self.assertEqual(stock, {"book": 0})

    def test_invalid_quantities(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                stock = {"book": 5}
                with self.assertRaises(ValueError):
                    reserve(stock, "book", quantity)
                self.assertEqual(stock, {"book": 5})

    def test_failure_does_not_break_later_reservation(self):
        stock = {"book": 4}
        self.assertIs(reserve(stock, "book", 5), False)
        self.assertIs(reserve(stock, "book", 2), True)
        self.assertEqual(stock, {"book": 2})


if __name__ == "__main__":
    unittest.main()
