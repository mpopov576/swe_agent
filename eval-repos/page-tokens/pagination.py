def get_page(items, page_size, token=None):
    if page_size <= 0:
        raise ValueError("Page size must be positive")

    start = 0 if token is None else int(token)
    if start < 0:
        raise ValueError("Token must be nonnegative")

    end = start + page_size
    return {
        "items": items[start:end],
        "next_token": str(end),
    }
