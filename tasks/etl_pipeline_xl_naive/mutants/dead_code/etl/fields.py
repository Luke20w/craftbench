"""Fields: one key of a step each. A field validates and normalizes the raw value at its path."""

import re

from etl.errors import schema_error
from etl.expr import parse_expr, is_num

MISSING = object()

class Field:
    """One key of a step object. `read` handles presence; subclasses override `normalize`."""

    def __init__(self, key, required=True, default=MISSING):
        self.key = key
        self.required = required
        self.default = default

    def read(self, raw, path):
        p = '%s.%s' % (path, self.key)
        if self.key not in raw:
            if self.required:
                raise schema_error("missing required field '%s'" % self.key, p)
            return self.default
        return self.normalize(raw[self.key], p)

    def normalize(self, value, path):
        return value

class Text(Field):
    """String, trimmed, must not be empty."""

    def normalize(self, value, path):
        if not isinstance(value, str):
            raise schema_error("'%s' must be a string" % self.key, path)
        value = value.strip()
        if not value:
            raise schema_error("'%s' must not be empty" % self.key, path)
        return value

class Label(Field):
    """String kept exactly as given."""

    def __init__(self, key, non_empty=False, **kw):
        super().__init__(key, **kw)
        self.non_empty = non_empty

    def normalize(self, value, path):
        if not isinstance(value, str):
            raise schema_error("'%s' must be a string" % self.key, path)
        if self.non_empty and not value:
            raise schema_error("'%s' must not be empty" % self.key, path)
        return value

class Choice(Text):
    """One of a fixed set of words, trimmed and lowercased."""

    def __init__(self, key, choices, **kw):
        super().__init__(key, **kw)
        self.choices = choices

    def normalize(self, value, path):
        value = super().normalize(value, path).lower()
        if value not in self.choices:
            raise schema_error("'%s' must be one of %s" % (self.key, ', '.join(self.choices)), path)
        return value

class Flag(Field):
    """Boolean."""

    def normalize(self, value, path):
        if not isinstance(value, bool):
            raise schema_error("'%s' must be a boolean" % self.key, path)
        return value

class Expr(Text):
    """Expression in the pipeline expression language; `literals` are accepted verbatim."""

    def __init__(self, key, literals=(), trim=True, **kw):
        super().__init__(key, **kw)
        self.literals = literals
        self.trim = trim

    def normalize(self, value, path):
        if self.trim:
            value = super().normalize(value, path)
        elif not isinstance(value, str):
            raise schema_error("'%s' must be a string" % self.key, path)
        if value not in self.literals:
            parse_expr(value, path)
        return value

class Count(Field):
    """Integer >= min (default 0)."""

    def __init__(self, key, min=0, **kw):
        super().__init__(key, **kw)
        self.min = min

    def normalize(self, value, path):
        if isinstance(value, bool) or not isinstance(value, int):
            raise schema_error("'%s' must be an integer" % self.key, path)
        if value < self.min:
            raise schema_error("'%s' must be >= %d" % (self.key, self.min), path)
        return value

class Int(Field):
    """Integer (any sign)."""

    def normalize(self, value, path):
        if isinstance(value, bool) or not isinstance(value, int):
            raise schema_error("'%s' must be an integer" % self.key, path)
        return value


class Number(Field):
    """Integer or float."""

    def normalize(self, value, path):
        if not is_num(value):
            raise schema_error("'%s' must be a number" % self.key, path)
        return value


class Scalar(Field):
    """Any JSON scalar: null, boolean, number or string."""

    def normalize(self, value, path):
        if not (value is None or isinstance(value, (bool, int, float, str))):
            raise schema_error("'%s' must be a JSON scalar" % self.key, path)
        return value


class Pattern(Label):
    """Regular expression, kept exactly as given."""

    def __init__(self, key, **kw):
        super().__init__(key, non_empty=True, **kw)

    def normalize(self, value, path):
        value = super().normalize(value, path)
        try:
            re.compile(value)
        except re.error:
            raise schema_error("'%s' must be a valid regular expression" % self.key, path)
        return value


