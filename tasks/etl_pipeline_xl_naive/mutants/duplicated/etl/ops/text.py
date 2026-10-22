"""String ops."""

import json
import re

from etl.errors import EtlError, schema_error
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
class Concat(Op):
    name = 'concat'

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
        p = path + '.sep'
        if 'sep' in raw:
            sep = raw['sep']
            if not isinstance(sep, str):
                raise schema_error("'sep' must be a string", p)
            out['sep'] = sep
        else:
            out['sep'] = ''
        return out

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        for r in rows:
            r[step['as']] = step['sep'].join('' if r[c] is None else to_text(r[c]) for c in cols)
        return rows

@register
class Split(Op):
    name = 'split'

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
        p = path + '.sep'
        if 'sep' not in raw:
            raise schema_error("missing required field 'sep'", p)
        sep = raw['sep']
        if not isinstance(sep, str):
            raise schema_error("'sep' must be a string", p)
        if not sep:
            raise schema_error("'sep' must not be empty", p)
        out['sep'] = sep
        p = path + '.into'
        if 'into' not in raw:
            raise schema_error("missing required field 'into'", p)
        into = raw['into']
        if not isinstance(into, list):
            raise schema_error("'into' must be an array", p)
        if not into:
            raise schema_error("'into' must be non-empty", p)
        for i, item in enumerate(into):
            if not isinstance(item, str):
                raise schema_error("'column names' must be a string", '%s[%d]' % (p, i))
        into = list(into)
        out['into'] = into
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, str):
                raise execution_error(step, 'split requires a string', 'column')
            parts = v.split(step['sep']) if v is not None else []
            for i, name in enumerate(step['into']):
                r[name] = parts[i] if i < len(parts) else None
        return rows

@register
class TextOp(Op):
    name = 'text'

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
        p = path + '.fn'
        if 'fn' not in raw:
            raise schema_error("missing required field 'fn'", p)
        fn = raw['fn']
        if not isinstance(fn, str):
            raise schema_error("'fn' must be a string", p)
        fn = fn.strip()
        if not fn:
            raise schema_error("'fn' must not be empty", p)
        fn = fn.lower()
        if fn not in ('upper', 'lower', 'trim'):
            raise schema_error("'fn' must be one of upper, lower, trim", p)
        out['fn'] = fn
        return out

    def run(self, step, rows, ctx):
        cols = column_values(step, rows)
        fn = {'upper': str.upper, 'lower': str.lower, 'trim': str.strip}[step['fn']]
        for r in rows:
            for j, c in enumerate(cols):
                if r[c] is None:
                    continue
                if not isinstance(r[c], str):
                    raise execution_error(step, 'text requires a string', 'columns', j)
                r[c] = fn(r[c])
        return rows

@register
class Replace(Op):
    name = 'replace'

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
        p = path + '.find'
        if 'find' not in raw:
            raise schema_error("missing required field 'find'", p)
        find = raw['find']
        if not isinstance(find, str):
            raise schema_error("'find' must be a string", p)
        if not find:
            raise schema_error("'find' must not be empty", p)
        out['find'] = find
        p = path + '.with'
        if 'with' not in raw:
            raise schema_error("missing required field 'with'", p)
        with_ = raw['with']
        if not isinstance(with_, str):
            raise schema_error("'with' must be a string", p)
        out['with'] = with_
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not isinstance(v, str):
                raise execution_error(step, 'replace requires a string', 'column')
            r[step['column']] = v.replace(step['find'], step['with'])
        return rows

@register
class RegexExtract(Op):
    name = 'regex_extract'

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
        p = path + '.pattern'
        if 'pattern' not in raw:
            raise schema_error("missing required field 'pattern'", p)
        pattern = raw['pattern']
        if not isinstance(pattern, str):
            raise schema_error("'pattern' must be a string", p)
        if not pattern:
            raise schema_error("'pattern' must not be empty", p)
        try:
            re.compile(pattern)
        except re.error:
                raise schema_error("'pattern' must be a valid regular expression", p)
        out['pattern'] = pattern
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
        p = path + '.group'
        if 'group' in raw:
            group = raw['group']
            if isinstance(group, bool) or not isinstance(group, int):
                raise schema_error("'group' must be an integer", p)
            if group < 0:
                raise schema_error("'group' must be >= 0", p)
            out['group'] = group
        else:
            out['group'] = 0
        return out

    def run(self, step, rows, ctx):
        rx = re.compile(step['pattern'])
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, str):
                raise execution_error(step, 'regex_extract requires a string', 'column')
            m = rx.search(v) if v is not None else None
            if m is not None and step['group'] > rx.groups:
                raise execution_error(step, 'pattern has no group %d' % step['group'], 'group')
            r[step['as']] = m.group(step['group']) if m else None
        return rows

