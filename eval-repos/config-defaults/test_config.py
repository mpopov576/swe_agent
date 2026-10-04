from config import build_config


def test_missing_options_use_defaults():
    assert build_config({}) == {
        "retries": 3,
        "enabled": True,
        "prefix": "app",
    }
