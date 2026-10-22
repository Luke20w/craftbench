"""Ops that add, remove or reshape columns."""

import json

from etl.expr import is_num
from etl.fields import Text, Label, Choice, Expr, Scalar, List, Map
from etl.steps import Op, register
from etl.ops.common import column_values, column_value, execution_error, to_text

@register
class Drop(Op):
    name = 'drop'
    fields = (List('columns', Label('column names')),)

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        return [{k: v for k, v in r.items() if k not in cols} for r in rows]

@register
class Fill(Op):
    name = 'fill'
    fields = (Text('column'), Expr('value'))

    def run(self, step, rows, ctx):
        for r in rows:
            if r.get(step['column']) is None:
                r[step['column']] = ctx.eval(step, step['value'], r, 'value')
        return rows

@register
class Cast(Op):
    name = 'cast'
    fields = (Text('column'), Choice('to', ('int', 'float', 'string', 'bool')))

    def run(self, step, rows, ctx):
        convert = getattr(self, 'to_' + step['to'])
        for r in rows:
            v = column_value(step, r)
            if v is not None:
                try:
                    r[step['column']] = convert(v)
                except (TypeError, ValueError):
                    raise execution_error(step, 'cannot cast %s to %s' % (json.dumps(v), step['to']), 'column')
        return rows

    def to_int(self, v):
        if isinstance(v, bool):
            raise TypeError
        return int(v)

    def to_float(self, v):
        if isinstance(v, bool):
            raise TypeError
        return float(v)

    def to_string(self, v):
        return to_text(v)

    def to_bool(self, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str) and v.strip().lower() in ('true', 'false'):
            return v.strip().lower() == 'true'
        if is_num(v):
            return v != 0
        raise ValueError

@register
class Coalesce(Op):
    name = 'coalesce'
    fields = (Text('as'), List('exprs', Expr('exprs entries'), non_empty=True))

    def run(self, step, rows, ctx):
        for r in rows:
            value = None
            for k, expr in enumerate(step['exprs']):
                value = ctx.eval(step, expr, r, 'exprs', k)
                if value is not None:
                    break
            r[step['as']] = value
        return rows

@register
class Explode(Op):
    name = 'explode'
    fields = (Text('column'),)

    def run(self, step, rows, ctx):
        out = []
        for r in rows:
            v = column_value(step, r)
            if isinstance(v, list):
                out.extend(dict(r, **{step['column']: x}) for x in v)
            else:
                out.append(r)
        return out

@register
class Lookup(Op):
    name = 'lookup'
    fields = (Text('column'), Text('as'), Map('table', Scalar('table values')), Scalar('default', required=False),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            key = v if isinstance(v, str) else json.dumps(v)
            if key in step['table']:
                r[step['as']] = step['table'][key]
            else:
                r[step['as']] = step['default'] if 'default' in step.values else None
        return rows

@register
class SetOp(Op):
    name = 'set'
    fields = (Text('column'), Scalar('value'),)

    def run(self, step, rows, ctx):
        for r in rows:
            r[step['column']] = step['value']
        return rows

@register
class Ensure(Op):
    name = 'ensure'
    fields = (List('columns', Label('column names'), non_empty=True), Scalar('value', required=False, default=None),)

    def run(self, step, rows, ctx):
        for r in rows:
            for c in step['columns']:
                if c not in r:
                    r[c] = step['value']
        return rows

@register
class Reorder(Op):
    name = 'reorder'
    fields = (List('columns', Label('column names'), non_empty=True),)

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        return [dict([(c, r[c]) for c in cols] + [(k, v) for k, v in r.items() if k not in cols]) for r in rows]

@register
class Prefix(Op):
    name = 'prefix'
    fields = (Label('prefix', non_empty=True), List('columns', Label('column names'), required=False),)

    def run(self, step, rows, ctx):
        for k, r in enumerate(rows):
            targets = step['columns'] if 'columns' in step.values else list(r)
            rows[k] = {(step['prefix'] + c if c in targets else c): v for c, v in r.items()}
        return rows

@register
class Nest(Op):
    name = 'nest'
    fields = (List('columns', Label('column names'), non_empty=True), Text('as'),)

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        out = []
        for r in rows:
            nr = {k: v for k, v in r.items() if k not in cols}
            nr[step['as']] = {c: r[c] for c in cols}
            out.append(nr)
        return out

@register
class Unnest(Op):
    name = 'unnest'
    fields = (Text('column'), Label('prefix', required=False, default=''),)

    def run(self, step, rows, ctx):
        out = []
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, dict):
                raise execution_error(step, 'unnest requires an object', 'column')
            nr = {k: x for k, x in r.items() if k != step['column']}
            for k, x in (v or {}).items():
                nr[step['prefix'] + k] = x
            out.append(nr)
        return out


class CastV1(Op):
    """Cast with a fixed conversion table; replaced by Cast's to_* methods."""
    name = 'cast'
    fields = (Text('column'), Choice('to', ('int', 'float', 'string')))
    CONVERT = {'int': int, 'float': float, 'string': str}

    def run(self, step, rows, ctx):
        convert = self.CONVERT[step['to']]
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            try:
                r[step['column']] = convert(v)
            except (TypeError, ValueError):
                raise execution_error(step, 'cannot cast %s to %s' % (json.dumps(v), step['to']), 'column')
        return rows


class Default(Op):
    """Old name for fill with a constant value."""
    name = 'default'
    fields = (Text('column'), Scalar('value'))

    def run(self, step, rows, ctx):
        for r in rows:
            if r.get(step['column']) is None:
                r[step['column']] = step['value']
        return rows


def lookup_key(v):
    return v if isinstance(v, str) else json.dumps(v)
