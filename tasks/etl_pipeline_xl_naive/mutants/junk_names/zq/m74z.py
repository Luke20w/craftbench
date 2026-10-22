import re
from zq.m80j import K85X
K20Z = re.compile('\\s*(?:\n        (?P<bad>\\*{2,}|\\^+|%|&{3,}|\\|{3,}|&(?!&)|\\|(?!\\|)|=(?!=))\n      | (?P<num>\\d+\\.\\d*|\\.\\d+|\\d+)\n      | (?P<id>[A-Za-z_][A-Za-z0-9_]*)\n      | (?P<str>"[^"]*"|\'[^\']*\')\n      | (?P<op>>=|<=|==|!=|&&|\\|\\||[-+*/<>()!])\n    )', re.VERBOSE)
K7Z = {'and': '&&', 'or': '||', 'not': '!'}
K55J = {'true': True, 'false': False, 'null': None}


def q95x(q65v):
    q80x = []
    q94v = 0
    while q94v < len(q65v):
        if q65v[q94v:].strip() == '':
            break
        q14j = K20Z.match(q65v, q94v)
        if not q14j:
            raise ValueError('unexpected character %r' % q65v[q94v:].lstrip()[0])
        q94v = q14j.end()
        q78x = q14j.lastgroup
        q44j = q14j.group(q78x)
        if q78x == 'bad':
            raise ValueError("unsupported operator '%s'" % q44j)
        if q78x == 'id' and q44j in K7Z:
            q78x, q44j = ('op', K7Z[q44j])
        q80x.append((q78x, q44j))
    return q80x


class K6X:
    K82X = {'>', '>=', '<', '<=', '==', '!='}

    def __init__(self, q80x):
        self.q17j = q80x
        self.q23x = 0

    def q8z(self):
        return self.q17j[self.q23x] if self.q23x < len(self.q17j) else (None, None)

    def q92j(self):
        q91x = self.q8z()
        self.q23x += 1
        return q91x

    def q46x(self, q12v):
        q78x, q44j = self.q8z()
        return q78x == 'op' and q44j in q12v

    def q50v(self):
        q52v = self.q96j()
        if self.q23x != len(self.q17j):
            raise ValueError('unexpected token %r' % (self.q8z()[1],))
        return q52v

    def q92x(self, q12v, q34j):
        q52v = q34j()
        while self.q46x(q12v):
            q72z = self.q92j()[1]
            q52v = ('bin', q72z, q52v, q34j())
        return q52v

    def q96j(self):
        return self.q92x(('||',), self.q97j)

    def q97j(self):
        return self.q92x(('&&',), self.q87v)

    def q87v(self):
        if self.q46x(('!',)):
            self.q92j()
            return ('un', '!', self.q87v())
        return self.q10x()

    def q10x(self):
        return self.q92x(self.K82X, self.q87j)

    def q87j(self):
        return self.q92x(('+', '-'), self.q17x)

    def q17x(self):
        return self.q92x(('*', '/'), self.q32j)

    def q32j(self):
        if self.q46x(('+', '-')):
            q72z = self.q92j()[1]
            return ('un', q72z, self.q32j())
        if self.q46x(('!',)):
            self.q92j()
            return ('un', '!', self.q32j())
        return self.q24j()

    def q24j(self):
        q78x, q44j = self.q92j()
        if q78x == 'num':
            return ('lit', float(q44j) if '.' in q44j else int(q44j))
        if q78x == 'str':
            return ('lit', q44j[1:-1])
        if q78x == 'id':
            if q44j in K55J:
                return ('lit', K55J[q44j])
            return ('id', q44j)
        if q78x == 'op' and q44j == '(':
            q52v = self.q96j()
            if self.q92j() != ('op', ')'):
                raise ValueError('missing closing parenthesis')
            return q52v
        if q78x is None:
            raise ValueError('unexpected end of expression')
        raise ValueError('unexpected token %r' % q44j)


def q48z(q65v, q85x):
    try:
        return K6X(q95x(q65v)).q50v()
    except ValueError as q84v:
        q90z = str(q84v)
        if not q90z.startswith('unsupported operator'):
            q90z = 'invalid expression: ' + q90z
        raise K85X('BAD_EXPR', 'ETL_ERROR: ' + q90z, q85x)


def q64z(q77j):
    return isinstance(q77j, (int, float)) and (not isinstance(q77j, bool))


def q20j(q77j):
    return q77j is not None and bool(q77j)


def q77v(q77j):
    if isinstance(q77j, float) and q77j.is_integer() and (abs(q77j) < 1000000000000000.0):
        return int(q77j)
    return q77j


def q54j(q52v, q7z):
    q78x = q52v[0]
    if q78x == 'lit':
        return q52v[1]
    if q78x == 'id':
        return q7z.get(q52v[1])
    if q78x == 'un':
        q72z, q77j = (q52v[1], q54j(q52v[2], q7z))
        if q72z == '!':
            return not q20j(q77j)
        if q77j is None:
            return None
        if not q64z(q77j):
            raise TypeError("unary '%s' requires a number" % q72z)
        return q77j if q72z == '+' else q77v(-q77j)
    q72z = q52v[1]
    if q72z == '&&':
        return q20j(q54j(q52v[2], q7z)) and q20j(q54j(q52v[3], q7z))
    if q72z == '||':
        return q20j(q54j(q52v[2], q7z)) or q20j(q54j(q52v[3], q7z))
    q56x, q93z = (q54j(q52v[2], q7z), q54j(q52v[3], q7z))
    if q72z in ('+', '-', '*', '/'):
        if q56x is None or q93z is None:
            return None
        if q72z == '+' and isinstance(q56x, str) and isinstance(q93z, str):
            return q56x + q93z
        if not (q64z(q56x) and q64z(q93z)):
            raise TypeError("operator '%s' requires numeric operands" % q72z)
        if q72z == '+':
            return q77v(q56x + q93z)
        if q72z == '-':
            return q77v(q56x - q93z)
        if q72z == '*':
            return q77v(q56x * q93z)
        return None if q93z == 0 else q77v(q56x / q93z)
    if q56x is None or q93z is None:
        return False
    if q64z(q56x) and q64z(q93z):
        pass
    elif type(q56x) is not type(q93z):
        return False
    if q72z == '==':
        return q56x == q93z
    if q72z == '!=':
        return q56x != q93z
    if isinstance(q56x, (bool, list, dict)):
        return False
    return {'<': q56x < q93z, '<=': q56x <= q93z, '>': q56x > q93z, '>=': q56x >= q93z}[q72z]


def q20x(q52v, q7z, q85x):
    try:
        return q54j(q52v, q7z)
    except (TypeError, OverflowError, ValueError) as q84v:
        raise K85X('EXECUTION_FAILED', 'ETL_ERROR: %s' % q84v, q85x)
