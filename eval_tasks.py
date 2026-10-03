TASKS = [
    {
        "name": "tag-order",
        "checker": "check_tag_order.py",
        "issue": (
            "normalize_tags should strip whitespace, lowercase tags, remove "
            "blank tags, and remove duplicates while preserving the order of "
            "their first appearance. It currently changes that order. Fix "
            "this behavior without modifying the caller's input."
        ),
    },
    {
        "name": "merge-intervals",
        "checker": "check_merge_intervals.py",
        "issue": (
            "Fix merge_intervals so it returns the union of overlapping or "
            "touching closed intervals, sorted by start. Nested intervals "
            "must not shorten an existing interval. Return a list of "
            "[start, end] lists without modifying the input. Inputs contain "
            "valid numeric intervals with start <= end."
        ),
    },
    {
        "name": "config-defaults",
        "checker": "check_config_defaults.py",
        "issue": (
            "Configuration loading incorrectly replaces explicitly supplied "
            "values with defaults. Fix get_option and its use by build_config "
            "so defaults apply only when a key is missing or its value is "
            "None. Preserve all other supplied values, including 0, False, "
            "empty strings, and empty collections. Do not modify the input "
            "settings."
        ),
    },
    {
        "name": "inventory",
        "checker": "check_inventory.py",
        "issue": (
            "Fix reserve(stock, item, quantity). For a positive integer "
            "quantity, reserve stock and return True only when enough units "
            "exist. Otherwise return False and leave the entire stock "
            "dictionary unchanged, including when the item is missing. "
            "Successful reservations must decrement only the requested item, "
            "retaining its key at zero. Nonpositive quantities must raise "
            "ValueError without changing stock. Stock values are nonnegative "
            "integers."
        ),
    },
    {
        "name": "page-tokens",
        "checker": "check_page_tokens.py",
        "issue": (
            "Fix get_page so next_token is a string offset only when more "
            "items remain after the returned page; otherwise it must be None. "
            "This includes empty inputs, full and partial final pages, and "
            "offsets at or beyond the end. Preserve item order and do not "
            "modify the input list. Tokens are None or strings representing "
            "integer offsets. Keep ValueError for nonpositive integer page "
            "sizes and negative offsets."
        ),
    },
    {
        "name": "csv-output",
        "checker": "check_csv_output.py",
        "issue": (
            "Fix encode_row(fields) to serialize a list of strings as one "
            "valid comma-separated CSV record ending in CRLF. Preserve field "
            "contents exactly, including commas, double quotes, carriage "
            "returns, line feeds, Unicode, and empty strings. Embedded double "
            "quotes must be doubled within quoted fields. Distinguish a single "
            "empty field from a row containing no fields. Do not modify the "
            "input list. Standard-library solutions are allowed."
        ),
    },
]