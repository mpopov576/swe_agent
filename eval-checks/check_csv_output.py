import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv.pop(1)).resolve()))

from csv_output import encode_row


class CSVChecks(unittest.TestCase):
    def check_row(self, fields):
        original = fields.copy()
        encoded = encode_row(fields)

        self.assertIsInstance(encoded, str)
        self.assertTrue(encoded.endswith("\r\n"))

        decoded = list(
            csv.reader(io.StringIO(encoded, newline=""), strict=True)
        )
        self.assertEqual(decoded, [original])
        self.assertEqual(fields, original)

    def test_plain_fields(self):
        self.check_row(["alpha", "beta"])

    def test_comma(self):
        self.check_row(["alpha,beta", "gamma"])

    def test_quotes(self):
        self.check_row(['"quoted"', "plain"])

    def test_line_feed(self):
        self.check_row(["first\nsecond", "end"])

    def test_carriage_return(self):
        self.check_row(["first\rsecond", "end"])

    def test_single_empty_field(self):
        self.check_row([""])

    def test_multiple_empty_fields(self):
        self.check_row(["", "middle", ""])

    def test_unicode(self):
        self.check_row(["café", "здравей"])

    def test_empty_row(self):
        self.check_row([])


if __name__ == "__main__":
    unittest.main()
