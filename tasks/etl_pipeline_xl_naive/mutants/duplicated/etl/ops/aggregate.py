"""Ops that collapse rows into groups."""

import json

from etl.errors import EtlError, schema_error
from etl.expr import is_num, num_result
from etl.steps import Op, register


def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))


@register
class GroupCount(Op):
    name = 'group_count'

    def normalize(self, raw, path):
        out = {}
        p = path + '.by'
        if 'by' not in raw:
            raise schema_error("missing required field 'by'", p)
        by = raw['by']
        if not isinstance(by, list):
            raise schema_error("'by' must be an array", p)
        if not by:
            raise schema_error("'by' must be non-empty", p)
        for i, item in enumerate(by):
            if not isinstance(item, str):
                raise schema_error("'column names' must be a string", '%s[%d]' % (p, i))
        by = list(by)
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
        return out

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

    def normalize(self, raw, path):
        out = {}
        p = path + '.by'
        if 'by' in raw:
            by = raw['by']
            if not isinstance(by, list):
                raise schema_error("'by' must be an array", p)
            for i, item in enumerate(by):
                if not isinstance(item, str):
                    raise schema_error("'column names' must be a string", '%s[%d]' % (p, i))
            by = list(by)
            out['by'] = by
        else:
            out['by'] = []
        p = path + '.metrics'
        if 'metrics' not in raw:
            raise schema_error("missing required field 'metrics'", p)
        metrics = raw['metrics']
        if not isinstance(metrics, list):
            raise schema_error("'metrics' must be an array", p)
        if not metrics:
            raise schema_error("'metrics' must be non-empty", p)
        items = []
        for i, item in enumerate(metrics):
            ip = '%s[%d]' % (p, i)
            if not isinstance(item, dict):
                raise schema_error('metrics entry must be an object', ip)
            record = {}
            p2 = ip + '.as'
            if 'as' not in item:
                raise schema_error("missing required field 'as'", p2)
            as_ = item['as']
            if not isinstance(as_, str):
                raise schema_error("'as' must be a string", p2)
            as_ = as_.strip()
            if not as_:
                raise schema_error("'as' must not be empty", p2)
            record['as'] = as_
            p2 = ip + '.fn'
            if 'fn' not in item:
                raise schema_error("missing required field 'fn'", p2)
            fn = item['fn']
            if not isinstance(fn, str):
                raise schema_error("'fn' must be a string", p2)
            fn = fn.strip()
            if not fn:
                raise schema_error("'fn' must not be empty", p2)
            fn = fn.lower()
            if fn not in ('sum', 'min', 'max', 'avg', 'count'):
                raise schema_error("'fn' must be one of sum, min, max, avg, count", p2)
            record['fn'] = fn
            p2 = ip + '.column'
            if 'column' in item:
                column = item['column']
                if not isinstance(column, str):
                    raise schema_error("'column' must be a string", p2)
                record['column'] = column
            item = record
            items.append(item)
        metrics = items
        out['metrics'] = metrics
        return out

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
