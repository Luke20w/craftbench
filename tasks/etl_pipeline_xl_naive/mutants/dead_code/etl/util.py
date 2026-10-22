"""Small row and value helpers."""

import json

from etl.expr import is_num


def row_key(row, columns=None):
    """Stable JSON key for a row, or for some of its columns."""
    if columns is None:
        return json.dumps(row, sort_keys=True)
    return json.dumps([row.get(c) for c in columns])


def pluck(rows, column):
    return [r.get(column) for r in rows]


def chunked(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def flatten(row, sep='.', prefix=''):
    out = {}
    for k, v in row.items():
        name = prefix + k
        if isinstance(v, dict):
            out.update(flatten(v, sep, name + sep))
        else:
            out[name] = v
    return out


def deep_merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def coerce_number(v):
    if is_num(v):
        return v
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return None
    return None
