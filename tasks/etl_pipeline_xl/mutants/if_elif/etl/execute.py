"""Execution of normalized pipeline steps over rows."""

import json
import math
import re

from etl.errors import EtlError
from etl.expr import parse_expr, is_num, truthy, num_result, eval_at

def at(path, *parts):
    """Error path below a step, e.g. at(path, 'columns', 2) -> '<path>.columns[2]'."""
    for part in parts:
        path += '[%d]' % part if isinstance(part, int) else '.' + part
    return path


def eval_in(path, expr, row, *parts):
    """Evaluate a step's expression; errors point at at(path, *parts)."""
    p = at(path, *parts)
    return eval_at(parse_expr(expr, p), row, p)


def execution_error(path, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, at(path, *parts))


def column_value(step, row, path, key='column'):
    """The row's value for the step's single `column`, which must exist."""
    c = step[key]
    if c not in row:
        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, at(path, key))
    return row[c]


def column_values(step, rows, path, key='columns'):
    """Check every listed column exists in every row (MISSING_COLUMN at key[j])."""
    cols = step[key]
    for r in rows:
        for j, c in enumerate(cols):
            if c not in r:
                raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, at(path, key, j))
    return cols


def to_text(v):
    return v if isinstance(v, str) else json.dumps(v)

def execute_steps(steps, raw_steps, rows, path_prefix):
    """Execute a list of steps on rows, with proper error path tracking."""
    for i, step in enumerate(steps):
        path = '%s[%d]' % (path_prefix, i)
        op = step['op']
        if op == 'select':
            cols = step['columns']
            for r in rows:
                for j, c in enumerate(cols):
                    if c not in r:
                        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, '%s.columns[%d]' % (path, j))
            rows = [{c: r[c] for c in cols} for r in rows]
        elif op == 'filter':
            node = parse_expr(step['where'], path + '.where')
            rows = [r for r in rows if truthy(eval_at(node, r, path + '.where'))]
        elif op == 'map':
            node = parse_expr(step['expr'], path + '.expr')
            for r in rows:
                r[step['as']] = eval_at(node, r, path + '.expr')
        elif op == 'rename':
            from_form = 'mapping' not in raw_steps[i] if i < len(raw_steps) else False
            for src, dst in step['mapping'].items():
                p = path + '.from' if from_form else '%s.mapping.%s' % (path, src)
                new_rows = []
                for r in rows:
                    if src not in r:
                        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % src, p)
                    nr = {}
                    for k, v in r.items():
                        if k == src:
                            nr[dst] = v
                        elif k != dst:
                            nr[k] = v
                    new_rows.append(nr)
                rows = new_rows
        elif op == 'limit':
            rows = rows[:step['n']]
        elif op in ('drop', 'concat', 'text'):
            cols = step['columns']
            for r in rows:
                for j, c in enumerate(cols):
                    if c not in r:
                        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, '%s.columns[%d]' % (path, j))
            if op == 'drop':
                rows = [{k: v for k, v in r.items() if k not in cols} for r in rows]
            elif op == 'concat':
                for r in rows:
                    r[step['as']] = step['sep'].join(('' if r[c] is None else r[c] if isinstance(r[c], str) else json.dumps(r[c]) for c in cols))
            else:
                for r in rows:
                    for j, c in enumerate(cols):
                        v = r[c]
                        if v is None:
                            continue
                        if not isinstance(v, str):
                            raise EtlError('EXECUTION_FAILED', 'ETL_ERROR: text requires a string', '%s.columns[%d]' % (path, j))
                        if step['fn'] == 'upper':
                            r[c] = v.upper()
                        elif step['fn'] == 'lower':
                            r[c] = v.lower()
                        else:
                            r[c] = v.strip()
        elif op == 'distinct':
            seen = set()
            new_rows = []
            for r in rows:
                if 'columns' in step:
                    key = json.dumps([r.get(c) for c in step['columns']])
                else:
                    key = json.dumps(r, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    new_rows.append(r)
            rows = new_rows
        elif op == 'sort':
            by = step['by']
            present = [r for r in rows if r.get(by) is not None]
            nulls = [r for r in rows if r.get(by) is None]

            def sort_key(r):
                v = r[by]
                if is_num(v):
                    return (0, v)
                if isinstance(v, str):
                    return (1, v)
                if isinstance(v, bool):
                    return (2, v)
                raise EtlError('EXECUTION_FAILED', 'ETL_ERROR: cannot sort by a %s value' % type(v).__name__, path + '.by')
            rows = sorted(present, key=sort_key, reverse=step['desc']) + nulls
        elif op == 'offset':
            rows = rows[step['n']:]
        elif op == 'tail':
            rows = rows[max(0, len(rows) - step['n']):] if step['n'] else []
        elif op == 'fill':
            node = parse_expr(step['value'], path + '.value')
            for r in rows:
                if r.get(step['column']) is None:
                    r[step['column']] = eval_at(node, r, path + '.value')
        elif op in ('cast', 'round', 'split', 'explode'):
            col = step['column']
            new_rows = []
            for r in rows:
                if col not in r:
                    raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % col, path + '.column')
                v = r[col]
                if op == 'cast':
                    if v is not None:
                        to = step['to']
                        bad = EtlError('EXECUTION_FAILED', 'ETL_ERROR: cannot cast %s to %s' % (json.dumps(v), to), path + '.column')
                        try:
                            if to == 'int':
                                if isinstance(v, bool):
                                    raise bad
                                r[col] = int(v)
                            elif to == 'float':
                                if isinstance(v, bool):
                                    raise bad
                                r[col] = float(v)
                            elif to == 'string':
                                r[col] = v if isinstance(v, str) else json.dumps(v)
                            elif isinstance(v, bool):
                                r[col] = v
                            elif isinstance(v, str) and v.strip().lower() in ('true', 'false'):
                                r[col] = v.strip().lower() == 'true'
                            elif is_num(v):
                                r[col] = v != 0
                            else:
                                raise bad
                        except (TypeError, ValueError):
                            raise bad
                    new_rows.append(r)
                elif op == 'round':
                    if v is not None:
                        if not is_num(v):
                            raise EtlError('EXECUTION_FAILED', 'ETL_ERROR: round requires a number', path + '.column')
                        r[col] = num_result(round(v, step['digits']))
                    new_rows.append(r)
                elif op == 'split':
                    if v is not None and not isinstance(v, str):
                        raise EtlError('EXECUTION_FAILED', 'ETL_ERROR: split requires a string', path + '.column')
                    parts = v.split(step['sep']) if v is not None else []
                    for i, name in enumerate(step['into']):
                        r[name] = parts[i] if i < len(parts) else None
                    new_rows.append(r)
                elif isinstance(v, list):
                    for x in v:
                        nr = dict(r)
                        nr[col] = x
                        new_rows.append(nr)
                else:
                    new_rows.append(r)
            rows = new_rows
        elif op == 'assert':
            node = parse_expr(step['where'], path + '.where')
            for r in rows:
                if not truthy(eval_at(node, r, path + '.where')):
                    raise EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + step['message'], path + '.where')
        elif op == 'coalesce':
            nodes = [parse_expr(e, '%s.exprs[%d]' % (path, k)) for k, e in enumerate(step['exprs'])]
            for r in rows:
                value = None
                for k, node in enumerate(nodes):
                    value = eval_at(node, r, '%s.exprs[%d]' % (path, k))
                    if value is not None:
                        break
                r[step['as']] = value
        elif op == 'group_count':
            groups = {}
            for r in rows:
                key = json.dumps([r.get(c) for c in step['by']])
                if key not in groups:
                    groups[key] = {c: r.get(c) for c in step['by']}
                    groups[key][step['as']] = 0
                groups[key][step['as']] += 1
            rows = list(groups.values())
        elif op == 'summarize':
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
                        raise execution_error(path, '%s requires numbers' % m['fn'], 'metrics', j, 'column')
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
            rows = out
        elif op == 'lookup':
            for r in rows:
                v = column_value(step, r, path)
                key = v if isinstance(v, str) else json.dumps(v)
                if key in step['table']:
                    r[step['as']] = step['table'][key]
                else:
                    r[step['as']] = step['default'] if 'default' in step else None
            rows = rows
        elif op == 'set':
            for r in rows:
                r[step['column']] = step['value']
            rows = rows
        elif op == 'ensure':
            for r in rows:
                for c in step['columns']:
                    if c not in r:
                        r[c] = step['value']
            rows = rows
        elif op == 'reorder':
            cols = column_values(step, rows, path)
            rows = [dict([(c, r[c]) for c in cols] + [(k, v) for k, v in r.items() if k not in cols]) for r in rows]
        elif op == 'prefix':
            for k, r in enumerate(rows):
                targets = step['columns'] if 'columns' in step else list(r)
                rows[k] = {(step['prefix'] + c if c in targets else c): v for c, v in r.items()}
            rows = rows
        elif op == 'nest':
            cols = column_values(step, rows, path)
            out = []
            for r in rows:
                nr = {k: v for k, v in r.items() if k not in cols}
                nr[step['as']] = {c: r[c] for c in cols}
                out.append(nr)
            rows = out
        elif op == 'unnest':
            out = []
            for r in rows:
                v = column_value(step, r, path)
                if v is not None and not isinstance(v, dict):
                    raise execution_error(path, 'unnest requires an object', 'column')
                nr = {k: x for k, x in r.items() if k != step['column']}
                for k, x in (v or {}).items():
                    nr[step['prefix'] + k] = x
                out.append(nr)
            rows = out
        elif op == 'sample_every':
            rows = rows[::step['n']]
        elif op == 'take_while':
            out = []
            for r in rows:
                if not truthy(eval_in(path, step['where'], r, 'where')):
                    break
                out.append(r)
            rows = out
        elif op == 'skip_while':
            out = []
            skipping = True
            for r in rows:
                if skipping and truthy(eval_in(path, step['where'], r, 'where')):
                    continue
                skipping = False
                out.append(r)
            rows = out
        elif op == 'append':
            rows = rows + [dict(x) for x in step['rows']]
        elif op == 'require':
            for r in rows:
                for j, c in enumerate(step['columns']):
                    if r.get(c) is None:
                        raise execution_error(path, "column '%s' is required" % c, 'columns', j)
            rows = rows
        elif op == 'row_number':
            for k, r in enumerate(rows):
                r[step['as']] = step['start'] + k
            rows = rows
        elif op == 'rank':
            distinct = []
            for r in rows:
                v = r.get(step['by'])
                if v is None:
                    continue
                if not is_num(v):
                    raise execution_error(path, 'rank requires numbers', 'by')
                if v not in distinct:
                    distinct.append(v)
            distinct.sort(reverse=step['desc'])
            for r in rows:
                v = r.get(step['by'])
                r[step['as']] = None if v is None else distinct.index(v) + 1
            rows = rows
        elif op == 'cumsum':
            total = 0
            for r in rows:
                v = r.get(step['column'])
                if v is not None and not is_num(v):
                    raise execution_error(path, 'cumsum requires numbers', 'column')
                total = num_result(total + (v or 0))
                r[step['as']] = total
            rows = rows
        elif op == 'lag':
            values = [r.get(step['column']) for r in rows]
            for k, r in enumerate(rows):
                if k >= step['n']:
                    r[step['as']] = values[k - step['n']]
                else:
                    r[step['as']] = step['default'] if 'default' in step else None
            rows = rows
        elif op == 'replace':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    continue
                if not isinstance(v, str):
                    raise execution_error(path, 'replace requires a string', 'column')
                r[step['column']] = v.replace(step['find'], step['with'])
            rows = rows
        elif op == 'regex_extract':
            rx = re.compile(step['pattern'])
            for r in rows:
                v = column_value(step, r, path)
                if v is not None and not isinstance(v, str):
                    raise execution_error(path, 'regex_extract requires a string', 'column')
                m = rx.search(v) if v is not None else None
                if m is not None and step['group'] > rx.groups:
                    raise execution_error(path, 'pattern has no group %d' % step['group'], 'group')
                r[step['as']] = m.group(step['group']) if m else None
            rows = rows
        elif op == 'regex_filter':
            rx = re.compile(step['pattern'])
            out = []
            for r in rows:
                v = r.get(step['column'])
                if (isinstance(v, str) and rx.search(v) is not None) != step['invert']:
                    out.append(r)
            rows = out
        elif op == 'substr':
            for r in rows:
                v = column_value(step, r, path)
                if v is not None and not isinstance(v, str):
                    raise execution_error(path, 'substr requires a string', 'column')
                if v is None:
                    r[step['as']] = None
                elif 'length' in step:
                    r[step['as']] = v[step['start']:step['start'] + step['length']]
                else:
                    r[step['as']] = v[step['start']:]
            rows = rows
        elif op == 'pad':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    continue
                s = to_text(v)
                short = max(0, step['width'] - len(s))
                padding = (step['fill'] * short)[:short]
                r[step['column']] = padding + s if step['side'] == 'left' else s + padding
            rows = rows
        elif op == 'length':
            for r in rows:
                v = column_value(step, r, path)
                if v is not None and not isinstance(v, (str, list, dict)):
                    raise execution_error(path, 'length requires a string, array or object', 'column')
                r[step['as']] = None if v is None else len(v)
            rows = rows
        elif op == 'json_parse':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    continue
                if not isinstance(v, str):
                    raise execution_error(path, 'json_parse requires a string', 'column')
                try:
                    r[step['column']] = json.loads(v)
                except ValueError:
                    raise execution_error(path, 'invalid JSON text', 'column')
            rows = rows
        elif op == 'json_dump':
            for r in rows:
                v = column_value(step, r, path)
                if v is not None:
                    r[step['column']] = json.dumps(v, sort_keys=True)
            rows = rows
        elif op == 'date_part':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    r[step['as']] = None
                    continue
                m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', v) if isinstance(v, str) else None
                if m is None:
                    raise execution_error(path, 'expected a YYYY-MM-DD date', 'column')
                r[step['as']] = int(m.group(('year', 'month', 'day').index(step['part']) + 1))
            rows = rows
        elif op == 'clip':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    continue
                if not is_num(v):
                    raise execution_error(path, 'clip requires a number', 'column')
                if 'min' in step and v < step['min']:
                    v = step['min']
                if 'max' in step and v > step['max']:
                    v = step['max']
                r[step['column']] = v
            rows = rows
        elif op == 'scale':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    continue
                if not is_num(v):
                    raise execution_error(path, 'scale requires a number', 'column')
                r[step['column']] = num_result(v * step['factor'] + step['offset'])
            rows = rows
        elif op == 'bucket':
            for r in rows:
                v = column_value(step, r, path)
                if v is not None and not is_num(v):
                    raise execution_error(path, 'bucket requires a number', 'column')
                r[step['as']] = None if v is None else sum(1 for e in step['edges'] if v >= e)
            rows = rows
        elif op == 'math':
            for r in rows:
                v = column_value(step, r, path)
                if v is None:
                    continue
                if not is_num(v) or (step['fn'] == 'sqrt' and v < 0):
                    raise execution_error(path, 'cannot apply %s to %s' % (step['fn'], json.dumps(v)), 'column')
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
            rows = rows
        elif op == 'between':
            for r in rows:
                v = r.get(step['column'])
                if v is not None and not is_num(v):
                    raise execution_error(path, 'between requires a number', 'column')
                r[step['as']] = v is not None and step['low'] <= v <= step['high']
            rows = rows
        elif op == 'branch':
            routed_rows = [[] for _ in step['branches']]
            for row in rows:
                for branch_idx, branch in enumerate(step['branches']):
                    when_expr = branch['when']
                    branch_path = '%s.branches[%d]' % (path, branch_idx)
                    matches = False
                    if when_expr == 'otherwise':
                        matches = True
                    else:
                        node = parse_expr(when_expr, branch_path + '.when')
                        matches = truthy(eval_at(node, row, branch_path + '.when'))
                    if matches:
                        routed_rows[branch_idx].append(row)
                        break
            rows = []
            for branch_idx, branch in enumerate(step['branches']):
                branch_path = '%s.branches[%d]' % (path, branch_idx)
                branch_steps_path = branch_path + '.steps'
                if routed_rows[branch_idx]:
                    branch_raw_steps = []
                    branch_executed = execute_steps(branch['steps'], branch_raw_steps, [dict(r) for r in routed_rows[branch_idx]], branch_steps_path)
                    rows.extend(branch_executed)
    return rows

def execute(steps, raw_steps, dataset):
    rows = [dict(r) for r in dataset]
    return execute_steps(steps, raw_steps, rows, 'pipeline.steps')
