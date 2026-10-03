import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv.pop(1)).resolve()))

from tags import normalize_tags


class TagChecks(unittest.TestCase):
    def test_first_appearance_order(self):
        self.assertEqual(
            normalize_tags(["Zebra", "apple", "Moon"]),
            ["zebra", "apple", "moon"],
        )

    def test_duplicates_keep_first_position(self):
        self.assertEqual(
            normalize_tags([" Beta ", "alpha", "BETA", "gamma", "ALPHA"]),
            ["beta", "alpha", "gamma"],
        )

    def test_blank_tags(self):
        self.assertEqual(
            normalize_tags(["", "  ", " B ", "\t", "a"]),
            ["b", "a"],
        )

    def test_empty_input(self):
        self.assertEqual(normalize_tags([]), [])

    def test_input_is_not_modified(self):
        tags = [" B ", "a", "B"]
        original = tags.copy()
        normalize_tags(tags)
        self.assertEqual(tags, original)


if __name__ == "__main__":
    unittest.main()
