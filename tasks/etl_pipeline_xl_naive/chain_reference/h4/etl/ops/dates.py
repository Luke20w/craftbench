"""Date ops. A date is a `YYYY-MM-DD` string naming a real calendar day."""

import datetime
import re

from etl.fields import Text, Choice, Int
from etl.steps import Op, register
from etl.ops.common import column_value, execution_error

FORMATS = {
    'iso': (re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})'), 'ymd'),
    'us': (re.compile(r'([0-9]{2})/([0-9]{2})/([0-9]{4})'), 'mdy'),
    'eu': (re.compile(r'([0-9]{2})/([0-9]{2})/([0-9]{4})'), 'dmy'),
}

def parse_date(v, fmt='iso'):
    """The date `v` holds in format `fmt`, or None if it doesn't hold one."""
    pattern, order = FORMATS[fmt]
    m = pattern.fullmatch(v) if isinstance(v, str) else None
    if m is None:
        return None
    parts = dict(zip(order, map(int, m.groups())))
    try:
        return datetime.date(parts['y'], parts['m'], parts['d'])
    except ValueError:
        return None

def date_value(step, row, key):
    """The row's date in the column named by `key` (None for null); it must exist and hold a date."""
    v = column_value(step, row, key)
    if v is None:
        return None
    d = parse_date(v)
    if d is None:
        raise execution_error(step, 'expected a YYYY-MM-DD date', key)
    return d

@register
class ToDate(Op):
    name = 'to_date'
    fields = (Text('column'), Choice('format', tuple(FORMATS), required=False, default='iso'), Text('as', required=False))

    def run(self, step, rows, ctx):
        target = step.values.get('as', step['column'])
        for r in rows:
            v = column_value(step, r)
            if v is not None:
                d = parse_date(v, step['format'])
                if d is None:
                    raise execution_error(step, 'not a %s date' % step['format'], 'column')
                v = d.isoformat()
            r[target] = v
        return rows

@register
class DateDiff(Op):
    name = 'date_diff'
    fields = (Text('start'), Text('end'), Text('as'))

    def run(self, step, rows, ctx):
        for r in rows:
            column_value(step, r, 'start')
            column_value(step, r, 'end')
            start, end = date_value(step, r, 'start'), date_value(step, r, 'end')
            r[step['as']] = None if start is None or end is None else (end - start).days
        return rows

@register
class DateAdd(Op):
    name = 'date_add'
    fields = (Text('column'), Int('days'), Text('as'))

    def run(self, step, rows, ctx):
        for r in rows:
            d = date_value(step, r, 'column')
            if d is not None:
                try:
                    d = d + datetime.timedelta(days=step['days'])
                except OverflowError:
                    raise execution_error(step, 'date out of range', 'days')
            r[step['as']] = None if d is None else d.isoformat()
        return rows
