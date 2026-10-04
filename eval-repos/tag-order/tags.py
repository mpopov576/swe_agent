def normalize_tags(tags):
    cleaned = (tag.strip().lower() for tag in tags)
    return sorted({tag for tag in cleaned if tag})
