"""Number ops."""

import json
import math

from etl.expr import is_num, num_result
from etl.fields import Text, Choice, Count, Number, List
from etl.steps import Op, register
from etl.options import match
from etl.ops.common import column_value, execution_error

@register
class Round(Op):
    name = 'round'
    fields = (Text('column'), Count('digits', required=False, default=0))

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'round requires a number', 'column')
            r[match(r, step['column'])] = num_result(round(v, step['digits']))
        return rows

@register
class Clip(Op):
    name = 'clip'
    fields = (Text('column'), Number('min', required=False), Number('max', required=False),)

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
            r[match(r, step['column'])] = v
        return rows

@register
class Scale(Op):
    name = 'scale'
    fields = (Text('column'), Number('factor'), Number('offset', required=False, default=0),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v):
                raise execution_error(step, 'scale requires a number', 'column')
            r[match(r, step['column'])] = num_result(v * step['factor'] + step['offset'])
        return rows

@register
class Bucket(Op):
    name = 'bucket'
    fields = (Text('column'), Text('as'), List('edges', Number('edges entries'), non_empty=True),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is not None and not is_num(v):
                raise execution_error(step, 'bucket requires a number', 'column')
            r[match(r, step['as'])] = None if v is None else sum(1 for e in step['edges'] if v >= e)
        return rows

@register
class MathOp(Op):
    name = 'math'
    fields = (Text('column'), Choice('fn', ('abs', 'floor', 'ceil', 'sqrt', 'neg')),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = column_value(step, r)
            if v is None:
                continue
            if not is_num(v) or (step['fn'] == 'sqrt' and v < 0):
                raise execution_error(step, 'cannot apply %s to %s' % (step['fn'], json.dumps(v)), 'column')
            if step['fn'] == 'abs':
                v = abs(v)
            elif step['fn'] == 'floor':
                v = math.floor(v)
            elif step['fn'] == 'ceil':
                v = math.ceil(v)
            elif step['fn'] == 'sqrt':
                v = num_result(math.sqrt(v))
            else:
                v = num_result(-v)
            r[match(r, step['column'])] = v
        return rows

@register
class Between(Op):
    name = 'between'
    fields = (Text('column'), Number('low'), Number('high'), Text('as'),)

    def run(self, step, rows, ctx):
        for r in rows:
            v = r.get(match(r, step['column']))
            if v is not None and not is_num(v):
                raise execution_error(step, 'between requires a number', 'column')
            r[match(r, step['as'])] = v is not None and step['low'] <= v <= step['high']
        return rows
