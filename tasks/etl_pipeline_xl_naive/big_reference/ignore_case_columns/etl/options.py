"""Request options that change how every step finds columns; set once per request (see etl/request.py)."""

OPTIONS = {'ignore_case_columns': False}


def match(row, name):
    """The row's key that the column name `name` refers to: `name` itself, or with ignore_case_columns the
    first key equal to it ignoring case (an exact spelling wins). `name` when no key matches."""
    if name in row or not OPTIONS['ignore_case_columns']:
        return name
    low = name.lower()
    return next((k for k in row if k.lower() == low), name)


def same(key, name):
    """Does row key `key` refer to the same column as `name`?"""
    return key == name or (OPTIONS['ignore_case_columns'] and key.lower() == name.lower())
