from pagination import get_page


def test_first_page():
    assert get_page([1, 2, 3], 2) == {
        "items": [1, 2],
        "next_token": "2",
    }
