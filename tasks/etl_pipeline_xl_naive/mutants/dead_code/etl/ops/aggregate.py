"""Ops that collapse rows into groups."""

import json

from etl.expr import is_num, num_result
from etl.fields import Text, Label, Choice, List, Record
from etl.steps import Op, register
from etl.ops.common import execution_error

@register
class GroupCount(Op):
    name = 'group_count'
    fields = (List('by', Label('column names'), non_empty=True), Text('as'),)

    def run(self, step, rows, ctx):
        groups = {}
        for r in rows:
            key = json.dumps([r.get(c) for c in step['by']])
            if key not in groups:
                groups[key] = {c: r.get(c) for c in step['by']}
                groups[key][step['as']] = 0
            groups[key][step['as']] += 1
        return list(groups.values())

@register
class Summarize(Op):
    name = 'summarize'
    fields = (List('by', Label('column names'), required=False, default=[]), List('metrics', Record('metrics entry', (Text('as'), Choice('fn', ('sum', 'min', 'max', 'avg', 'count')), Label('column', required=False),)), non_empty=True),)

    def run(self, step, rows, ctx):
        groups = {}
        for r in rows:
            groups.setdefault(json.dumps([r.get(c) for c in step['by']]), []).append(r)
        out = []
        for members in groups.values():
            row = {c: members[0].get(c) for c in step['by']}
            for j, m in enumerate(step['metrics']):
                values = [x.get(m['column']) for x in members] if 'column' in m else members
                values = [v for v in values if v is not None]
                if m['fn'] == 'count':
                    row[m['as']] = len(values)
                    continue
                if any(not is_num(v) for v in values):
                    raise execution_error(step, '%s requires numbers' % m['fn'], 'metrics', j, 'column')
                if not values:
                    row[m['as']] = None
                elif m['fn'] == 'sum':
                    row[m['as']] = num_result(sum(values))
                elif m['fn'] == 'min':
                    row[m['as']] = min(values)
                elif m['fn'] == 'max':
                    row[m['as']] = max(values)
                else:
                    row[m['as']] = num_result(sum(values) / len(values))
            out.append(row)
        return out


class GroupCountV1(Op):
    """group_count over a single column (superseded by GroupCount, which takes a list)."""
    name = 'group_count'
    fields = (Text('by'), Text('as'))

    def run(self, step, rows, ctx):
        counts = {}
        order = []
        for r in rows:
            key = json.dumps(r.get(step['by']))
            if key not in counts:
                counts[key] = 0
                order.append((key, r.get(step['by'])))
            counts[key] += 1
        return [{step['by']: v, step['as']: counts[k]} for k, v in order]


def group_rows(rows, by):
    groups = {}
    for r in rows:
        groups.setdefault(json.dumps([r.get(c) for c in by]), []).append(r)
    return list(groups.values())


def metric_value(fn, values):
    values = [v for v in values if v is not None]
    if fn == 'count':
        return len(values)
    if not values:
        return None
    if fn == 'sum':
        return num_result(sum(values))
    if fn == 'min':
        return min(values)
    if fn == 'max':
        return max(values)
    return num_result(sum(values) / len(values))


def all_numbers(values):
    return all(is_num(v) for v in values if v is not None)
