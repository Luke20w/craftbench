"""String ops."""

import json
import re

from etl.fields import Text, Label, Choice, Flag, Count, Pattern, List
from etl.steps import Op, register
from etl.options import match
from etl.ops.common import column_values, column_value, execution_error, to_text

@register
class Concat(Op):
    name = 'concat'
    fields = (Text('as'), List('columns', Label('column names'), non_empty=True), Label('sep', required=False, default=''))

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        for r in rows:
            values = [r[match(r, c)] for c in cols]
            r[match(r, step['as'])] = step['sep'].join('' if v is None else to_text(v) for v in values)
        return rows

@register
class Split(Op):
    name = 'split'
    fields = (Text('column'), Label('sep', non_empty=True), List('into', Label('column names'), non_empty=True))

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, str):
                raise execution_error(step, 'split requires a string', 'column')
            parts = v.split(step['sep']) if v is not None else []
            for i, name in enumerate(step['into']):
                r[match(r, name)] = parts[i] if i < len(parts) else None
        return rows

@register
class TextOp(Op):
    name = 'text'
    fields = (List('columns', Label('column names')), Choice('fn', ('upper', 'lower', 'trim')))

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        fn = {'upper': str.upper, 'lower': str.lower, 'trim': str.strip}[step['fn']]
        for r in rows:
            for j, c in enumerate(cols):
                key = match(r, c)
                if r[key] is None:
                    continue
                if not isinstance(r[key], str):
                    raise execution_error(step, 'text requires a string', 'columns', j)
                r[key] = fn(r[key])
        return rows

@register
class Replace(Op):
    name = 'replace'
    fields = (Text('column'), Label('find', non_empty=True), Label('with'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not isinstance(v, str):
                raise execution_error(step, 'replace requires a string', 'column')
            r[match(r, step['column'])] = v.replace(step['find'], step['with'])
        return rows

@register
class RegexExtract(Op):
    name = 'regex_extract'
    fields = (Text('column'), Pattern('pattern'), Text('as'), Count('group', required=False, default=0),)

    def run(self, step, rows, ctx):
        rx = re.compile(step['pattern'])
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, str):
                raise execution_error(step, 'regex_extract requires a string', 'column')
            m = rx.search(v) if v is not None else None
            if m is not None and step['group'] > rx.groups:
                raise execution_error(step, 'pattern has no group %d' % step['group'], 'group')
            r[match(r, step['as'])] = m.group(step['group']) if m else None
        return rows

@register
class RegexFilter(Op):
    name = 'regex_filter'
    fields = (Text('column'), Pattern('pattern'), Flag('invert', required=False, default=False),)

    def run(self, step, rows, ctx):
        rx = re.compile(step['pattern'])
        out = []
        for r in rows:
            v = r.get(match(r, step['column']))
            if (isinstance(v, str) and rx.search(v) is not None) != step['invert']:
                out.append(r)
        return out

@register
class Substr(Op):
    name = 'substr'
    fields = (Text('column'), Text('as'), Count('start'), Count('length', required=False),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, str):
                raise execution_error(step, 'substr requires a string', 'column')
            if v is None:
                out = None
            elif 'length' in step.values:
                out = v[step['start']:step['start'] + step['length']]
            else:
                out = v[step['start']:]
            r[match(r, step['as'])] = out
        return rows

@register
class Pad(Op):
    name = 'pad'
    fields = (Text('column'), Count('width'), Label('fill', non_empty=True, required=False, default=' '), Choice('side', ('left', 'right'), required=False, default='left'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            s = to_text(v)
            short = max(0, step['width'] - len(s))
            padding = (step['fill'] * short)[:short]
            r[match(r, step['column'])] = padding + s if step['side'] == 'left' else s + padding
        return rows

@register
class Length(Op):
    name = 'length'
    fields = (Text('column'), Text('as'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, (str, list, dict)):
                raise execution_error(step, 'length requires a string, array or object', 'column')
            r[match(r, step['as'])] = None if v is None else len(v)
        return rows

@register
class JsonParse(Op):
    name = 'json_parse'
    fields = (Text('column'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not isinstance(v, str):
                raise execution_error(step, 'json_parse requires a string', 'column')
            try:
                r[match(r, step['column'])] = json.loads(v)
            except ValueError:
                raise execution_error(step, 'invalid JSON text', 'column')
        return rows

@register
class JsonDump(Op):
    name = 'json_dump'
    fields = (Text('column'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None:
                r[match(r, step['column'])] = json.dumps(v, sort_keys=True)
        return rows

@register
class DatePart(Op):
    name = 'date_part'
    fields = (Text('column'), Choice('part', ('year', 'month', 'day')), Text('as'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                r[match(r, step['as'])] = None
                continue
            m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', v) if isinstance(v, str) else None
            if m is None:
                raise execution_error(step, 'expected a YYYY-MM-DD date', 'column')
            r[match(r, step['as'])] = int(m.group(('year', 'month', 'day').index(step['part']) + 1))
        return rows
