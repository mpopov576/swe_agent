from options import get_option


def build_config(settings):
    return {
        "retries": get_option(settings, "retries", 3),
        "enabled": get_option(settings, "enabled", True),
        "prefix": get_option(settings, "prefix", "app"),
    }
