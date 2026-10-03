import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv.pop(1)).resolve()))

from pagination import get_page


class PaginationChecks(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(
            get_page([1, 2, 3], 2),
            {"items": [1, 2], "next_token": "2"},
        )

    def test_partial_final_page(self):
        self.assertEqual(
            get_page([1, 2, 3], 2, "2"),
            {"items": [3], "next_token": None},
        )

    def test_full_final_page(self):
        self.assertEqual(
            get_page([1, 2, 3, 4], 2, "2"),
            {"items": [3, 4], "next_token": None},
        )

    def test_empty_input(self):
        self.assertEqual(
            get_page([], 2),
            {"items": [], "next_token": None},
        )

    def test_offset_beyond_end(self):
        self.assertEqual(
            get_page([1, 2], 2, "8"),
            {"items": [], "next_token": None},
        )

    def test_complete_traversal(self):
        items = [1, 2, 3, 4, 5]
        collected = []
        token = None

        # A bounded loop prevents broken pagination from hanging the checker.
        for _ in range(5):
            page = get_page(items, 2, token)
            collected.extend(page["items"])
            token = page["next_token"]

            if token is None:
                break
        else:
            self.fail("Pagination did not terminate")

        self.assertEqual(collected, items)

    def test_input_unchanged(self):
        items = [1, 2, 3]
        get_page(items, 2)
        self.assertEqual(items, [1, 2, 3])

    def test_invalid_arguments(self):
        for size in (0, -1):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    get_page([1], size)

        with self.assertRaises(ValueError):
            get_page([1], 2, "-1")


if __name__ == "__main__":
    unittest.main()
