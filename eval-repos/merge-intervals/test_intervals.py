from intervals import merge_intervals


def test_overlapping_intervals():
    assert merge_intervals([[1, 3], [2, 5]]) == [[1, 5]]
