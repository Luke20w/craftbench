import argparse
import json
import re
import sys

class q1x(Exception):

    def __init__(self, q24z, q47x, q72z):
        super().__init__(q47x)
        self.q24z = q24z
        self.q72z = q72z

def q88z(q47x, q72z):
    return q1x('SCHEMA_VALIDATION_FAILED', q47x, q72z)
q5x = re.compile('\\s*(?:\n        (?P<bad>\\*{2,}|\\^+|%|&{3,}|\\|{3,}|&(?!&)|\\|(?!\\|)|=(?!=))\n      | (?P<num>\\d+\\.\\d*|\\.\\d+|\\d+)\n      | (?P<id>[A-Za-z_][A-Za-z0-9_]*)\n      | (?P<str>"[^"]*"|\'[^\']*\')\n      | (?P<op>>=|<=|==|!=|&&|\\|\\||[-+*/<>()!])\n    )', re.VERBOSE)
q2z = {'and': '&&', 'or': '||', 'not': '!'}
q3x = {'true': True, 'false': False, 'null': None}

def q101x(q99x):
    q102z = []
    q76z = 0
    while q76z < len(q99x):
        if q99x[q76z:].strip() == '':
            break
        q44z = q5x.match(q99x, q76z)
        if not q44z:
            raise ValueError('unexpected character %r' % q99x[q76z:].lstrip()[0])
        q76z = q44z.end()
        q42z = q44z.lastgroup
        q106z = q44z.group(q42z)
        if q42z == 'bad':
            raise ValueError("unsupported operator '%s'" % q106z)
        if q42z == 'id' and q106z in q2z:
            q42z, q106z = ('op', q2z[q106z])
        q102z.append((q42z, q106z))
    return q102z

class q4z:
    q0z = {'>', '>=', '<', '<=', '==', '!='}

    def __init__(self, q102z):
        self.q96z = q102z
        self.q37x = 0

    def q74z(self):
        return self.q96z[self.q37x] if self.q37x < len(self.q96z) else (None, None)

    def q97x(self):
        q100z = self.q74z()
        self.q37x += 1
        return q100z

    def q11x(self, q61x):
        q42z, q106z = self.q74z()
        return q42z == 'op' and q106z in q61x

    def q68z(self):
        q51x = self.q62z()
        if self.q37x != len(self.q96z):
            raise ValueError('unexpected token %r' % (self.q74z()[1],))
        return q51x

    def q13x(self, q61x, q93x):
        q51x = q93x()
        while self.q11x(q61x):
            q60z = self.q97x()[1]
            q51x = ('bin', q60z, q51x, q93x())
        return q51x

    def q62z(self):
        return self.q13x(('||',), self.q8z)

    def q8z(self):
        return self.q13x(('&&',), self.q57x)

    def q57x(self):
        if self.q11x(('!',)):
            self.q97x()
            return ('un', '!', self.q57x())
        return self.q26z()

    def q26z(self):
        return self.q13x(self.q0z, self.q7x)

    def q7x(self):
        return self.q13x(('+', '-'), self.q98z)

    def q98z(self):
        return self.q13x(('*', '/'), self.q104z)

    def q104z(self):
        if self.q11x(('+', '-')):
            q60z = self.q97x()[1]
            return ('un', q60z, self.q104z())
        if self.q11x(('!',)):
            self.q97x()
            return ('un', '!', self.q104z())
        return self.q77x()

    def q77x(self):
        q42z, q106z = self.q97x()
        if q42z == 'num':
            return ('lit', float(q106z) if '.' in q106z else int(q106z))
        if q42z == 'str':
            return ('lit', q106z[1:-1])
        if q42z == 'id':
            if q106z in q3x:
                return ('lit', q3x[q106z])
            return ('id', q106z)
        if q42z == 'op' and q106z == '(':
            q51x = self.q62z()
            if self.q97x() != ('op', ')'):
                raise ValueError('missing closing parenthesis')
            return q51x
        if q42z is None:
            raise ValueError('unexpected end of expression')
        raise ValueError('unexpected token %r' % q106z)

def q70z(q99x, q72z):
    try:
        return q4z(q101x(q99x)).q68z()
    except ValueError as e:
        q48z = str(e)
        if not q48z.startswith('unsupported operator'):
            q48z = 'invalid expression: ' + q48z
        raise q1x('BAD_EXPR', 'ETL_ERROR: ' + q48z, q72z)

def q23x(q99x, q72z):
    q70z(q99x, q72z)

