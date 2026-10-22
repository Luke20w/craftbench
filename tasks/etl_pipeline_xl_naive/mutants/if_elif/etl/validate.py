"""Validation and normalization of pipeline steps."""

import re

from etl.errors import EtlError, schema_error
from etl.expr import parse_expr, is_num

def check_expr(text, path):
    parse_expr(text, path)

def get_str(step, key, path):
    """Required string field, trimmed and non-empty."""
    p = '%s.%s' % (path, key)
    if key not in step:
        raise schema_error("ETL_ERROR: missing required field '%s'" % key, p)
    v = step[key]
    if not isinstance(v, str):
        raise schema_error("ETL_ERROR: '%s' must be a string" % key, p)
    v = v.strip()
    if not v:
        raise schema_error("ETL_ERROR: '%s' must not be empty" % key, p)
    return v

def normalize_step(step, i, path=None):
    if path is None:
        path = 'pipeline.steps[%d]' % i
    if not isinstance(step, dict):
        raise schema_error('ETL_ERROR: step must be an object', path)
    if 'op' not in step:
        raise schema_error("ETL_ERROR: missing required field 'op'", path + '.op')
    if not isinstance(step['op'], str):
        raise schema_error("ETL_ERROR: 'op' must be a string", path + '.op')
    op = step['op'].strip().lower()
    if op not in ('select', 'filter', 'map', 'rename', 'limit', 'branch', 'drop', 'distinct', 'sort', 'offset', 'tail', 'fill', 'cast', 'round', 'concat', 'split', 'text', 'assert', 'coalesce', 'explode', 'group_count', 'summarize', 'lookup', 'set', 'ensure', 'reorder', 'prefix', 'nest', 'unnest', 'sample_every', 'take_while', 'skip_while', 'append', 'require', 'row_number', 'rank', 'cumsum', 'lag', 'replace', 'regex_extract', 'regex_filter', 'substr', 'pad', 'length', 'json_parse', 'json_dump', 'date_part', 'clip', 'scale', 'bucket', 'math', 'between'):
        raise EtlError('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % op, path + '.op')
    out = {'op': op}
    if op == 'select':
        cols = step.get('columns')
        p = path + '.columns'
        if 'columns' not in step:
            raise schema_error("ETL_ERROR: missing required field 'columns'", p)
        if not isinstance(cols, list):
            raise schema_error("ETL_ERROR: 'columns' must be an array", p)
        for j, c in enumerate(cols):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (p, j))
        out['columns'] = list(cols)
    elif op == 'filter':
        out['where'] = get_str(step, 'where', path)
        check_expr(out['where'], path + '.where')
    elif op == 'map':
        as_ = get_str(step, 'as', path)
        expr = get_str(step, 'expr', path)
        check_expr(expr, path + '.expr')
        out['as'] = as_
        out['expr'] = expr
    elif op == 'rename':
        if 'mapping' in step:
            p = path + '.mapping'
            m = step['mapping']
            if not isinstance(m, dict):
                raise schema_error("ETL_ERROR: 'mapping' must be an object", p)
            for k, v in m.items():
                if not isinstance(v, str):
                    raise schema_error('ETL_ERROR: mapping values must be strings', '%s.%s' % (p, k))
            out['mapping'] = dict(m)
        elif 'from' in step or 'to' in step:
            out['mapping'] = {get_str(step, 'from', path): get_str(step, 'to', path)}
        else:
            raise schema_error("ETL_ERROR: rename requires 'from' and 'to' or 'mapping'", path)
    elif op == 'limit':
        p = path + '.n'
        if 'n' not in step:
            raise schema_error("ETL_ERROR: missing required field 'n'", p)
        n = step['n']
        if isinstance(n, bool) or not isinstance(n, int):
            raise schema_error("ETL_ERROR: 'n' must be an integer", p)
        if n < 0:
            raise schema_error("ETL_ERROR: 'n' must be >= 0", p)
        out['n'] = n
    elif op in ('drop', 'distinct', 'concat', 'text'):
        if op == 'concat':
            out['as'] = get_str(step, 'as', path)
        p = path + '.columns'
        if 'columns' not in step:
            if op != 'distinct':
                raise schema_error("ETL_ERROR: missing required field 'columns'", p)
        else:
            cols = step['columns']
            if not isinstance(cols, list):
                raise schema_error("ETL_ERROR: 'columns' must be an array", p)
            if op == 'concat' and len(cols) == 0:
                raise schema_error("ETL_ERROR: 'columns' must be non-empty", p)
            for j, c in enumerate(cols):
                if not isinstance(c, str):
                    raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (p, j))
            out['columns'] = list(cols)
        if op == 'concat':
            sep = step.get('sep', '')
            if not isinstance(sep, str):
                raise schema_error("ETL_ERROR: 'sep' must be a string", path + '.sep')
            out['sep'] = sep
        if op == 'text':
            fn = get_str(step, 'fn', path).lower()
            if fn not in ('upper', 'lower', 'trim'):
                raise schema_error("ETL_ERROR: 'fn' must be one of upper, lower, trim", path + '.fn')
            out['fn'] = fn
    elif op == 'sort':
        out['by'] = get_str(step, 'by', path)
        desc = step.get('desc', False)
        if not isinstance(desc, bool):
            raise schema_error("ETL_ERROR: 'desc' must be a boolean", path + '.desc')
        out['desc'] = desc
    elif op in ('offset', 'tail'):
        p = path + '.n'
        if 'n' not in step:
            raise schema_error("ETL_ERROR: missing required field 'n'", p)
        n = step['n']
        if isinstance(n, bool) or not isinstance(n, int):
            raise schema_error("ETL_ERROR: 'n' must be an integer", p)
        if n < 0:
            raise schema_error("ETL_ERROR: 'n' must be >= 0", p)
        out['n'] = n
    elif op == 'fill':
        out['column'] = get_str(step, 'column', path)
        out['value'] = get_str(step, 'value', path)
        check_expr(out['value'], path + '.value')
    elif op == 'cast':
        out['column'] = get_str(step, 'column', path)
        to = get_str(step, 'to', path).lower()
        if to not in ('int', 'float', 'string', 'bool'):
            raise schema_error("ETL_ERROR: 'to' must be one of int, float, string, bool", path + '.to')
        out['to'] = to
    elif op == 'round':
        out['column'] = get_str(step, 'column', path)
        digits = step.get('digits', 0)
        if isinstance(digits, bool) or not isinstance(digits, int):
            raise schema_error("ETL_ERROR: 'digits' must be an integer", path + '.digits')
        if digits < 0:
            raise schema_error("ETL_ERROR: 'digits' must be >= 0", path + '.digits')
        out['digits'] = digits
    elif op == 'split':
        out['column'] = get_str(step, 'column', path)
        if 'sep' not in step:
            raise schema_error("ETL_ERROR: missing required field 'sep'", path + '.sep')
        sep = step['sep']
        if not isinstance(sep, str):
            raise schema_error("ETL_ERROR: 'sep' must be a string", path + '.sep')
        if not sep:
            raise schema_error("ETL_ERROR: 'sep' must not be empty", path + '.sep')
        out['sep'] = sep
        p = path + '.into'
        if 'into' not in step:
            raise schema_error("ETL_ERROR: missing required field 'into'", p)
        into = step['into']
        if not isinstance(into, list):
            raise schema_error("ETL_ERROR: 'into' must be an array", p)
        if len(into) == 0:
            raise schema_error("ETL_ERROR: 'into' must be non-empty", p)
        for j, c in enumerate(into):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (p, j))
        out['into'] = list(into)
    elif op == 'assert':
        out['where'] = get_str(step, 'where', path)
        check_expr(out['where'], path + '.where')
        message = step.get('message', 'assertion failed')
        if not isinstance(message, str):
            raise schema_error("ETL_ERROR: 'message' must be a string", path + '.message')
        out['message'] = message
    elif op == 'coalesce':
        out['as'] = get_str(step, 'as', path)
        p = path + '.exprs'
        if 'exprs' not in step:
            raise schema_error("ETL_ERROR: missing required field 'exprs'", p)
        exprs = step['exprs']
        if not isinstance(exprs, list):
            raise schema_error("ETL_ERROR: 'exprs' must be an array", p)
        if len(exprs) == 0:
            raise schema_error("ETL_ERROR: 'exprs' must be non-empty", p)
        normalized_exprs = []
        for k, e in enumerate(exprs):
            ep = '%s[%d]' % (p, k)
            if not isinstance(e, str):
                raise schema_error('ETL_ERROR: exprs entries must be strings', ep)
            e = e.strip()
            if not e:
                raise schema_error('ETL_ERROR: exprs entries must not be empty', ep)
            check_expr(e, ep)
            normalized_exprs.append(e)
        out['exprs'] = normalized_exprs
    elif op == 'explode':
        out['column'] = get_str(step, 'column', path)
    elif op == 'group_count':
        if 'by' not in step:
            raise schema_error("ETL_ERROR: missing required field 'by'", path + '.by')
        if not isinstance(step['by'], list):
            raise schema_error("ETL_ERROR: 'by' must be an array", path + '.by')
        if len(step['by']) == 0:
            raise schema_error("ETL_ERROR: 'by' must be non-empty", path + '.by')
        for j, c in enumerate(step['by']):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.by', j))
        out['by'] = list(step['by'])
        out['as'] = get_str(step, 'as', path)
    elif op == 'summarize':
        if 'by' in step:
            if not isinstance(step['by'], list):
                raise schema_error("ETL_ERROR: 'by' must be an array", path + '.by')
            for j, c in enumerate(step['by']):
                if not isinstance(c, str):
                    raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.by', j))
            out['by'] = list(step['by'])
        else:
            out['by'] = []
        if 'metrics' not in step:
            raise schema_error("ETL_ERROR: missing required field 'metrics'", path + '.metrics')
        if not isinstance(step['metrics'], list):
            raise schema_error("ETL_ERROR: 'metrics' must be an array", path + '.metrics')
        if len(step['metrics']) == 0:
            raise schema_error("ETL_ERROR: 'metrics' must be non-empty", path + '.metrics')
        out['metrics'] = []
        for j, item in enumerate(step['metrics']):
            ip = '%s[%d]' % (path + '.metrics', j)
            if not isinstance(item, dict):
                raise schema_error('ETL_ERROR: metrics entry must be an object', ip)
            entry = {}
            entry['as'] = get_str(item, 'as', ip)
            entry['fn'] = get_str(item, 'fn', ip)
            entry['fn'] = entry['fn'].lower()
            if entry['fn'] not in ('sum', 'min', 'max', 'avg', 'count'):
                raise schema_error("ETL_ERROR: 'fn' must be one of sum, min, max, avg, count", ip + '.fn')
            if 'column' in item:
                if not isinstance(item['column'], str):
                    raise schema_error("ETL_ERROR: 'column' must be a string", ip + '.column')
                entry['column'] = item['column']
            out['metrics'].append(entry)
    elif op == 'lookup':
        out['column'] = get_str(step, 'column', path)
        out['as'] = get_str(step, 'as', path)
        if 'table' not in step:
            raise schema_error("ETL_ERROR: missing required field 'table'", path + '.table')
        if not isinstance(step['table'], dict):
            raise schema_error("ETL_ERROR: 'table' must be an object", path + '.table')
        for k, x in step['table'].items():
            if not (x is None or isinstance(x, (bool, int, float, str))):
                raise schema_error("ETL_ERROR: 'table' values must be JSON scalars", '%s.%s' % (path + '.table', k))
        out['table'] = dict(step['table'])
        if 'default' in step:
            if not (step['default'] is None or isinstance(step['default'], (bool, int, float, str))):
                raise schema_error("ETL_ERROR: 'default' must be a JSON scalar", path + '.default')
            out['default'] = step['default']
    elif op == 'set':
        out['column'] = get_str(step, 'column', path)
        if 'value' not in step:
            raise schema_error("ETL_ERROR: missing required field 'value'", path + '.value')
        if not (step['value'] is None or isinstance(step['value'], (bool, int, float, str))):
            raise schema_error("ETL_ERROR: 'value' must be a JSON scalar", path + '.value')
        out['value'] = step['value']
    elif op == 'ensure':
        if 'columns' not in step:
            raise schema_error("ETL_ERROR: missing required field 'columns'", path + '.columns')
        if not isinstance(step['columns'], list):
            raise schema_error("ETL_ERROR: 'columns' must be an array", path + '.columns')
        if len(step['columns']) == 0:
            raise schema_error("ETL_ERROR: 'columns' must be non-empty", path + '.columns')
        for j, c in enumerate(step['columns']):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.columns', j))
        out['columns'] = list(step['columns'])
        if 'value' in step:
            if not (step['value'] is None or isinstance(step['value'], (bool, int, float, str))):
                raise schema_error("ETL_ERROR: 'value' must be a JSON scalar", path + '.value')
            out['value'] = step['value']
        else:
            out['value'] = None
    elif op == 'reorder':
        if 'columns' not in step:
            raise schema_error("ETL_ERROR: missing required field 'columns'", path + '.columns')
        if not isinstance(step['columns'], list):
            raise schema_error("ETL_ERROR: 'columns' must be an array", path + '.columns')
        if len(step['columns']) == 0:
            raise schema_error("ETL_ERROR: 'columns' must be non-empty", path + '.columns')
        for j, c in enumerate(step['columns']):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.columns', j))
        out['columns'] = list(step['columns'])
    elif op == 'prefix':
        if 'prefix' not in step:
            raise schema_error("ETL_ERROR: missing required field 'prefix'", path + '.prefix')
        if not isinstance(step['prefix'], str):
            raise schema_error("ETL_ERROR: 'prefix' must be a string", path + '.prefix')
        if not step['prefix']:
            raise schema_error("ETL_ERROR: 'prefix' must not be empty", path + '.prefix')
        out['prefix'] = step['prefix']
        if 'columns' in step:
            if not isinstance(step['columns'], list):
                raise schema_error("ETL_ERROR: 'columns' must be an array", path + '.columns')
            for j, c in enumerate(step['columns']):
                if not isinstance(c, str):
                    raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.columns', j))
            out['columns'] = list(step['columns'])
    elif op == 'nest':
        if 'columns' not in step:
            raise schema_error("ETL_ERROR: missing required field 'columns'", path + '.columns')
        if not isinstance(step['columns'], list):
            raise schema_error("ETL_ERROR: 'columns' must be an array", path + '.columns')
        if len(step['columns']) == 0:
            raise schema_error("ETL_ERROR: 'columns' must be non-empty", path + '.columns')
        for j, c in enumerate(step['columns']):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.columns', j))
        out['columns'] = list(step['columns'])
        out['as'] = get_str(step, 'as', path)
    elif op == 'unnest':
        out['column'] = get_str(step, 'column', path)
        if 'prefix' in step:
            if not isinstance(step['prefix'], str):
                raise schema_error("ETL_ERROR: 'prefix' must be a string", path + '.prefix')
            out['prefix'] = step['prefix']
        else:
            out['prefix'] = ''
    elif op == 'sample_every':
        if 'n' not in step:
            raise schema_error("ETL_ERROR: missing required field 'n'", path + '.n')
        if isinstance(step['n'], bool) or not isinstance(step['n'], int):
            raise schema_error("ETL_ERROR: 'n' must be an integer", path + '.n')
        if step['n'] < 1:
            raise schema_error("ETL_ERROR: 'n' must be >= 1", path + '.n')
        out['n'] = step['n']
    elif op == 'take_while':
        out['where'] = get_str(step, 'where', path)
        check_expr(out['where'], path + '.where')
    elif op == 'skip_while':
        out['where'] = get_str(step, 'where', path)
        check_expr(out['where'], path + '.where')
    elif op == 'append':
        if 'rows' not in step:
            raise schema_error("ETL_ERROR: missing required field 'rows'", path + '.rows')
        if not isinstance(step['rows'], list):
            raise schema_error("ETL_ERROR: 'rows' must be an array", path + '.rows')
        for j, x in enumerate(step['rows']):
            if not isinstance(x, dict):
                raise schema_error("ETL_ERROR: 'rows' entries must be objects", '%s[%d]' % (path + '.rows', j))
        out['rows'] = [dict(x) for x in step['rows']]
    elif op == 'require':
        if 'columns' not in step:
            raise schema_error("ETL_ERROR: missing required field 'columns'", path + '.columns')
        if not isinstance(step['columns'], list):
            raise schema_error("ETL_ERROR: 'columns' must be an array", path + '.columns')
        if len(step['columns']) == 0:
            raise schema_error("ETL_ERROR: 'columns' must be non-empty", path + '.columns')
        for j, c in enumerate(step['columns']):
            if not isinstance(c, str):
                raise schema_error('ETL_ERROR: column names must be strings', '%s[%d]' % (path + '.columns', j))
        out['columns'] = list(step['columns'])
    elif op == 'row_number':
        out['as'] = get_str(step, 'as', path)
        if 'start' in step:
            if isinstance(step['start'], bool) or not isinstance(step['start'], int):
                raise schema_error("ETL_ERROR: 'start' must be an integer", path + '.start')
            out['start'] = step['start']
        else:
            out['start'] = 1
    elif op == 'rank':
        out['by'] = get_str(step, 'by', path)
        out['as'] = get_str(step, 'as', path)
        if 'desc' in step:
            if not isinstance(step['desc'], bool):
                raise schema_error("ETL_ERROR: 'desc' must be a boolean", path + '.desc')
            out['desc'] = step['desc']
        else:
            out['desc'] = False
    elif op == 'cumsum':
        out['column'] = get_str(step, 'column', path)
        out['as'] = get_str(step, 'as', path)
    elif op == 'lag':
        out['column'] = get_str(step, 'column', path)
        out['as'] = get_str(step, 'as', path)
        if 'n' in step:
            if isinstance(step['n'], bool) or not isinstance(step['n'], int):
                raise schema_error("ETL_ERROR: 'n' must be an integer", path + '.n')
            if step['n'] < 0:
                raise schema_error("ETL_ERROR: 'n' must be >= 0", path + '.n')
            out['n'] = step['n']
        else:
            out['n'] = 1
        if 'default' in step:
            if not (step['default'] is None or isinstance(step['default'], (bool, int, float, str))):
                raise schema_error("ETL_ERROR: 'default' must be a JSON scalar", path + '.default')
            out['default'] = step['default']
    elif op == 'replace':
        out['column'] = get_str(step, 'column', path)
        if 'find' not in step:
            raise schema_error("ETL_ERROR: missing required field 'find'", path + '.find')
        if not isinstance(step['find'], str):
            raise schema_error("ETL_ERROR: 'find' must be a string", path + '.find')
        if not step['find']:
            raise schema_error("ETL_ERROR: 'find' must not be empty", path + '.find')
        out['find'] = step['find']
        if 'with' not in step:
            raise schema_error("ETL_ERROR: missing required field 'with'", path + '.with')
        if not isinstance(step['with'], str):
            raise schema_error("ETL_ERROR: 'with' must be a string", path + '.with')
        out['with'] = step['with']
    elif op == 'regex_extract':
        out['column'] = get_str(step, 'column', path)
        if 'pattern' not in step:
            raise schema_error("ETL_ERROR: missing required field 'pattern'", path + '.pattern')
        if not isinstance(step['pattern'], str):
            raise schema_error("ETL_ERROR: 'pattern' must be a string", path + '.pattern')
        if not step['pattern']:
            raise schema_error("ETL_ERROR: 'pattern' must not be empty", path + '.pattern')
        try:
            re.compile(step['pattern'])
        except re.error:
            raise schema_error("ETL_ERROR: 'pattern' must be a valid regular expression", path + '.pattern')
        out['pattern'] = step['pattern']
        out['as'] = get_str(step, 'as', path)
        if 'group' in step:
            if isinstance(step['group'], bool) or not isinstance(step['group'], int):
                raise schema_error("ETL_ERROR: 'group' must be an integer", path + '.group')
            if step['group'] < 0:
                raise schema_error("ETL_ERROR: 'group' must be >= 0", path + '.group')
            out['group'] = step['group']
        else:
            out['group'] = 0
    elif op == 'regex_filter':
        out['column'] = get_str(step, 'column', path)
        if 'pattern' not in step:
            raise schema_error("ETL_ERROR: missing required field 'pattern'", path + '.pattern')
        if not isinstance(step['pattern'], str):
            raise schema_error("ETL_ERROR: 'pattern' must be a string", path + '.pattern')
        if not step['pattern']:
            raise schema_error("ETL_ERROR: 'pattern' must not be empty", path + '.pattern')
        try:
            re.compile(step['pattern'])
        except re.error:
            raise schema_error("ETL_ERROR: 'pattern' must be a valid regular expression", path + '.pattern')
        out['pattern'] = step['pattern']
        if 'invert' in step:
            if not isinstance(step['invert'], bool):
                raise schema_error("ETL_ERROR: 'invert' must be a boolean", path + '.invert')
            out['invert'] = step['invert']
        else:
            out['invert'] = False
    elif op == 'substr':
        out['column'] = get_str(step, 'column', path)
        out['as'] = get_str(step, 'as', path)
        if 'start' not in step:
            raise schema_error("ETL_ERROR: missing required field 'start'", path + '.start')
        if isinstance(step['start'], bool) or not isinstance(step['start'], int):
            raise schema_error("ETL_ERROR: 'start' must be an integer", path + '.start')
        if step['start'] < 0:
            raise schema_error("ETL_ERROR: 'start' must be >= 0", path + '.start')
        out['start'] = step['start']
        if 'length' in step:
            if isinstance(step['length'], bool) or not isinstance(step['length'], int):
                raise schema_error("ETL_ERROR: 'length' must be an integer", path + '.length')
            if step['length'] < 0:
                raise schema_error("ETL_ERROR: 'length' must be >= 0", path + '.length')
            out['length'] = step['length']
    elif op == 'pad':
        out['column'] = get_str(step, 'column', path)
        if 'width' not in step:
            raise schema_error("ETL_ERROR: missing required field 'width'", path + '.width')
        if isinstance(step['width'], bool) or not isinstance(step['width'], int):
            raise schema_error("ETL_ERROR: 'width' must be an integer", path + '.width')
        if step['width'] < 0:
            raise schema_error("ETL_ERROR: 'width' must be >= 0", path + '.width')
        out['width'] = step['width']
        if 'fill' in step:
            if not isinstance(step['fill'], str):
                raise schema_error("ETL_ERROR: 'fill' must be a string", path + '.fill')
            if not step['fill']:
                raise schema_error("ETL_ERROR: 'fill' must not be empty", path + '.fill')
            out['fill'] = step['fill']
        else:
            out['fill'] = ' '
        if 'side' in step:
            out['side'] = get_str(step, 'side', path)
            out['side'] = out['side'].lower()
            if out['side'] not in ('left', 'right'):
                raise schema_error("ETL_ERROR: 'side' must be one of left, right", path + '.side')
        else:
            out['side'] = 'left'
    elif op == 'length':
        out['column'] = get_str(step, 'column', path)
        out['as'] = get_str(step, 'as', path)
    elif op == 'json_parse':
        out['column'] = get_str(step, 'column', path)
    elif op == 'json_dump':
        out['column'] = get_str(step, 'column', path)
    elif op == 'date_part':
        out['column'] = get_str(step, 'column', path)
        out['part'] = get_str(step, 'part', path)
        out['part'] = out['part'].lower()
        if out['part'] not in ('year', 'month', 'day'):
            raise schema_error("ETL_ERROR: 'part' must be one of year, month, day", path + '.part')
        out['as'] = get_str(step, 'as', path)
    elif op == 'clip':
        out['column'] = get_str(step, 'column', path)
        if 'min' in step:
            if not is_num(step['min']):
                raise schema_error("ETL_ERROR: 'min' must be a number", path + '.min')
            out['min'] = step['min']
        if 'max' in step:
            if not is_num(step['max']):
                raise schema_error("ETL_ERROR: 'max' must be a number", path + '.max')
            out['max'] = step['max']
    elif op == 'scale':
        out['column'] = get_str(step, 'column', path)
        if 'factor' not in step:
            raise schema_error("ETL_ERROR: missing required field 'factor'", path + '.factor')
        if not is_num(step['factor']):
            raise schema_error("ETL_ERROR: 'factor' must be a number", path + '.factor')
        out['factor'] = step['factor']
        if 'offset' in step:
            if not is_num(step['offset']):
                raise schema_error("ETL_ERROR: 'offset' must be a number", path + '.offset')
            out['offset'] = step['offset']
        else:
            out['offset'] = 0
    elif op == 'bucket':
        out['column'] = get_str(step, 'column', path)
        out['as'] = get_str(step, 'as', path)
        if 'edges' not in step:
            raise schema_error("ETL_ERROR: missing required field 'edges'", path + '.edges')
        if not isinstance(step['edges'], list):
            raise schema_error("ETL_ERROR: 'edges' must be an array", path + '.edges')
        if len(step['edges']) == 0:
            raise schema_error("ETL_ERROR: 'edges' must be non-empty", path + '.edges')
        for j, x in enumerate(step['edges']):
            if not is_num(x):
                raise schema_error("ETL_ERROR: 'edges' entries must be numbers", '%s[%d]' % (path + '.edges', j))
        out['edges'] = list(step['edges'])
    elif op == 'math':
        out['column'] = get_str(step, 'column', path)
        out['fn'] = get_str(step, 'fn', path)
        out['fn'] = out['fn'].lower()
        if out['fn'] not in ('abs', 'floor', 'ceil', 'sqrt', 'neg'):
            raise schema_error("ETL_ERROR: 'fn' must be one of abs, floor, ceil, sqrt, neg", path + '.fn')
    elif op == 'between':
        out['column'] = get_str(step, 'column', path)
        if 'low' not in step:
            raise schema_error("ETL_ERROR: missing required field 'low'", path + '.low')
        if not is_num(step['low']):
            raise schema_error("ETL_ERROR: 'low' must be a number", path + '.low')
        out['low'] = step['low']
        if 'high' not in step:
            raise schema_error("ETL_ERROR: missing required field 'high'", path + '.high')
        if not is_num(step['high']):
            raise schema_error("ETL_ERROR: 'high' must be a number", path + '.high')
        out['high'] = step['high']
        out['as'] = get_str(step, 'as', path)
    elif op == 'branch':
        p = path + '.branches'
        if 'branches' not in step:
            raise schema_error("ETL_ERROR: missing required field 'branches'", p)
        branches = step['branches']
        if not isinstance(branches, list):
            raise schema_error("ETL_ERROR: 'branches' must be an array", p)
        if len(branches) == 0:
            raise schema_error("ETL_ERROR: 'branches' must be non-empty", p)
        otherwise_count = sum((1 for b in branches if isinstance(b, dict) and b.get('when') == 'otherwise'))
        if otherwise_count > 1:
            raise EtlError('MALFORMED_STEP', "ETL_ERROR: at most one 'otherwise' branch allowed", p)
        if otherwise_count == 1:
            otherwise_idx = next((j for j, b in enumerate(branches) if isinstance(b, dict) and b.get('when') == 'otherwise'))
            if otherwise_idx != len(branches) - 1:
                raise EtlError('MALFORMED_STEP', "ETL_ERROR: 'otherwise' branch must be last", p)
        normalized_branches = []
        for j, b in enumerate(branches):
            bp = '%s[%d]' % (p, j)
            if not isinstance(b, dict):
                raise schema_error('ETL_ERROR: branch must be an object', bp)
            if 'when' not in b:
                raise schema_error("ETL_ERROR: missing required field 'when'", bp + '.when')
            if not isinstance(b['when'], str):
                raise schema_error("ETL_ERROR: 'when' must be a string", bp + '.when')
            when = b['when']
            if when != 'otherwise':
                check_expr(when, bp + '.when')
            if 'steps' not in b:
                raise schema_error("ETL_ERROR: missing required field 'steps'", bp + '.steps')
            if not isinstance(b['steps'], list):
                raise schema_error("ETL_ERROR: 'steps' must be an array", bp + '.steps')
            normalized_branch = {'when': when}
            if 'id' in b:
                if not isinstance(b['id'], str):
                    raise schema_error("ETL_ERROR: 'id' must be a string", bp + '.id')
                normalized_branch['id'] = b['id']
            normalized_steps = []
            for k, sub_step in enumerate(b['steps']):
                sub_path = '%s[%d]' % (bp + '.steps', k)
                normalized_steps.append(normalize_step(sub_step, k, path=sub_path))
            normalized_branch['steps'] = normalized_steps
            normalized_branches.append(normalized_branch)
        out['branches'] = normalized_branches
        merge = step.get('merge', {})
        if not isinstance(merge, dict):
            raise schema_error("ETL_ERROR: 'merge' must be an object", path + '.merge')
        strategy = merge.get('strategy', 'concat')
        if strategy != 'concat':
            raise schema_error("ETL_ERROR: only 'concat' merge strategy is supported", path + '.merge.strategy')
        out['merge'] = {'strategy': strategy}
    ordered = {'op': out.pop('op')}
    for k in sorted(out):
        ordered[k] = out[k]
    return ordered
