import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv.pop(1)).resolve()))

from intervals import merge_intervals


class IntervalChecks(unittest.TestCase):
    def test_nested_interval(self):
        self.assertEqual(
            merge_intervals([[1, 10], [2, 3]]),
            [[1, 10]],
        )

    def test_nested_then_overlapping(self):
        self.assertEqual(
            merge_intervals([[1, 10], [2, 3], [9, 12]]),
            [[1, 12]],
        )

    def test_same_start(self):
        self.assertEqual(
            merge_intervals([[1, 8], [1, 3]]),
            [[1, 8]],
        )

    def test_unsorted_and_touching(self):
        self.assertEqual(
            merge_intervals([[8, 9], [3, 5], [1, 3]]),
            [[1, 5], [8, 9]],
        )

    def test_empty_input(self):
        self.assertEqual(merge_intervals([]), [])

    def test_input_is_not_modified(self):
        intervals = [[5, 8], [1, 6]]
        original = [interval.copy() for interval in intervals]
        self.assertEqual(merge_intervals(intervals), [[1, 8]])
        self.assertEqual(intervals, original)


if __name__ == "__main__":
    unittest.main()
