"""Ops that collapse rows into groups."""

import json

from etl.expr import is_num, num_result
from etl.fields import Text, Label, Choice, List, Record
from etl.steps import Op, register
from etl.options import match
from etl.ops.common import execution_error

@register
class GroupCount(Op):
    name = 'group_count'
    fields = (List('by', Label('column names'), non_empty=True), Text('as'),)

    def run(self, step, rows, ctx):
        groups = {}
        for r in rows:
            key = json.dumps([r.get(match(r, c)) for c in step['by']])
            if key not in groups:
                groups[key] = {match(r, c): r.get(match(r, c)) for c in step['by']}
                groups[key][match(groups[key], step['as'])] = 0
            groups[key][match(groups[key], step['as'])] += 1
        return list(groups.values())

@register
class Summarize(Op):
    name = 'summarize'
    fields = (List('by', Label('column names'), required=False, default=[]), List('metrics', Record('metrics entry', (Text('as'), Choice('fn', ('sum', 'min', 'max', 'avg', 'count')), Label('column', required=False),)), non_empty=True),)

    def run(self, step, rows, ctx):
        groups = {}
        for r in rows:
            groups.setdefault(json.dumps([r.get(match(r, c)) for c in step['by']]), []).append(r)
        out = []
        for members in groups.values():
            first = members[0]
            row = {match(first, c): first.get(match(first, c)) for c in step['by']}
            for j, m in enumerate(step['metrics']):
                values = [x.get(match(x, m['column'])) for x in members] if 'column' in m else members
                values = [v for v in values if v is not None]
                if m['fn'] == 'count':
                    row[match(row, m['as'])] = len(values)
                    continue
                if any(not is_num(v) for v in values):
                    raise execution_error(step, '%s requires numbers' % m['fn'], 'metrics', j, 'column')
                if not values:
                    row[match(row, m['as'])] = None
                elif m['fn'] == 'sum':
                    row[match(row, m['as'])] = num_result(sum(values))
                elif m['fn'] == 'min':
                    row[match(row, m['as'])] = min(values)
                elif m['fn'] == 'max':
                    row[match(row, m['as'])] = max(values)
                else:
                    row[match(row, m['as'])] = num_result(sum(values) / len(values))
            out.append(row)
        return out
