from tags import normalize_tags


def test_normalization():
    assert normalize_tags([" Python ", "PYTHON", ""]) == ["python"]
