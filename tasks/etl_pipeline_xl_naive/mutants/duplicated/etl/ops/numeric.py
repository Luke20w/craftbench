"""Number ops."""

import json
import math

from etl.errors import EtlError, schema_error
from etl.expr import is_num, num_result
from etl.steps import Op, register


def column_value(step, row, key='column'):
    """The row's value for the step's single `column`, which must exist."""
    c = step[key]
    if c not in row:
        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, step.at(key))
    return row[c]


def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))


@register
class Round(Op):
    name = 'round'

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
        p = path + '.digits'
        if 'digits' in raw:
            digits = raw['digits']
            if isinstance(digits, bool) or not isinstance(digits, int):
                raise schema_error("'digits' must be an integer", p)
            if digits < 0:
                raise schema_error("'digits' must be >= 0", p)
            out['digits'] = digits
        else:
            out['digits'] = 0
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'round requires a number', 'column')
            r[step['column']] = num_result(round(v, step['digits']))
        return rows

@register
class Clip(Op):
    name = 'clip'

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
        p = path + '.min'
        if 'min' in raw:
            min_ = raw['min']
            if not is_num(min_):
                raise schema_error("'min' must be a number", p)
            out['min'] = min_
        p = path + '.max'
        if 'max' in raw:
            max_ = raw['max']
            if not is_num(max_):
                raise schema_error("'max' must be a number", p)
            out['max'] = max_
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'clip requires a number', 'column')
            if 'min' in step.values and v < step['min']:
                v = step['min']
            if 'max' in step.values and v > step['max']:
                v = step['max']
            r[step['column']] = v
        return rows

@register
class Scale(Op):
    name = 'scale'

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
        p = path + '.factor'
        if 'factor' not in raw:
            raise schema_error("missing required field 'factor'", p)
        factor = raw['factor']
        if not is_num(factor):
            raise schema_error("'factor' must be a number", p)
        out['factor'] = factor
        p = path + '.offset'
        if 'offset' in raw:
            offset = raw['offset']
            if not is_num(offset):
                raise schema_error("'offset' must be a number", p)
            out['offset'] = offset
        else:
            out['offset'] = 0
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'scale requires a number', 'column')
            r[step['column']] = num_result(v * step['factor'] + step['offset'])
        return rows

@register
class Bucket(Op):
    name = 'bucket'

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
        p = path + '.edges'
        if 'edges' not in raw:
            raise schema_error("missing required field 'edges'", p)
        edges = raw['edges']
        if not isinstance(edges, list):
            raise schema_error("'edges' must be an array", p)
        if not edges:
            raise schema_error("'edges' must be non-empty", p)
        for i, item in enumerate(edges):
            if not is_num(item):
                raise schema_error("'edges entries' must be a number", '%s[%d]' % (p, i))
        edges = list(edges)
        out['edges'] = edges
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not is_num(v):
                raise execution_error(step, 'bucket requires a number', 'column')
            r[step['as']] = None if v is None else sum(1 for e in step['edges'] if v >= e)
        return rows

@register
class MathOp(Op):
    name = 'math'

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
        if fn not in ('abs', 'floor', 'ceil', 'sqrt', 'neg'):
            raise schema_error("'fn' must be one of abs, floor, ceil, sqrt, neg", p)
        out['fn'] = fn
        return out

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v) or (step['fn'] == 'sqrt' and v < 0):
                raise execution_error(step, 'cannot apply %s to %s' % (step['fn'], json.dumps(v)), 'column')
            if step['fn'] == 'abs':
                r[step['column']] = abs(v)
            elif step['fn'] == 'floor':
                r[step['column']] = math.floor(v)
            elif step['fn'] == 'ceil':
                r[step['column']] = math.ceil(v)
            elif step['fn'] == 'sqrt':
                r[step['column']] = num_result(math.sqrt(v))
            else:
                r[step['column']] = num_result(-v)
        return rows

@register
class Between(Op):
    name = 'between'

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
        p = path + '.low'
        if 'low' not in raw:
            raise schema_error("missing required field 'low'", p)
        low = raw['low']
        if not is_num(low):
            raise schema_error("'low' must be a number", p)
        out['low'] = low
        p = path + '.high'
        if 'high' not in raw:
            raise schema_error("missing required field 'high'", p)
        high = raw['high']
        if not is_num(high):
            raise schema_error("'high' must be a number", p)
        out['high'] = high
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
            v = r.get(step['column'])
            if v is not None and not is_num(v):
                raise execution_error(step, 'between requires a number', 'column')
            r[step['as']] = v is not None and step['low'] <= v <= step['high']
        return rows
