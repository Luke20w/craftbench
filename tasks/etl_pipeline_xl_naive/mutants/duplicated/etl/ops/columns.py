"""Ops that add, remove or reshape columns."""

import json

from etl.errors import EtlError, schema_error
from etl.expr import is_num, parse_expr
from etl.steps import Op, register


def column_values(step, rows, key='columns'):
    """Check every listed column exists in every row (MISSING_COLUMN at key[j])."""
    cols = step[key]
    for r in rows:
        for j, c in enumerate(cols):
            if c not in r:
                raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, step.at(key, j))
    return cols


def column_value(step, row, key='column'):
    """The row's value for the step's single `column`, which must exist."""
    c = step[key]
    if c not in row:
        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, step.at(key))
    return row[c]


def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))


def to_text(v):
    return v if isinstance(v, str) else json.dumps(v)


@register
class Drop(Op):
    name = 'drop'

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
        cols = column_values(step, rows)
        return [{k: v for k, v in r.items() if k not in cols} for r in rows]

@register
class Fill(Op):
    name = 'fill'

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
        p = path + '.value'
        if 'value' not in raw:
            raise schema_error("missing required field 'value'", p)
        value = raw['value']
        if not isinstance(value, str):
            raise schema_error("'value' must be a string", p)
        value = value.strip()
        if not value:
            raise schema_error("'value' must not be empty", p)
        parse_expr(value, p)
        out['value'] = value
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            if r.get(step['column']) is None:
                r[step['column']] = ctx.eval(step, step['value'], r, 'value')
        return rows

@register
class Cast(Op):
    name = 'cast'

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
        p = path + '.to'
        if 'to' not in raw:
            raise schema_error("missing required field 'to'", p)
        to = raw['to']
        if not isinstance(to, str):
            raise schema_error("'to' must be a string", p)
        to = to.strip()
        if not to:
            raise schema_error("'to' must not be empty", p)
        to = to.lower()
        if to not in ('int', 'float', 'string', 'bool'):
            raise schema_error("'to' must be one of int, float, string, bool", p)
        out['to'] = to
        return out

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
        p = path + '.exprs'
        if 'exprs' not in raw:
            raise schema_error("missing required field 'exprs'", p)
        exprs = raw['exprs']
        if not isinstance(exprs, list):
            raise schema_error("'exprs' must be an array", p)
        if not exprs:
            raise schema_error("'exprs' must be non-empty", p)
        items = []
        for i, item in enumerate(exprs):
            ip = '%s[%d]' % (p, i)
            if not isinstance(item, str):
                raise schema_error("'exprs entries' must be a string", ip)
            item = item.strip()
            if not item:
                raise schema_error("'exprs entries' must not be empty", ip)
            parse_expr(item, ip)
            items.append(item)
        exprs = items
        out['exprs'] = exprs
        return out

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
        return out

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
        p = path + '.table'
        if 'table' not in raw:
            raise schema_error("missing required field 'table'", p)
        table = raw['table']
        if not isinstance(table, dict):
            raise schema_error("'table' must be an object", p)
        entries = {}
        for name, entry in table.items():
            ep = '%s.%s' % (p, name)
            if not (entry is None or isinstance(entry, (bool, int, float, str))):
                raise schema_error("'table values' must be a JSON scalar", ep)
            entries[name] = entry
        table = entries
        out['table'] = table
        p = path + '.default'
        if 'default' in raw:
            default = raw['default']
            if not (default is None or isinstance(default, (bool, int, float, str))):
                raise schema_error("'default' must be a JSON scalar", p)
            out['default'] = default
        return out

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
        p = path + '.value'
        if 'value' not in raw:
            raise schema_error("missing required field 'value'", p)
        value = raw['value']
        if not (value is None or isinstance(value, (bool, int, float, str))):
            raise schema_error("'value' must be a JSON scalar", p)
        out['value'] = value
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            r[step['column']] = step['value']
        return rows

@register
class Ensure(Op):
    name = 'ensure'

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
        p = path + '.value'
        if 'value' in raw:
            value = raw['value']
            if not (value is None or isinstance(value, (bool, int, float, str))):
                raise schema_error("'value' must be a JSON scalar", p)
            out['value'] = value
        else:
            out['value'] = None
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            for c in step['columns']:
                if c not in r:
                    r[c] = step['value']
        return rows

@register
class Reorder(Op):
    name = 'reorder'

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
        cols = column_values(step, rows)
        return [dict([(c, r[c]) for c in cols] + [(k, v) for k, v in r.items() if k not in cols]) for r in rows]

@register
class Prefix(Op):
    name = 'prefix'

    def normalize(self, raw, path):
        out = {}
        p = path + '.prefix'
        if 'prefix' not in raw:
            raise schema_error("missing required field 'prefix'", p)
        prefix = raw['prefix']
        if not isinstance(prefix, str):
            raise schema_error("'prefix' must be a string", p)
        if not prefix:
            raise schema_error("'prefix' must not be empty", p)
        out['prefix'] = prefix
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
        for k, r in enumerate(rows):
            targets = step['columns'] if 'columns' in step.values else list(r)
            rows[k] = {(step['prefix'] + c if c in targets else c): v for c, v in r.items()}
        return rows

@register
class Nest(Op):
    name = 'nest'

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
        p = path + '.prefix'
        if 'prefix' in raw:
            prefix = raw['prefix']
            if not isinstance(prefix, str):
                raise schema_error("'prefix' must be a string", p)
            out['prefix'] = prefix
        else:
            out['prefix'] = ''
        return out

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
