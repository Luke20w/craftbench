"""Ops that add, remove or reshape columns."""

import json

from etl.expr import is_num
from etl.fields import Text, Label, Choice, Expr, Scalar, List, Map
from etl.steps import ANY, Op, register
from etl.types import Known
from etl.ops.common import column_values, column_value, execution_error, to_text

@register
class Drop(Op):
    name = 'drop'
    reads = removes = ('columns',)
    fields = (List('columns', Label('column names')),)

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        return [{k: v for k, v in r.items() if k not in cols} for r in rows]

@register
class Fill(Op):
    name = 'fill'
    reads = writes = ('column',)
    exprs = ('value',)
    fields = (Text('column'), Expr('value'))

    def run(self, step, rows, ctx):
        for r in rows:
            if r.get(step['column']) is None:
                r[step['column']] = ctx.eval(step, step['value'], r, 'value')
        return rows

@register
class Cast(Op):
    name = 'cast'
    reads = writes = ('column',)
    fields = (Text('column'), Choice('to', ('int', 'float', 'string', 'bool')))
    # the types each target can convert from, and the type it gives
    CAST_TYPES = {'int': ('number', 'string'), 'float': ('number', 'string'),
                  'string': ('number', 'string', 'boolean', 'array', 'object'), 'bool': ('boolean', 'string', 'number')}
    RESULT_TYPES = {'int': 'number', 'float': 'number', 'string': 'string', 'bool': 'boolean'}

    def typed_columns(self, step):
        yield step['column'], self.CAST_TYPES[step['to']], ('column',)

    def retype(self, step, known):
        known = super().retype(step, known)
        known[step['column']] = Known(self.RESULT_TYPES[step['to']])
        return known

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
    writes, exprs = ('as',), ('exprs',)
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
    reads = writes = ('column',)
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
    reads, writes = ('column',), ('as',)
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
    writes = ('column',)
    fields = (Text('column'), Scalar('value'),)

    def run(self, step, rows, ctx):
        for r in rows:
            r[step['column']] = step['value']
        return rows

@register
class Ensure(Op):
    name = 'ensure'
    reads = writes = ('columns',)
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
    reads = ('columns',)
    fields = (List('columns', Label('column names'), non_empty=True),)

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        return [dict([(c, r[c]) for c in cols] + [(k, v) for k, v in r.items() if k not in cols]) for r in rows]

@register
class Prefix(Op):
    name = 'prefix'
    fields = (Label('prefix', non_empty=True), List('columns', Label('column names'), required=False),)

    def columns(self, step):
        if 'columns' not in step.values:
            return [ANY], [ANY], [ANY]
        return step['columns'], [step['prefix'] + c for c in step['columns']], step['columns']

    def run(self, step, rows, ctx):
        for k, r in enumerate(rows):
            targets = step['columns'] if 'columns' in step.values else list(r)
            rows[k] = {(step['prefix'] + c if c in targets else c): v for c, v in r.items()}
        return rows

@register
class Nest(Op):
    name = 'nest'
    reads = removes = ('columns',)
    writes = ('as',)
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
    accepts = {'column': ('object',)}
    reads = removes = ('column',)
    writes = (ANY,)
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
