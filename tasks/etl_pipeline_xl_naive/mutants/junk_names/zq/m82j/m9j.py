import json
from zq.m74z import q64z, q20j, q77v
from zq.m43v import K97Z, K78X, K34X, K91V, K2J, K8Z, K68V, K51Z, K45V
from zq.m85x import K21V, q33v
from zq.m82j.m98j import q63j


@q33v
class K72J(K21V):
    q90x = 'distinct'
    q12x = (K45V('columns', K78X('column names'), q89x=False),)

    def q64j(self, q73v, q55v, q47j):
        q75z, q5z = (set(), [])
        for q93z in q55v:
            if 'columns' in q73v.q13v:
                q54z = json.dumps([q93z.get(q21z) for q21z in q73v['columns']])
            else:
                q54z = json.dumps(q93z, sort_keys=True)
            if q54z not in q75z:
                q75z.add(q54z)
                q5z.append(q93z)
        return q5z
K60X = ((lambda q77j: q64z(q77j), 0), (lambda q77j: isinstance(q77j, str), 1), (lambda q77j: isinstance(q77j, bool), 2))


@q33v
class K39X(K21V):
    q90x = 'sort'
    q12x = (K97Z('by'), K34X('desc', q89x=False, q4x=False))

    def q64j(self, q73v, q55v, q47j):
        q80v = [q93z for q93z in q55v if q93z.get(q73v['by']) is not None]
        q11j = [q93z for q93z in q55v if q93z.get(q73v['by']) is None]
        return sorted(q80v, key=lambda q93z: self.q54z(q73v, q93z[q73v['by']]), reverse=q73v['desc']) + q11j

    def q54z(self, q73v, q77j):
        for q84z, q13j in K60X:
            if q84z(q77j):
                return (q13j, q77j)
        raise q63j(q73v, 'cannot sort by a %s value' % type(q77j).__name__, 'by')


@q33v
class K98V(K21V):
    q90x = 'offset'
    q12x = (K2J('n'),)

    def q64j(self, q73v, q55v, q47j):
        return q55v[q73v['n']:]


@q33v
class K84V(K21V):
    q90x = 'tail'
    q12x = (K2J('n'),)

    def q64j(self, q73v, q55v, q47j):
        return q55v[max(0, len(q55v) - q73v['n']):] if q73v['n'] else []


@q33v
class K59Z(K21V):
    q90x = 'assert'
    q12x = (K91V('where'), K78X('message', q89x=False, q4x='assertion failed'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            if not q20j(q47j.q36j(q73v, q73v['where'], q93z, 'where')):
                raise q63j(q73v, q73v['message'], 'where')
        return q55v


@q33v
class K36V(K21V):
    q90x = 'sample_every'
    q12x = (K2J('n', q75j=1),)

    def q64j(self, q73v, q55v, q47j):
        return q55v[::q73v['n']]


@q33v
class K23Z(K21V):
    q90x = 'take_while'
    q12x = (K91V('where'),)

    def q64j(self, q73v, q55v, q47j):
        q5z = []
        for q93z in q55v:
            if not q20j(q47j.q36j(q73v, q73v['where'], q93z, 'where')):
                break
            q5z.append(q93z)
        return q5z


@q33v
class K15Z(K21V):
    q90x = 'skip_while'
    q12x = (K91V('where'),)

    def q64j(self, q73v, q55v, q47j):
        q5z = []
        q95j = True
        for q93z in q55v:
            if q95j and q20j(q47j.q36j(q73v, q73v['where'], q93z, 'where')):
                continue
            q95j = False
            q5z.append(q93z)
        return q5z


@q33v
class K46X(K21V):
    q90x = 'append'
    q12x = (K51Z('rows'),)

    def q64j(self, q73v, q55v, q47j):
        return q55v + [dict(q98x) for q98x in q73v['rows']]


@q33v
class K50X(K21V):
    q90x = 'require'
    q12x = (K45V('columns', K78X('column names'), q5v=True),)

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            for q55z, q21z in enumerate(q73v['columns']):
                if q93z.get(q21z) is None:
                    raise q63j(q73v, "column '%s' is required" % q21z, 'columns', q55z)
        return q55v


@q33v
class K44X(K21V):
    q90x = 'row_number'
    q12x = (K97Z('as'), K8Z('start', q89x=False, q4x=1))

    def q64j(self, q73v, q55v, q47j):
        for q12z, q93z in enumerate(q55v):
            q93z[q73v['as']] = q73v['start'] + q12z
        return q55v


@q33v
class K40J(K21V):
    q90x = 'rank'
    q12x = (K97Z('by'), K97Z('as'), K34X('desc', q89x=False, q4x=False))

    def q64j(self, q73v, q55v, q47j):
        q87z = []
        for q93z in q55v:
            q77j = q93z.get(q73v['by'])
            if q77j is None:
                continue
            if not q64z(q77j):
                raise q63j(q73v, 'rank requires numbers', 'by')
            if q77j not in q87z:
                q87z.append(q77j)
        q87z.sort(reverse=q73v['desc'])
        for q93z in q55v:
            q77j = q93z.get(q73v['by'])
            q93z[q73v['as']] = None if q77j is None else q87z.index(q77j) + 1
        return q55v


@q33v
class K56Z(K21V):
    q90x = 'cumsum'
    q12x = (K97Z('column'), K97Z('as'))

    def q64j(self, q73v, q55v, q47j):
        q75x = 0
        for q93z in q55v:
            q77j = q93z.get(q73v['column'])
            if q77j is not None and (not q64z(q77j)):
                raise q63j(q73v, 'cumsum requires numbers', 'column')
            q75x = q77v(q75x + (q77j or 0))
            q93z[q73v['as']] = q75x
        return q55v


@q33v
class K56J(K21V):
    q90x = 'lag'
    q12x = (K97Z('column'), K97Z('as'), K2J('n', q89x=False, q4x=1), K68V('default', q89x=False))

    def q64j(self, q73v, q55v, q47j):
        q13v = [q93z.get(q73v['column']) for q93z in q55v]
        for q12z, q93z in enumerate(q55v):
            if q12z >= q73v['n']:
                q93z[q73v['as']] = q13v[q12z - q73v['n']]
            else:
                q93z[q73v['as']] = q73v['default'] if 'default' in q73v.q13v else None
        return q55v
