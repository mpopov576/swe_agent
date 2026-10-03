import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv.pop(1)).resolve()))

from config import build_config
from options import get_option


class ConfigChecks(unittest.TestCase):
    def test_missing_options(self):
        self.assertEqual(
            build_config({}),
            {"retries": 3, "enabled": True, "prefix": "app"},
        )

    def test_zero_retries(self):
        self.assertEqual(build_config({"retries": 0})["retries"], 0)

    def test_disabled(self):
        self.assertIs(build_config({"enabled": False})["enabled"], False)

    def test_empty_prefix(self):
        self.assertEqual(build_config({"prefix": ""})["prefix"], "")

    def test_none_uses_default(self):
        self.assertEqual(
            build_config({"retries": None, "enabled": None, "prefix": None}),
            {"retries": 3, "enabled": True, "prefix": "app"},
        )

    def test_explicit_values_and_input_unchanged(self):
        settings = {"retries": 7, "enabled": True, "prefix": "service"}
        original = settings.copy()
        self.assertEqual(build_config(settings), original)
        self.assertEqual(settings, original)

    def test_helper_preserves_empty_collection(self):
        self.assertEqual(get_option({"items": []}, "items", ["default"]), [])


if __name__ == "__main__":
    unittest.main()