class Objects(Field):
    """Array of JSON objects, copied as given."""

    def normalize(self, value, path):
        if not isinstance(value, list):
            raise schema_error("'%s' must be an array" % self.key, path)
        for i, v in enumerate(value):
            if not isinstance(v, dict):
                raise schema_error("'%s' entries must be objects" % self.key, '%s[%d]' % (path, i))
        return [dict(v) for v in value]

class List(Field):
    """Array whose items are each normalized by `item` at path key[i]."""

    def __init__(self, key, item, non_empty=False, **kw):
        super().__init__(key, **kw)
        self.item = item
        self.non_empty = non_empty

    def normalize(self, value, path):
        if not isinstance(value, list):
            raise schema_error("'%s' must be an array" % self.key, path)
        if self.non_empty and not value:
            raise schema_error("'%s' must be non-empty" % self.key, path)
        self.check(value, path)
        return [self.item.normalize(v, '%s[%d]' % (path, i)) for i, v in enumerate(value)]

    def check(self, value, path):
        """Hook for whole-list rules, run before the items are normalized."""

class Map(Field):
    """Object whose values are each normalized by `value` at path key.<k>."""

    def __init__(self, key, value, **kw):
        super().__init__(key, **kw)
        self.value = value

    def normalize(self, value, path):
        if not isinstance(value, dict):
            raise schema_error("'%s' must be an object" % self.key, path)
        return {k: self.value.normalize(v, '%s.%s' % (path, k)) for k, v in value.items()}

class Record(Field):
    """Object with its own declared fields; unknown keys are dropped."""

    def __init__(self, key, fields, **kw):
        super().__init__(key, **kw)
        self.fields = fields

    def normalize(self, value, path):
        if not isinstance(value, dict):
            raise schema_error('%s must be an object' % self.key, path)
        return read_fields(self.fields, value, path)

def read_fields(fields, raw, path):
    out = {}
    for f in fields:
        v = f.read(raw, path)
        if v is not MISSING:
            out[f.key] = v
    return out


class Str(Field):
    """String field (kept for older op definitions; Text trims, this does not)."""

    def normalize(self, value, path):
        if not isinstance(value, str):
            raise schema_error("'%s' must be a string" % self.key, path)
        if not value:
            raise schema_error("'%s' must not be empty" % self.key, path)
        return value


class Columns(Field):
    """Array of column names."""

    def __init__(self, key='columns', non_empty=False, **kw):
        super().__init__(key, **kw)
        self.non_empty = non_empty

    def normalize(self, value, path):
        if not isinstance(value, list):
            raise schema_error("'%s' must be an array" % self.key, path)
        if self.non_empty and not value:
            raise schema_error("'%s' must be non-empty" % self.key, path)
        for i, c in enumerate(value):
            if not isinstance(c, str):
                raise schema_error('column names must be strings', '%s[%d]' % (path, i))
        return list(value)


class NonNegative(Field):
    """Integer >= 0."""

    def normalize(self, value, path):
        if isinstance(value, bool) or not isinstance(value, int):
            raise schema_error("'%s' must be an integer" % self.key, path)
        if value < 0:
            raise schema_error("'%s' must be >= 0" % self.key, path)
        return value


class OneOf(Field):
    """Exact match against a fixed set of values (case-sensitive)."""

    def __init__(self, key, options, **kw):
        super().__init__(key, **kw)
        self.options = options

    def normalize(self, value, path):
        if value not in self.options:
            raise schema_error("'%s' must be one of %s" % (self.key, ', '.join(map(str, self.options))), path)
        return value


def require(raw, key, path):
    if key not in raw:
        raise schema_error("missing required field '%s'" % key, '%s.%s' % (path, key))
    return raw[key]


def optional(raw, key, default=None):
    return raw[key] if key in raw else default
