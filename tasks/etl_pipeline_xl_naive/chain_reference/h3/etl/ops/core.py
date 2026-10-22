"""Core ops: select, filter, map, rename, limit, branch."""

from etl.errors import EtlError, schema_error
from etl.expr import truthy
from etl.fields import Field, Text, Label, Expr, Count, List, Map, Record, read_fields
from etl.steps import Op, register, StepList

@register
class Select(Op):
    name = 'select'
    fields = (List('columns', Label('column names')),)

    def run(self, step, rows, ctx):
        cols = step['columns']
        for r in rows:
            for j, c in enumerate(cols):
                if c not in r:
                    raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c,
                                   step.at('columns', j))
        return [{c: r[c] for c in cols} for r in rows]

@register
class Filter(Op):
    name = 'filter'
    fields = (Expr('where'),)

    def run(self, step, rows, ctx):
        return [r for r in rows if truthy(ctx.eval(step, step['where'], r, 'where'))]

@register
class MapOp(Op):
    name = 'map'
    fields = (Text('as'), Expr('expr'))

    def run(self, step, rows, ctx):
        for r in rows:
            r[step['as']] = ctx.eval(step, step['expr'], r, 'expr')
        return rows

@register
class Rename(Op):
    name = 'rename'

    def keys(self):
        return ['from', 'to', 'mapping']

    def normalize(self, raw, path):
        if 'mapping' in raw:
            return read_fields((Map('mapping', Label('mapping values')),), raw, path)
        if 'from' in raw or 'to' in raw:
            v = read_fields((Text('from'), Text('to')), raw, path)
            return {'mapping': {v['from']: v['to']}} if len(v) == 2 else v
        raise schema_error("rename requires 'from' and 'to' or 'mapping'", path)

    def run(self, step, rows, ctx):
        for src, dst in step['mapping'].items():
            path = step.at('from') if 'mapping' not in step.raw else step.at('mapping', src)
            out = []
            for r in rows:
                if src not in r:
                    raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % src, path)
                out.append({(dst if k == src else k): v for k, v in r.items() if k != dst or k == src})
            rows = out
        return rows

@register
class Limit(Op):
    name = 'limit'
    fields = (Count('n'),)

    def run(self, step, rows, ctx):
        return rows[:step['n']]

class Branches(List):
    """branch.branches: at most one 'otherwise', and it must be last."""

    def check(self, value, path):
        flags = [isinstance(b, dict) and b.get('when') == 'otherwise' for b in value]
        if sum(flags) > 1:
            raise EtlError('MALFORMED_STEP', "ETL_ERROR: at most one 'otherwise' branch allowed", path)
        if any(flags[:-1]):
            raise EtlError('MALFORMED_STEP', "ETL_ERROR: 'otherwise' branch must be last", path)

class MergeStrategy(Field):

    def normalize(self, value, path):
        if value != 'concat':
            raise schema_error("only 'concat' merge strategy is supported", path)
        return value

@register
class Branch(Op):
    name = 'branch'
    fields = (
        Branches('branches', Record('branch', (
            Expr('when', literals=('otherwise',), trim=False),
            StepList('steps'),
            Label('id', required=False),
        )), non_empty=True),
        Record('merge', (MergeStrategy('strategy', required=False, default='concat'),),
               required=False, default={'strategy': 'concat'}),
    )

    def run(self, step, rows, ctx):
        branches = step['branches']
        routed = [[] for _ in branches]
        for row in rows:
            for j, b in enumerate(branches):
                if b['when'] == 'otherwise' or truthy(ctx.eval(step, b['when'], row, 'branches', j, 'when')):
                    routed[j].append(row)
                    break
        out = []
        for b, part in zip(branches, routed):
            if part:
                out.extend(ctx.run(b['steps'], [dict(r) for r in part]))
        return out
