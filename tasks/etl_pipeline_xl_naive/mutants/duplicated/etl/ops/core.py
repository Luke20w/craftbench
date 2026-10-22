"""Core ops: select, filter, map, rename, limit, branch."""

from etl.errors import EtlError, schema_error
from etl.expr import truthy, parse_expr
from etl.steps import Op, register, Step

@register
class Select(Op):
    name = 'select'

    def normalize(self, raw, path):
        out = {}
        p = path + '.columns'
        if 'columns' not in raw:
            raise schema_error("missing required field 'columns'", p)
        columns = raw['columns']
        if not isinstance(columns, list):
            raise schema_error("'columns' must be an array", p)
        for i, item in enumerate(columns):
            if not isinstance(item, str):
                raise schema_error("'column names' must be a string", '%s[%d]' % (p, i))
        columns = list(columns)
        out['columns'] = columns
        return out

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

    def normalize(self, raw, path):
        out = {}
        p = path + '.where'
        if 'where' not in raw:
            raise schema_error("missing required field 'where'", p)
        where = raw['where']
        if not isinstance(where, str):
            raise schema_error("'where' must be a string", p)
        where = where.strip()
        if not where:
            raise schema_error("'where' must not be empty", p)
        parse_expr(where, p)
        out['where'] = where
        return out

    def run(self, step, rows, ctx):
        return [r for r in rows if truthy(ctx.eval(step, step['where'], r, 'where'))]

@register
class MapOp(Op):
    name = 'map'

    def normalize(self, raw, path):
        out = {}
        p = path + '.as'
        if 'as' not in raw:
            raise schema_error("missing required field 'as'", p)
        as_ = raw['as']
        if not isinstance(as_, str):
            raise schema_error("'as' must be a string", p)
        as_ = as_.strip()
        if not as_:
            raise schema_error("'as' must not be empty", p)
        out['as'] = as_
        p = path + '.expr'
        if 'expr' not in raw:
            raise schema_error("missing required field 'expr'", p)
        expr = raw['expr']
        if not isinstance(expr, str):
            raise schema_error("'expr' must be a string", p)
        expr = expr.strip()
        if not expr:
            raise schema_error("'expr' must not be empty", p)
        parse_expr(expr, p)
        out['expr'] = expr
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            r[step['as']] = ctx.eval(step, step['expr'], r, 'expr')
        return rows

@register
class Rename(Op):
    name = 'rename'

    def normalize(self, raw, path):
        if 'mapping' in raw:
            p = path + '.mapping'
            mapping = raw['mapping']
            if not isinstance(mapping, dict):
                raise schema_error("'mapping' must be an object", p)
            for name, target in mapping.items():
                if not isinstance(target, str):
                    raise schema_error("'mapping values' must be a string", '%s.%s' % (p, name))
            return {'mapping': dict(mapping)}
        if 'from' in raw or 'to' in raw:
            p = path + '.from'
            if 'from' not in raw:
                raise schema_error("missing required field 'from'", p)
            src = raw['from']
            if not isinstance(src, str):
                raise schema_error("'from' must be a string", p)
            src = src.strip()
            if not src:
                raise schema_error("'from' must not be empty", p)
            p = path + '.to'
            if 'to' not in raw:
                raise schema_error("missing required field 'to'", p)
            dst = raw['to']
            if not isinstance(dst, str):
                raise schema_error("'to' must be a string", p)
            dst = dst.strip()
            if not dst:
                raise schema_error("'to' must not be empty", p)
            return {'mapping': {src: dst}}
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

    def normalize(self, raw, path):
        out = {}
        p = path + '.n'
        if 'n' not in raw:
            raise schema_error("missing required field 'n'", p)
        n = raw['n']
        if isinstance(n, bool) or not isinstance(n, int):
            raise schema_error("'n' must be an integer", p)
        if n < 0:
            raise schema_error("'n' must be >= 0", p)
        out['n'] = n
        return out

    def run(self, step, rows, ctx):
        return rows[:step['n']]

@register
class Branch(Op):
    name = 'branch'

    def normalize(self, raw, path):
        out = {}
        p = path + '.branches'
        if 'branches' not in raw:
            raise schema_error("missing required field 'branches'", p)
        branches = raw['branches']
        if not isinstance(branches, list):
            raise schema_error("'branches' must be an array", p)
        if not branches:
            raise schema_error("'branches' must be non-empty", p)
        flags = [isinstance(b, dict) and b.get('when') == 'otherwise' for b in branches]
        if sum(flags) > 1:
            raise EtlError('MALFORMED_STEP', "ETL_ERROR: at most one 'otherwise' branch allowed", p)
        if any(flags[:-1]):
            raise EtlError('MALFORMED_STEP', "ETL_ERROR: 'otherwise' branch must be last", p)
        items = []
        for i, b in enumerate(branches):
            bp = '%s[%d]' % (p, i)
            if not isinstance(b, dict):
                raise schema_error('branch must be an object', bp)
            branch = {}
            p2 = bp + '.when'
            if 'when' not in b:
                raise schema_error("missing required field 'when'", p2)
            when = b['when']
            if not isinstance(when, str):
                raise schema_error("'when' must be a string", p2)
            if when not in ('otherwise',):
                parse_expr(when, p2)
            branch['when'] = when
            p2 = bp + '.steps'
            if 'steps' not in b:
                raise schema_error("missing required field 'steps'", p2)
            steps = b['steps']
            if not isinstance(steps, list):
                raise schema_error("'steps' must be an array", p2)
            branch['steps'] = [Step.parse(s, '%s[%d]' % (p2, k)) for k, s in enumerate(steps)]
            p2 = bp + '.id'
            if 'id' in b:
                id_ = b['id']
                if not isinstance(id_, str):
                    raise schema_error("'id' must be a string", p2)
                branch['id'] = id_
            items.append(branch)
        out['branches'] = items
        p = path + '.merge'
        if 'merge' in raw:
            merge = raw['merge']
            if not isinstance(merge, dict):
                raise schema_error('merge must be an object', p)
            record = {}
            p2 = p + '.strategy'
            if 'strategy' in merge:
                strategy = merge['strategy']
                if strategy != 'concat':
                    raise schema_error("only 'concat' merge strategy is supported", p2)
                record['strategy'] = strategy
            else:
                record['strategy'] = 'concat'
            out['merge'] = record
        else:
            out['merge'] = {'strategy': 'concat'}
        return out

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
