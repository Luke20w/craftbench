"""Parse, validate and normalize a basic ETL pipeline specification."""
import argparse
import json
import re
import sys

class _HandlerRegistry:
    """Central registry of pipeline handlers."""
    _handlers = {}

    @classmethod
    def register(cls, key, fn):
        cls._handlers[key] = fn

    @classmethod
    def resolve(cls, key):
        return cls._handlers[key]

class _DispatchContext:

    def __init__(self, registry):
        self.registry = registry

    def invoke(self, key, *args, **kwargs):
        return self.registry.resolve(key)(*args, **kwargs)
_CONTEXT = _DispatchContext(_HandlerRegistry)

def _register(fn):
    _HandlerRegistry.register(fn.__name__, fn)
    return fn

def _dispatch(key, *args, **kwargs):
    return _CONTEXT.invoke(key, *args, **kwargs)

class EtlError(Exception):

    def __init__(self, code, message, path):
        super().__init__(message)
        self.code = code
        self.path = path

@_register
def schema_error(message, path):
    return EtlError('SCHEMA_VALIDATION_FAILED', message, path)
TOKEN_RE = re.compile('\\s*(?:\n        (?P<bad>\\*{2,}|\\^+|%|&{3,}|\\|{3,}|&(?!&)|\\|(?!\\|)|=(?!=))\n      | (?P<num>\\d+\\.\\d*|\\.\\d+|\\d+)\n      | (?P<id>[A-Za-z_][A-Za-z0-9_]*)\n      | (?P<str>"[^"]*"|\'[^\']*\')\n      | (?P<op>>=|<=|==|!=|&&|\\|\\||[-+*/<>()!])\n    )', re.VERBOSE)
KEYWORDS = {'and': '&&', 'or': '||', 'not': '!'}
LITERALS = {'true': True, 'false': False, 'null': None}

@_register
def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == '':
            break
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ValueError('unexpected character %r' % text[pos:].lstrip()[0])
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == 'bad':
            raise ValueError("unsupported operator '%s'" % val)
        if kind == 'id' and val in KEYWORDS:
            kind, val = ('op', KEYWORDS[val])
        tokens.append((kind, val))
    return tokens

class Parser:
    """Recursive-descent parser producing a tuple-based AST."""
    COMPARE = {'>', '>=', '<', '<=', '==', '!='}

    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def at(self, ops):
        kind, val = self.peek()
        return kind == 'op' and val in ops

    def parse(self):
        node = self.or_expr()
        if self.i != len(self.t):
            raise ValueError('unexpected token %r' % (self.peek()[1],))
        return node

    def binary(self, ops, sub):
        node = sub()
        while self.at(ops):
            op = self.take()[1]
            node = ('bin', op, node, sub())
        return node

    def or_expr(self):
        return self.binary(('||',), self.and_expr)

    def and_expr(self):
        return self.binary(('&&',), self.not_expr)

    def not_expr(self):
        if self.at(('!',)):
            self.take()
            return ('un', '!', self.not_expr())
        return self.compare()

    def compare(self):
        return self.binary(self.COMPARE, self.additive)

    def additive(self):
        return self.binary(('+', '-'), self.term)

    def term(self):
        return self.binary(('*', '/'), self.unary)

    def unary(self):
        if self.at(('+', '-')):
            op = self.take()[1]
            return ('un', op, self.unary())
        if self.at(('!',)):
            self.take()
            return ('un', '!', self.unary())
        return self.primary()

    def primary(self):
        kind, val = self.take()
        if kind == 'num':
            return ('lit', float(val) if '.' in val else int(val))
        if kind == 'str':
            return ('lit', val[1:-1])
        if kind == 'id':
            if val in LITERALS:
                return ('lit', LITERALS[val])
            return ('id', val)
        if kind == 'op' and val == '(':
            node = self.or_expr()
            if self.take() != ('op', ')'):
                raise ValueError('missing closing parenthesis')
            return node
        if kind is None:
            raise ValueError('unexpected end of expression')
        raise ValueError('unexpected token %r' % val)