def q36z(q90z, q41x, q72z):
    q67x = '%s.%s' % (q72z, q41x)
    if q41x not in q90z:
        raise q88z("ETL_ERROR: missing required field '%s'" % q41x, q67x)
    q105x = q90z[q41x]
    if not isinstance(q105x, str):
        raise q88z("ETL_ERROR: '%s' must be a string" % q41x, q67x)
    q105x = q105x.strip()
    if not q105x:
        raise q88z("ETL_ERROR: '%s' must not be empty" % q41x, q67x)
    return q105x

def q52z(q90z, q37x, q72z=None):
    if q72z is None:
        q72z = 'pipeline.steps[%d]' % q37x
    if not isinstance(q90z, dict):
        raise q88z('ETL_ERROR: step must be an object', q72z)
    if 'op' not in q90z:
        raise q88z("ETL_ERROR: missing required field 'op'", q72z + '.op')
    if not isinstance(q90z['op'], str):
        raise q88z("ETL_ERROR: 'op' must be a string", q72z + '.op')
    q60z = q90z['op'].strip().lower()
    if q60z not in ('select', 'filter', 'map', 'rename', 'limit', 'branch'):
        raise q1x('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % q60z, q72z + '.op')
    q66z = {'op': q60z}
    if q60z == 'select':
        q25x = q90z.get('columns')
        q67x = q72z + '.columns'
        if 'columns' not in q90z:
            raise q88z("ETL_ERROR: missing required field 'columns'", q67x)
        if not isinstance(q25x, list):
            raise q88z("ETL_ERROR: 'columns' must be an array", q67x)
        for q39x, q22z in enumerate(q25x):
            if not isinstance(q22z, str):
                raise q88z('ETL_ERROR: column names must be strings', '%s[%d]' % (q67x, q39x))
        q66z['columns'] = list(q25x)
    elif q60z == 'filter':
        q66z['where'] = q36z(q90z, 'where', q72z)
        q23x(q66z['where'], q72z + '.where')
    elif q60z == 'map':
        q10z = q36z(q90z, 'as', q72z)
        q34z = q36z(q90z, 'expr', q72z)
        q23x(q34z, q72z + '.expr')
        q66z['as'] = q10z
        q66z['expr'] = q34z
    elif q60z == 'rename':
        if 'mapping' in q90z:
            q67x = q72z + '.mapping'
            q44z = q90z['mapping']
            if not isinstance(q44z, dict):
                raise q88z("ETL_ERROR: 'mapping' must be an object", q67x)
            for q40z, q105x in q44z.items():
                if not isinstance(q105x, str):
                    raise q88z('ETL_ERROR: mapping values must be strings', '%s.%s' % (q67x, q40z))
            q66z['mapping'] = dict(q44z)
        elif 'from' in q90z or 'to' in q90z:
            q66z['mapping'] = {q36z(q90z, 'from', q72z): q36z(q90z, 'to', q72z)}
        else:
            raise q88z("ETL_ERROR: rename requires 'from' and 'to' or 'mapping'", q72z)
    elif q60z == 'limit':
        q67x = q72z + '.n'
        if 'n' not in q90z:
            raise q88z("ETL_ERROR: missing required field 'n'", q67x)
        q49x = q90z['n']
        if isinstance(q49x, bool) or not isinstance(q49x, int):
            raise q88z("ETL_ERROR: 'n' must be an integer", q67x)
        if q49x < 0:
            raise q88z("ETL_ERROR: 'n' must be >= 0", q67x)
        q66z['n'] = q49x
    elif q60z == 'branch':
        q67x = q72z + '.branches'
        if 'branches' not in q90z:
            raise q88z("ETL_ERROR: missing required field 'branches'", q67x)
        q21x = q90z['branches']
        if not isinstance(q21x, list):
            raise q88z("ETL_ERROR: 'branches' must be an array", q67x)
        if len(q21x) == 0:
            raise q88z("ETL_ERROR: 'branches' must be non-empty", q67x)
        q64z = sum((1 for q12z in q21x if isinstance(q12z, dict) and q12z.get('when') == 'otherwise'))
        if q64z > 1:
            raise q1x('MALFORMED_STEP', "ETL_ERROR: at most one 'otherwise' branch allowed", q67x)
        if q64z == 1:
            q65x = next((q39x for q39x, q12z in enumerate(q21x) if isinstance(q12z, dict) and q12z.get('when') == 'otherwise'))
            if q65x != len(q21x) - 1:
                raise q1x('MALFORMED_STEP', "ETL_ERROR: 'otherwise' branch must be last", q67x)
        q55x = []
        for q39x, q12z in enumerate(q21x):
            q14z = '%s[%d]' % (q67x, q39x)
            if not isinstance(q12z, dict):
                raise q88z('ETL_ERROR: branch must be an object', q14z)
            if 'when' not in q12z:
                raise q88z("ETL_ERROR: missing required field 'when'", q14z + '.when')
            if not isinstance(q12z['when'], str):
                raise q88z("ETL_ERROR: 'when' must be a string", q14z + '.when')
            q107x = q12z['when']
            if q107x != 'otherwise':
                q23x(q107x, q14z + '.when')
            if 'steps' not in q12z:
                raise q88z("ETL_ERROR: missing required field 'steps'", q14z + '.steps')
            if not isinstance(q12z['steps'], list):
                raise q88z("ETL_ERROR: 'steps' must be an array", q14z + '.steps')
            q54z = {'when': q107x}
            if 'id' in q12z:
                if not isinstance(q12z['id'], str):
                    raise q88z("ETL_ERROR: 'id' must be a string", q14z + '.id')
                q54z['id'] = q12z['id']
            q56z = []
            for q40z, q95x in enumerate(q12z['steps']):
                q94z = '%s[%d]' % (q14z + '.steps', q40z)
                q56z.append(q52z(q95x, q40z, q72z=q94z))
            q54z['steps'] = q56z
            q55x.append(q54z)
        q66z['branches'] = q55x
        q46z = q90z.get('merge', {})
        if not isinstance(q46z, dict):
            raise q88z("ETL_ERROR: 'merge' must be an object", q72z + '.merge')
        q92z = q46z.get('strategy', 'concat')
        if q92z != 'concat':
            raise q88z("ETL_ERROR: only 'concat' merge strategy is supported", q72z + '.merge.strategy')
        q66z['merge'] = {'strategy': q92z}
    q63x = {'op': q66z.pop('op')}
    for q40z in sorted(q66z):
        q63x[q40z] = q66z[q40z]
    return q63x

def q38z(q105x):
    return isinstance(q105x, (int, float)) and (not isinstance(q105x, bool))

def q103x(q105x):
    return q105x is not None and bool(q105x)

def q59x(q105x):
    if isinstance(q105x, float) and q105x.is_integer() and (abs(q105x) < 1000000000000000.0):
        return int(q105x)
    return q105x

def q31x(q51x, q84z):
    q42z = q51x[0]
    if q42z == 'lit':
        return q51x[1]
    if q42z == 'id':
        return q84z.get(q51x[1])
    if q42z == 'un':
        q60z, q105x = (q51x[1], q31x(q51x[2], q84z))
        if q60z == '!':
            return not q103x(q105x)
        if q105x is None:
            return None
        if not q38z(q105x):
            raise TypeError("unary '%s' requires a number" % q60z)
        return q105x if q60z == '+' else q59x(-q105x)
    q60z = q51x[1]
    if q60z == '&&':
        return q103x(q31x(q51x[2], q84z)) and q103x(q31x(q51x[3], q84z))
    if q60z == '||':
        return q103x(q31x(q51x[2], q84z)) or q103x(q31x(q51x[3], q84z))
    q43x, q79x = (q31x(q51x[2], q84z), q31x(q51x[3], q84z))
    if q60z in ('+', '-', '*', '/'):
        if q43x is None or q79x is None:
            return None
        if q60z == '+' and isinstance(q43x, str) and isinstance(q79x, str):
            return q43x + q79x
        if not (q38z(q43x) and q38z(q79x)):
            raise TypeError("operator '%s' requires numeric operands" % q60z)
        if q60z == '+':
            return q59x(q43x + q79x)
        if q60z == '-':
            return q59x(q43x - q79x)
        if q60z == '*':
            return q59x(q43x * q79x)
        return None if q79x == 0 else q59x(q43x / q79x)
    if q43x is None or q79x is None:
        return False
    if q38z(q43x) and q38z(q79x):
        pass
    elif type(q43x) is not type(q79x):
        return False
    if q60z == '==':
        return q43x == q79x
    if q60z == '!=':
        return q43x != q79x
    if isinstance(q43x, (bool, list, dict)):
        return False
    return {'<': q43x < q79x, '<=': q43x <= q79x, '>': q43x > q79x, '>=': q43x >= q79x}[q60z]

def q30z(q51x, q84z, q72z):
    try:
        return q31x(q51x, q84z)
    except (TypeError, OverflowError, ValueError) as e:
        raise q1x('EXECUTION_FAILED', 'ETL_ERROR: %s' % e, q72z)

def q33x(q91x, q80z, q85x, q73x):
    for q37x, q90z in enumerate(q91x):
        q72z = '%s[%d]' % (q73x, q37x)
        q60z = q90z['op']
        if q60z == 'select':
            q25x = q90z['columns']
            for q79x in q85x:
                for q39x, q22z in enumerate(q25x):
                    if q22z not in q79x:
                        raise q1x('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % q22z, '%s.columns[%d]' % (q72z, q39x))
            q85x = [{q22z: q79x[q22z] for q22z in q25x} for q79x in q85x]
        elif q60z == 'filter':
            q51x = q70z(q90z['where'], q72z + '.where')
            q85x = [q79x for q79x in q85x if q103x(q30z(q51x, q79x, q72z + '.where'))]
        elif q60z == 'map':
            q51x = q70z(q90z['expr'], q72z + '.expr')
            for q79x in q85x:
                q79x[q90z['as']] = q30z(q51x, q79x, q72z + '.expr')
        elif q60z == 'rename':
            q35x = 'mapping' not in q80z[q37x] if q37x < len(q80z) else False
            for q89x, q29x in q90z['mapping'].items():
                q67x = q72z + '.from' if q35x else '%s.mapping.%s' % (q72z, q89x)
                q50z = []
                for q79x in q85x:
                    if q89x not in q79x:
                        raise q1x('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % q89x, q67x)
                    q58z = {}
                    for q40z, q105x in q79x.items():
                        if q40z == q89x:
                            q58z[q29x] = q105x
                        elif q40z != q29x:
                            q58z[q40z] = q105x
                    q50z.append(q58z)
                q85x = q50z
        elif q60z == 'limit':
            q85x = q85x[:q90z['n']]
        elif q60z == 'branch':
            q83x = [[] for q6z in q90z['branches']]
            for q84z in q85x:
                for q17x, q15x in enumerate(q90z['branches']):
                    q108z = q15x['when']
                    q18z = '%s.branches[%d]' % (q72z, q17x)
                    q45x = False
                    if q108z == 'otherwise':
                        q45x = True
                    else:
                        q51x = q70z(q108z, q18z + '.when')
                        q45x = q103x(q30z(q51x, q84z, q18z + '.when'))
                    if q45x:
                        q83x[q17x].append(q84z)
                        break
            q85x = []
            for q17x, q15x in enumerate(q90z['branches']):
                q18z = '%s.branches[%d]' % (q72z, q17x)
                q20z = q18z + '.steps'
                if q83x[q17x]:
                    q19x = []
                    q16z = q33x(q15x['steps'], q19x, [dict(q79x) for q79x in q83x[q17x]], q20z)
                    q85x.extend(q16z)
    return q85x

def q32z(q91x, q80z, q28z):
    q85x = [dict(q79x) for q79x in q28z]
    return q33x(q91x, q80z, q85x, 'pipeline.steps')

def q78z(q81x, q86z=False):
    if not isinstance(q81x, dict):
        raise q88z('ETL_ERROR: request must be an object', '')
    q75x = q81x.get('pipeline')
    if not isinstance(q75x, dict):
        raise q88z("ETL_ERROR: 'pipeline' must be an object", 'pipeline')
    q91x = q75x.get('steps')
    if not isinstance(q91x, list):
        raise q88z("ETL_ERROR: 'steps' must be an array", 'pipeline.steps')
    if 'dataset' not in q81x or not isinstance(q81x['dataset'], list):
        raise q88z("ETL_ERROR: 'dataset' must be an array", 'dataset')
    for q37x, q84z in enumerate(q81x['dataset']):
        if not isinstance(q84z, dict):
            raise q88z('ETL_ERROR: dataset rows must be objects', 'dataset[%d]' % q37x)
    q53x = [q52z(q87x, q37x) for q37x, q87x in enumerate(q91x)]
    if not q86z:
        return {'status': 'ok', 'normalized': {'steps': q53x}}
    q27x = q32z(q53x, q91x, q81x['dataset'])
    return {'status': 'ok', 'data': q27x, 'metrics': {'rows_in': len(q81x['dataset']), 'rows_out': len(q27x)}}

def q69x(q105x):
    if q105x.lower() in ('true', '1', 'yes'):
        return True
    if q105x.lower() in ('false', '0', 'no'):
        return False
    raise argparse.ArgumentTypeError('expected true or false')

def main():
    q71x = argparse.ArgumentParser()
    q71x.add_argument('--execute', nargs='?', const=True, default=False, type=q69x)
    q9x = q71x.parse_args()
    try:
        try:
            q81x = json.loads(sys.stdin.read())
        except ValueError:
            raise q88z('ETL_ERROR: invalid JSON input', '')
        q82z = q78z(q81x, q86z=q9x.execute)
        q24z = 0
    except q1x as e:
        q82z = {'status': 'error', 'error_code': e.q24z, 'message': str(e), 'path': e.q72z}
        q24z = 1
    sys.stdout.write(json.dumps(q82z))
    sys.stdout.write('\n')
    sys.exit(q24z)
if __name__ == '__main__':
    main()
