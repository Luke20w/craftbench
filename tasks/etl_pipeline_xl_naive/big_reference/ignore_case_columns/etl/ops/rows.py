"""Ops that filter, order or add rows."""

import json

from etl.expr import is_num, truthy, num_result
from etl.fields import Text, Label, Flag, Expr, Count, Int, Scalar, Objects, List
from etl.steps import Op, register
from etl.options import match
from etl.ops.common import execution_error

@register
class Distinct(Op):
    name = 'distinct'
    fields = (List('columns', Label('column names'), required=False),)

    def run(self, step, rows, ctx):
        seen, out = set(), []
        for r in rows:
            if 'columns' in step.values:
                key = json.dumps([r.get(match(r, c)) for c in step['columns']])
            else:
                key = json.dumps(r, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

TYPE_ORDER = ((lambda v: is_num(v), 0), (lambda v: isinstance(v, str), 1), (lambda v: isinstance(v, bool), 2))

@register
class Sort(Op):
    name = 'sort'
    fields = (Text('by'), Flag('desc', required=False, default=False))

    def run(self, step, rows, ctx):
        value = lambda r: r.get(match(r, step['by']))
        present = [r for r in rows if value(r) is not None]
        nulls = [r for r in rows if value(r) is None]
        return sorted(present, key=lambda r: self.key(step, value(r)), reverse=step['desc']) + nulls

    def key(self, step, v):
        for test, rank in TYPE_ORDER:
            if test(v):
                return (rank, v)
        raise execution_error(step, 'cannot sort by a %s value' % type(v).__name__, 'by')

@register
class Offset(Op):
    name = 'offset'
    fields = (Count('n'),)

    def run(self, step, rows, ctx):
        return rows[step['n']:]

@register
class Tail(Op):
    name = 'tail'
    fields = (Count('n'),)

    def run(self, step, rows, ctx):
        return rows[max(0, len(rows) - step['n']):] if step['n'] else []

@register
class Assert(Op):
    name = 'assert'
    fields = (Expr('where'), Label('message', required=False, default='assertion failed'))

    def run(self, step, rows, ctx):
        for r in rows:
            if not truthy(ctx.eval(step, step['where'], r, 'where')):
                raise execution_error(step, step['message'], 'where')
        return rows

@register
class SampleEvery(Op):
    name = 'sample_every'
    fields = (Count('n', min=1),)

    def run(self, step, rows, ctx):
        return rows[::step['n']]

@register
class TakeWhile(Op):
    name = 'take_while'
    fields = (Expr('where'),)

    def run(self, step, rows, ctx):
        out = []
        for r in rows:
            if not truthy(ctx.eval(step, step['where'], r, 'where')):
                break
            out.append(r)
        return out

@register
class SkipWhile(Op):
    name = 'skip_while'
    fields = (Expr('where'),)

    def run(self, step, rows, ctx):
        out = []
        skipping = True
        for r in rows:
            if skipping and truthy(ctx.eval(step, step['where'], r, 'where')):
                continue
            skipping = False
            out.append(r)
        return out

@register
class Append(Op):
    name = 'append'
    fields = (Objects('rows'),)

    def run(self, step, rows, ctx):
        return rows + [dict(x) for x in step['rows']]

@register
class Require(Op):
    name = 'require'
    fields = (List('columns', Label('column names'), non_empty=True),)

    def run(self, step, rows, ctx):
        for r in rows:
            for j, c in enumerate(step['columns']):
                if r.get(match(r, c)) is None:
                    raise execution_error(step, "column '%s' is required" % c, 'columns', j)
        return rows

@register
class RowNumber(Op):
    name = 'row_number'
    fields = (Text('as'), Int('start', required=False, default=1),)

    def run(self, step, rows, ctx):
        for k, r in enumerate(rows):
            r[match(r, step['as'])] = step['start'] + k
        return rows

@register
class Rank(Op):
    name = 'rank'
    fields = (Text('by'), Text('as'), Flag('desc', required=False, default=False),)

    def run(self, step, rows, ctx):
        distinct = []
        for r in rows:
            v = r.get(match(r, step['by']))
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'rank requires numbers', 'by')
            if v not in distinct:
                distinct.append(v)
        distinct.sort(reverse=step['desc'])
        for r in rows:
            v = r.get(match(r, step['by']))
            r[match(r, step['as'])] = None if v is None else distinct.index(v) + 1
        return rows

@register
class CumSum(Op):
    name = 'cumsum'
    fields = (Text('column'), Text('as'),)

    def run(self, step, rows, ctx):
        total = 0
        for r in rows:
            v = r.get(match(r, step['column']))
            if v is not None and not is_num(v):
                raise execution_error(step, 'cumsum requires numbers', 'column')
            total = num_result(total + (v or 0))
            r[match(r, step['as'])] = total
        return rows

@register
class Lag(Op):
    name = 'lag'
    fields = (Text('column'), Text('as'), Count('n', required=False, default=1), Scalar('default', required=False),)

    def run(self, step, rows, ctx):
        values = [r.get(match(r, step['column'])) for r in rows]
        for k, r in enumerate(rows):
            if k >= step['n']:
                r[match(r, step['as'])] = values[k - step['n']]
            else:
                r[match(r, step['as'])] = step['default'] if 'default' in step.values else None
        return rows