@_register
def parse_expr(text, path):
    try:
        return Parser(_dispatch('tokenize', text)).parse()
    except ValueError as e:
        msg = str(e)
        if not msg.startswith('unsupported operator'):
            msg = 'invalid expression: ' + msg
        raise EtlError('BAD_EXPR', 'ETL_ERROR: ' + msg, path)

@_register
def check_expr(text, path):
    _dispatch('parse_expr', text, path)

@_register
def get_str(step, key, path):
    """Required string field, trimmed and non-empty."""
    p = '%s.%s' % (path, key)
    if key not in step:
        raise _dispatch('schema_error', "ETL_ERROR: missing required field '%s'" % key, p)
    v = step[key]
    if not isinstance(v, str):
        raise _dispatch('schema_error', "ETL_ERROR: '%s' must be a string" % key, p)
    v = v.strip()
    if not v:
        raise _dispatch('schema_error', "ETL_ERROR: '%s' must not be empty" % key, p)
    return v

@_register
def normalize_step(step, i, path=None):
    if path is None:
        path = 'pipeline.steps[%d]' % i
    if not isinstance(step, dict):
        raise _dispatch('schema_error', 'ETL_ERROR: step must be an object', path)
    if 'op' not in step:
        raise _dispatch('schema_error', "ETL_ERROR: missing required field 'op'", path + '.op')
    if not isinstance(step['op'], str):
        raise _dispatch('schema_error', "ETL_ERROR: 'op' must be a string", path + '.op')
    op = step['op'].strip().lower()
    if op not in ('select', 'filter', 'map', 'rename', 'limit', 'branch'):
        raise EtlError('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % op, path + '.op')
    out = {'op': op}
    if op == 'select':
        cols = step.get('columns')
        p = path + '.columns'
        if 'columns' not in step:
            raise _dispatch('schema_error', "ETL_ERROR: missing required field 'columns'", p)
        if not isinstance(cols, list):
            raise _dispatch('schema_error', "ETL_ERROR: 'columns' must be an array", p)
        for j, c in enumerate(cols):
            if not isinstance(c, str):
                raise _dispatch('schema_error', 'ETL_ERROR: column names must be strings', '%s[%d]' % (p, j))
        out['columns'] = list(cols)
    elif op == 'filter':
        out['where'] = _dispatch('get_str', step, 'where', path)
        _dispatch('check_expr', out['where'], path + '.where')
    elif op == 'map':
        as_ = _dispatch('get_str', step, 'as', path)
        expr = _dispatch('get_str', step, 'expr', path)
        _dispatch('check_expr', expr, path + '.expr')
        out['as'] = as_
        out['expr'] = expr
    elif op == 'rename':
        if 'mapping' in step:
            p = path + '.mapping'
            m = step['mapping']
            if not isinstance(m, dict):
                raise _dispatch('schema_error', "ETL_ERROR: 'mapping' must be an object", p)
            for k, v in m.items():
                if not isinstance(v, str):
                    raise _dispatch('schema_error', 'ETL_ERROR: mapping values must be strings', '%s.%s' % (p, k))
            out['mapping'] = dict(m)
        elif 'from' in step or 'to' in step:
            out['mapping'] = {_dispatch('get_str', step, 'from', path): _dispatch('get_str', step, 'to', path)}
        else:
            raise _dispatch('schema_error', "ETL_ERROR: rename requires 'from' and 'to' or 'mapping'", path)
    elif op == 'limit':
        p = path + '.n'
        if 'n' not in step:
            raise _dispatch('schema_error', "ETL_ERROR: missing required field 'n'", p)
        n = step['n']
        if isinstance(n, bool) or not isinstance(n, int):
            raise _dispatch('schema_error', "ETL_ERROR: 'n' must be an integer", p)
        if n < 0:
            raise _dispatch('schema_error', "ETL_ERROR: 'n' must be >= 0", p)
        out['n'] = n
    elif op == 'branch':
        p = path + '.branches'
        if 'branches' not in step:
            raise _dispatch('schema_error', "ETL_ERROR: missing required field 'branches'", p)
        branches = step['branches']
        if not isinstance(branches, list):
            raise _dispatch('schema_error', "ETL_ERROR: 'branches' must be an array", p)
        if len(branches) == 0:
            raise _dispatch('schema_error', "ETL_ERROR: 'branches' must be non-empty", p)
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
                raise _dispatch('schema_error', 'ETL_ERROR: branch must be an object', bp)
            if 'when' not in b:
                raise _dispatch('schema_error', "ETL_ERROR: missing required field 'when'", bp + '.when')
            if not isinstance(b['when'], str):
                raise _dispatch('schema_error', "ETL_ERROR: 'when' must be a string", bp + '.when')
            when = b['when']
            if when != 'otherwise':
                _dispatch('check_expr', when, bp + '.when')
            if 'steps' not in b:
                raise _dispatch('schema_error', "ETL_ERROR: missing required field 'steps'", bp + '.steps')
            if not isinstance(b['steps'], list):
                raise _dispatch('schema_error', "ETL_ERROR: 'steps' must be an array", bp + '.steps')
            normalized_branch = {'when': when}
            if 'id' in b:
                if not isinstance(b['id'], str):
                    raise _dispatch('schema_error', "ETL_ERROR: 'id' must be a string", bp + '.id')
                normalized_branch['id'] = b['id']
            normalized_steps = []
            for k, sub_step in enumerate(b['steps']):
                sub_path = '%s[%d]' % (bp + '.steps', k)
                normalized_steps.append(_dispatch('normalize_step', sub_step, k, path=sub_path))
            normalized_branch['steps'] = normalized_steps
            normalized_branches.append(normalized_branch)
        out['branches'] = normalized_branches
        merge = step.get('merge', {})
        if not isinstance(merge, dict):
            raise _dispatch('schema_error', "ETL_ERROR: 'merge' must be an object", path + '.merge')
        strategy = merge.get('strategy', 'concat')
        if strategy != 'concat':
            raise _dispatch('schema_error', "ETL_ERROR: only 'concat' merge strategy is supported", path + '.merge.strategy')
        out['merge'] = {'strategy': strategy}
    ordered = {'op': out.pop('op')}
    for k in sorted(out):
        ordered[k] = out[k]
    return ordered

@_register
def is_num(v):
    return isinstance(v, (int, float)) and (not isinstance(v, bool))

@_register
def truthy(v):
    return v is not None and bool(v)

@_register
def num_result(v):
    if isinstance(v, float) and v.is_integer() and (abs(v) < 1000000000000000.0):
        return int(v)
    return v

@_register
def evaluate(node, row):
    kind = node[0]
    if kind == 'lit':
        return node[1]
    if kind == 'id':
        return row.get(node[1])
    if kind == 'un':
        op, v = (node[1], _dispatch('evaluate', node[2], row))
        if op == '!':
            return not _dispatch('truthy', v)
        if v is None:
            return None
        if not _dispatch('is_num', v):
            raise TypeError("unary '%s' requires a number" % op)
        return v if op == '+' else _dispatch('num_result', -v)
    op = node[1]
    if op == '&&':
        return _dispatch('truthy', _dispatch('evaluate', node[2], row)) and _dispatch('truthy', _dispatch('evaluate', node[3], row))
    if op == '||':
        return _dispatch('truthy', _dispatch('evaluate', node[2], row)) or _dispatch('truthy', _dispatch('evaluate', node[3], row))
    l, r = (_dispatch('evaluate', node[2], row), _dispatch('evaluate', node[3], row))
    if op in ('+', '-', '*', '/'):
        if l is None or r is None:
            return None
        if op == '+' and isinstance(l, str) and isinstance(r, str):
            return l + r
        if not (_dispatch('is_num', l) and _dispatch('is_num', r)):
            raise TypeError("operator '%s' requires numeric operands" % op)
        if op == '+':
            return _dispatch('num_result', l + r)
        if op == '-':
            return _dispatch('num_result', l - r)
        if op == '*':
            return _dispatch('num_result', l * r)
        return None if r == 0 else _dispatch('num_result', l / r)
    if l is None or r is None:
        return False
    if _dispatch('is_num', l) and _dispatch('is_num', r):
        pass
    elif type(l) is not type(r):
        return False
    if op == '==':
        return l == r
    if op == '!=':
        return l != r
    if isinstance(l, (bool, list, dict)):
        return False
    return {'<': l < r, '<=': l <= r, '>': l > r, '>=': l >= r}[op]

@_register
def eval_at(node, row, path):
    try:
        return _dispatch('evaluate', node, row)
    except (TypeError, OverflowError, ValueError) as e:
        raise EtlError('EXECUTION_FAILED', 'ETL_ERROR: %s' % e, path)

@_register
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
            node = _dispatch('parse_expr', step['where'], path + '.where')
            rows = [r for r in rows if _dispatch('truthy', _dispatch('eval_at', node, r, path + '.where'))]
        elif op == 'map':
            node = _dispatch('parse_expr', step['expr'], path + '.expr')
            for r in rows:
                r[step['as']] = _dispatch('eval_at', node, r, path + '.expr')
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
                        node = _dispatch('parse_expr', when_expr, branch_path + '.when')
                        matches = _dispatch('truthy', _dispatch('eval_at', node, row, branch_path + '.when'))
                    if matches:
                        routed_rows[branch_idx].append(row)
                        break
            rows = []
            for branch_idx, branch in enumerate(step['branches']):
                branch_path = '%s.branches[%d]' % (path, branch_idx)
                branch_steps_path = branch_path + '.steps'
                if routed_rows[branch_idx]:
                    branch_raw_steps = []
                    branch_executed = _dispatch('execute_steps', branch['steps'], branch_raw_steps, [dict(r) for r in routed_rows[branch_idx]], branch_steps_path)
                    rows.extend(branch_executed)
    return rows

@_register
def execute(steps, raw_steps, dataset):
    rows = [dict(r) for r in dataset]
    return _dispatch('execute_steps', steps, raw_steps, rows, 'pipeline.steps')

@_register
def process(req, run=False):
    if not isinstance(req, dict):
        raise _dispatch('schema_error', 'ETL_ERROR: request must be an object', '')
    pipeline = req.get('pipeline')
    if not isinstance(pipeline, dict):
        raise _dispatch('schema_error', "ETL_ERROR: 'pipeline' must be an object", 'pipeline')
    steps = pipeline.get('steps')
    if not isinstance(steps, list):
        raise _dispatch('schema_error', "ETL_ERROR: 'steps' must be an array", 'pipeline.steps')
    if 'dataset' not in req or not isinstance(req['dataset'], list):
        raise _dispatch('schema_error', "ETL_ERROR: 'dataset' must be an array", 'dataset')
    for i, row in enumerate(req['dataset']):
        if not isinstance(row, dict):
            raise _dispatch('schema_error', 'ETL_ERROR: dataset rows must be objects', 'dataset[%d]' % i)
    normalized = [_dispatch('normalize_step', s, i) for i, s in enumerate(steps)]
    if not run:
        return {'status': 'ok', 'normalized': {'steps': normalized}}
    data = _dispatch('execute', normalized, steps, req['dataset'])
    return {'status': 'ok', 'data': data, 'metrics': {'rows_in': len(req['dataset']), 'rows_out': len(data)}}

@_register
def parse_bool(v):
    if v.lower() in ('true', '1', 'yes'):
        return True
    if v.lower() in ('false', '0', 'no'):
        return False
    raise argparse.ArgumentTypeError('expected true or false')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', nargs='?', const=True, default=False, type=parse_bool)
    args = parser.parse_args()
    try:
        try:
            req = json.loads(sys.stdin.read())
        except ValueError:
            raise _dispatch('schema_error', 'ETL_ERROR: invalid JSON input', '')
        result = _dispatch('process', req, run=args.execute)
        code = 0
    except EtlError as e:
        result = {'status': 'error', 'error_code': e.code, 'message': str(e), 'path': e.path}
        code = 1
    sys.stdout.write(json.dumps(result))
    sys.stdout.write('\n')
    sys.exit(code)
if __name__ == '__main__':
    main()