@register
class RegexFilter(Op):
    name = 'regex_filter'

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
        p = path + '.pattern'
        if 'pattern' not in raw:
            raise schema_error("missing required field 'pattern'", p)
        pattern = raw['pattern']
        if not isinstance(pattern, str):
            raise schema_error("'pattern' must be a string", p)
        if not pattern:
            raise schema_error("'pattern' must not be empty", p)
        try:
            re.compile(pattern)
        except re.error:
                raise schema_error("'pattern' must be a valid regular expression", p)
        out['pattern'] = pattern
        p = path + '.invert'
        if 'invert' in raw:
            invert = raw['invert']
            if not isinstance(invert, bool):
                raise schema_error("'invert' must be a boolean", p)
            out['invert'] = invert
        else:
            out['invert'] = False
        return out

    def run(self, step, rows, ctx):
        rx = re.compile(step['pattern'])
        out = []
        for r in rows:
            v = r.get(step['column'])
            if (isinstance(v, str) and rx.search(v) is not None) != step['invert']:
                out.append(r)
        return out

@register
class Substr(Op):
    name = 'substr'

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
        p = path + '.start'
        if 'start' not in raw:
            raise schema_error("missing required field 'start'", p)
        start = raw['start']
        if isinstance(start, bool) or not isinstance(start, int):
            raise schema_error("'start' must be an integer", p)
        if start < 0:
            raise schema_error("'start' must be >= 0", p)
        out['start'] = start
        p = path + '.length'
        if 'length' in raw:
            length = raw['length']
            if isinstance(length, bool) or not isinstance(length, int):
                raise schema_error("'length' must be an integer", p)
            if length < 0:
                raise schema_error("'length' must be >= 0", p)
            out['length'] = length
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, str):
                raise execution_error(step, 'substr requires a string', 'column')
            if v is None:
                r[step['as']] = None
            elif 'length' in step.values:
                r[step['as']] = v[step['start']:step['start'] + step['length']]
            else:
                r[step['as']] = v[step['start']:]
        return rows

@register
class Pad(Op):
    name = 'pad'

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
        p = path + '.width'
        if 'width' not in raw:
            raise schema_error("missing required field 'width'", p)
        width = raw['width']
        if isinstance(width, bool) or not isinstance(width, int):
            raise schema_error("'width' must be an integer", p)
        if width < 0:
            raise schema_error("'width' must be >= 0", p)
        out['width'] = width
        p = path + '.fill'
        if 'fill' in raw:
            fill = raw['fill']
            if not isinstance(fill, str):
                raise schema_error("'fill' must be a string", p)
            if not fill:
                raise schema_error("'fill' must not be empty", p)
            out['fill'] = fill
        else:
            out['fill'] = ' '
        p = path + '.side'
        if 'side' in raw:
            side = raw['side']
            if not isinstance(side, str):
                raise schema_error("'side' must be a string", p)
            side = side.strip()
            if not side:
                raise schema_error("'side' must not be empty", p)
            side = side.lower()
            if side not in ('left', 'right'):
                raise schema_error("'side' must be one of left, right", p)
            out['side'] = side
        else:
            out['side'] = 'left'
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            s = to_text(v)
            short = max(0, step['width'] - len(s))
            padding = (step['fill'] * short)[:short]
            r[step['column']] = padding + s if step['side'] == 'left' else s + padding
        return rows

@register
class Length(Op):
    name = 'length'

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
        for r in rows:
            v = column_value(step, r)
            if v is not None and not isinstance(v, (str, list, dict)):
                raise execution_error(step, 'length requires a string, array or object', 'column')
            r[step['as']] = None if v is None else len(v)
        return rows

@register
class JsonParse(Op):
    name = 'json_parse'

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
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not isinstance(v, str):
                raise execution_error(step, 'json_parse requires a string', 'column')
            try:
                r[step['column']] = json.loads(v)
            except ValueError:
                raise execution_error(step, 'invalid JSON text', 'column')
        return rows

@register
class JsonDump(Op):
    name = 'json_dump'

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
        for r in rows:
            v = column_value(step, r)
            if v is not None:
                r[step['column']] = json.dumps(v, sort_keys=True)
        return rows

@register
class DatePart(Op):
    name = 'date_part'

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
        p = path + '.part'
        if 'part' not in raw:
            raise schema_error("missing required field 'part'", p)
        part = raw['part']
        if not isinstance(part, str):
            raise schema_error("'part' must be a string", p)
        part = part.strip()
        if not part:
            raise schema_error("'part' must not be empty", p)
        part = part.lower()
        if part not in ('year', 'month', 'day'):
            raise schema_error("'part' must be one of year, month, day", p)
        out['part'] = part
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
        for r in rows:
            v = column_value(step, r)
            if v is None:
                r[step['as']] = None
                continue
            m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', v) if isinstance(v, str) else None
            if m is None:
                raise execution_error(step, 'expected a YYYY-MM-DD date', 'column')
            r[step['as']] = int(m.group(('year', 'month', 'day').index(step['part']) + 1))
        return rows
