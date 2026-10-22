"""Ops that filter, order or add rows."""

import json

from etl.errors import EtlError, schema_error
from etl.expr import is_num, truthy, num_result, parse_expr
from etl.steps import Op, register


def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))


@register
class Distinct(Op):
    name = 'distinct'

    def normalize(self, raw, path):
        out = {}
        p = path + '.columns'
        if 'columns' in raw:
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
        seen, out = set(), []
        for r in rows:
            if 'columns' in step.values:
                key = json.dumps([r.get(c) for c in step['columns']])
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

    def normalize(self, raw, path):
        out = {}
        p = path + '.by'
        if 'by' not in raw:
            raise schema_error("missing required field 'by'", p)
        by = raw['by']
        if not isinstance(by, str):
            raise schema_error("'by' must be a string", p)
        by = by.strip()
        if not by:
            raise schema_error("'by' must not be empty", p)
        out['by'] = by
        p = path + '.desc'
        if 'desc' in raw:
            desc = raw['desc']
            if not isinstance(desc, bool):
                raise schema_error("'desc' must be a boolean", p)
            out['desc'] = desc
        else:
            out['desc'] = False
        return out

    def run(self, step, rows, ctx):
        present = [r for r in rows if r.get(step['by']) is not None]
        nulls = [r for r in rows if r.get(step['by']) is None]
        return sorted(present, key=lambda r: self.key(step, r[step['by']]), reverse=step['desc']) + nulls

    def key(self, step, v):
        for test, rank in TYPE_ORDER:
            if test(v):
                return (rank, v)
        raise execution_error(step, 'cannot sort by a %s value' % type(v).__name__, 'by')

@register
class Offset(Op):
    name = 'offset'

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
        return rows[step['n']:]

@register
class Tail(Op):
    name = 'tail'

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
        return rows[max(0, len(rows) - step['n']):] if step['n'] else []

@register
class Assert(Op):
    name = 'assert'

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
        p = path + '.message'
        if 'message' in raw:
            message = raw['message']
            if not isinstance(message, str):
                raise schema_error("'message' must be a string", p)
            out['message'] = message
        else:
            out['message'] = 'assertion failed'
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            if not truthy(ctx.eval(step, step['where'], r, 'where')):
                raise execution_error(step, step['message'], 'where')
        return rows

@register
class SampleEvery(Op):
    name = 'sample_every'

    def normalize(self, raw, path):
        out = {}
        p = path + '.n'
        if 'n' not in raw:
            raise schema_error("missing required field 'n'", p)
        n = raw['n']
        if isinstance(n, bool) or not isinstance(n, int):
            raise schema_error("'n' must be an integer", p)
        if n < 1:
            raise schema_error("'n' must be >= 1", p)
        out['n'] = n
        return out

    def run(self, step, rows, ctx):
        return rows[::step['n']]

@register
class TakeWhile(Op):
    name = 'take_while'

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
        out = []
        for r in rows:
            if not truthy(ctx.eval(step, step['where'], r, 'where')):
                break
            out.append(r)
        return out

@register
class SkipWhile(Op):
    name = 'skip_while'

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

    def normalize(self, raw, path):
        out = {}
        p = path + '.rows'
        if 'rows' not in raw:
            raise schema_error("missing required field 'rows'", p)
        rows = raw['rows']
        if not isinstance(rows, list):
            raise schema_error("'rows' must be an array", p)
        for i, item in enumerate(rows):
            if not isinstance(item, dict):
                raise schema_error("'rows' entries must be objects", '%s[%d]' % (p, i))
        rows = [dict(item) for item in rows]
        out['rows'] = rows
        return out

    def run(self, step, rows, ctx):
        return rows + [dict(x) for x in step['rows']]

