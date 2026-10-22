from zq.m80j import K85X, q57x
from zq.m74z import q20j
from zq.m43v import K4V, K97Z, K78X, K91V, K2J, K45V, K92Z, K52J, q38x
from zq.m85x import K21V, q33v, K88Z


@q33v
class K65V(K21V):
    q90x = 'select'
    q12x = (K45V('columns', K78X('column names')),)

    def q64j(self, q73v, q55v, q47j):
        q30v = q73v['columns']
        for q93z in q55v:
            for q55z, q21z in enumerate(q30v):
                if q21z not in q93z:
                    raise K85X('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % q21z, q73v.q46x('columns', q55z))
        return [{q21z: q93z[q21z] for q21z in q30v} for q93z in q55v]


@q33v
class K95J(K21V):
    q90x = 'filter'
    q12x = (K91V('where'),)

    def q64j(self, q73v, q55v, q47j):
        return [q93z for q93z in q55v if q20j(q47j.q36j(q73v, q73v['where'], q93z, 'where'))]


@q33v
class K25Z(K21V):
    q90x = 'map'
    q12x = (K97Z('as'), K91V('expr'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q93z[q73v['as']] = q47j.q36j(q73v, q73v['expr'], q93z, 'expr')
        return q55v


@q33v
class K82V(K21V):
    q90x = 'rename'

    def q1x(self, q72j, q85x):
        if 'mapping' in q72j:
            return q38x((K92Z('mapping', K78X('mapping values')),), q72j, q85x)
        if 'from' in q72j or 'to' in q72j:
            q77j = q38x((K97Z('from'), K97Z('to')), q72j, q85x)
            return {'mapping': {q77j['from']: q77j['to']}}
        raise q57x("rename requires 'from' and 'to' or 'mapping'", q85x)

    def q64j(self, q73v, q55v, q47j):
        for q27v, q8x in q73v['mapping'].items():
            q85x = q73v.q46x('from') if 'mapping' not in q73v.q72j else q73v.q46x('mapping', q27v)
            q5z = []
            for q93z in q55v:
                if q27v not in q93z:
                    raise K85X('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % q27v, q85x)
                q5z.append({q8x if q12z == q27v else q12z: q77j for q12z, q77j in q93z.items() if q12z != q8x or q12z == q27v})
            q55v = q5z
        return q55v


@q33v
class K8V(K21V):
    q90x = 'limit'
    q12x = (K2J('n'),)

    def q64j(self, q73v, q55v, q47j):
        return q55v[:q73v['n']]


class K78J(K45V):
    def q14x(self, q79v, q85x):
        q98j = [isinstance(q22x, dict) and q22x.get('when') == 'otherwise' for q22x in q79v]
        if sum(q98j) > 1:
            raise K85X('MALFORMED_STEP', "ETL_ERROR: at most one 'otherwise' branch allowed", q85x)
        if any(q98j[:-1]):
            raise K85X('MALFORMED_STEP', "ETL_ERROR: 'otherwise' branch must be last", q85x)


class K79V(K4V):
    def q1x(self, q79v, q85x):
        if q79v != 'concat':
            raise q57x("only 'concat' merge strategy is supported", q85x)
        return q79v


@q33v
class K87V(K21V):
    q90x = 'branch'
    q12x = (K78J('branches', K52J('branch', (K91V('when', q55j=('otherwise',), q74j=False), K88Z('steps'), K78X('id', q89x=False))), q5v=True), K52J('merge', (K79V('strategy', q89x=False, q4x='concat'),), q89x=False, q4x={'strategy': 'concat'}))

    def q64j(self, q73v, q55v, q47j):
        q39z = q73v['branches']
        q69j = [[] for _ in q39z]
        for q7z in q55v:
            for q55z, q22x in enumerate(q39z):
                if q22x['when'] == 'otherwise' or q20j(q47j.q36j(q73v, q22x['when'], q7z, 'branches', q55z, 'when')):
                    q69j[q55z].append(q7z)
                    break
        q5z = []
        for q22x, q98z in zip(q39z, q69j):
            if q98z:
                q5z.extend(q47j.q64j(q22x['steps'], [dict(q93z) for q93z in q98z]))
        return q5z