@register
class Require(Op):
    name = 'require'

    def normalize(self, raw, path):
        out = {}
        p = path + '.columns'
        if 'columns' not in raw:
            raise schema_error("missing required field 'columns'", p)
        columns = raw['columns']
        if not isinstance(columns, list):
            raise schema_error("'columns' must be an array", p)
        if not columns:
            raise schema_error("'columns' must be non-empty", p)
        for i, item in enumerate(columns):
            if not isinstance(item, str):
                raise schema_error("'column names' must be a string", '%s[%d]' % (p, i))
        columns = list(columns)
        out['columns'] = columns
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            for j, c in enumerate(step['columns']):
                if r.get(c) is None:
                    raise execution_error(step, "column '%s' is required" % c, 'columns', j)
        return rows

@register
class RowNumber(Op):
    name = 'row_number'

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
        p = path + '.start'
        if 'start' in raw:
            start = raw['start']
            if isinstance(start, bool) or not isinstance(start, int):
                raise schema_error("'start' must be an integer", p)
            out['start'] = start
        else:
            out['start'] = 1
        return out

    def run(self, step, rows, ctx):
        for k, r in enumerate(rows):
            r[step['as']] = step['start'] + k
        return rows

@register
class Rank(Op):
    name = 'rank'

    def normalize(self, raw, path):
        out = {}
        p = path + '.by'
        if 'by' not in raw:
            raise schema_error("missing required field 'by'", p)
        by = raw['by']
        if not isinstance(by, str):
            raise schema_error("'by' must be a string", p)
        by = by.strip()
        if not by:
            raise schema_error("'by' must not be empty", p)
        out['by'] = by
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
        p = path + '.desc'
        if 'desc' in raw:
            desc = raw['desc']
            if not isinstance(desc, bool):
                raise schema_error("'desc' must be a boolean", p)
            out['desc'] = desc
        else:
            out['desc'] = False
        return out

    def run(self, step, rows, ctx):
        distinct = []
        for r in rows:
            v = r.get(step['by'])
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'rank requires numbers', 'by')
            if v not in distinct:
                distinct.append(v)
        distinct.sort(reverse=step['desc'])
        for r in rows:
            v = r.get(step['by'])
            r[step['as']] = None if v is None else distinct.index(v) + 1
        return rows

@register
class CumSum(Op):
    name = 'cumsum'

    def normalize(self, raw, path):
        out = {}
        p = path + '.column'
        if 'column' not in raw:
            raise schema_error("missing required field 'column'", p)
        column = raw['column']
        if not isinstance(column, str):
            raise schema_error("'column' must be a string", p)
        column = column.strip()
        if not column:
            raise schema_error("'column' must not be empty", p)
        out['column'] = column
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
        return out

    def run(self, step, rows, ctx):
        total = 0
        for r in rows:
            v = r.get(step['column'])
            if v is not None and not is_num(v):
                raise execution_error(step, 'cumsum requires numbers', 'column')
            total = num_result(total + (v or 0))
            r[step['as']] = total
        return rows

@register
class Lag(Op):
    name = 'lag'

    def normalize(self, raw, path):
        out = {}
        p = path + '.column'
        if 'column' not in raw:
            raise schema_error("missing required field 'column'", p)
        column = raw['column']
        if not isinstance(column, str):
            raise schema_error("'column' must be a string", p)
        column = column.strip()
        if not column:
            raise schema_error("'column' must not be empty", p)
        out['column'] = column
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
        p = path + '.n'
        if 'n' in raw:
            n = raw['n']
            if isinstance(n, bool) or not isinstance(n, int):
                raise schema_error("'n' must be an integer", p)
            if n < 0:
                raise schema_error("'n' must be >= 0", p)
            out['n'] = n
        else:
            out['n'] = 1
        p = path + '.default'
        if 'default' in raw:
            default = raw['default']
            if not (default is None or isinstance(default, (bool, int, float, str))):
                raise schema_error("'default' must be a JSON scalar", p)
            out['default'] = default
        return out

    def run(self, step, rows, ctx):
        values = [r.get(step['column']) for r in rows]
        for k, r in enumerate(rows):
            if k >= step['n']:
                r[step['as']] = values[k - step['n']]
            else:
                r[step['as']] = step['default'] if 'default' in step.values else None
        return rows
