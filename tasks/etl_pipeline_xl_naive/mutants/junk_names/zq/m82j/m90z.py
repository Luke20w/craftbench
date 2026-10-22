import json
from zq.m74z import q64z
from zq.m43v import K97Z, K78X, K84X, K91V, K68V, K45V, K92Z
from zq.m85x import K21V, q33v
from zq.m82j.m98j import q61z, q43v, q63j, q20z


@q33v
class K28Z(K21V):
    q90x = 'drop'
    q12x = (K45V('columns', K78X('column names')),)

    def q64j(self, q73v, q55v, q47j):
        q30v = q61z(q73v, q55v)
        return [{q12z: q77j for q12z, q77j in q93z.items() if q12z not in q30v} for q93z in q55v]


@q33v
class K70J(K21V):
    q90x = 'fill'
    q12x = (K97Z('column'), K91V('value'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            if q93z.get(q73v['column']) is None:
                q93z[q73v['column']] = q47j.q36j(q73v, q73v['value'], q93z, 'value')
        return q55v


@q33v
class K10V(K21V):
    q90x = 'cast'
    q12x = (K97Z('column'), K84X('to', ('int', 'float', 'string', 'bool')))

    def q64j(self, q73v, q55v, q47j):
        q9z = {'int': self.q71x, 'float': self.q86v, 'string': self.q99x, 'bool': self.q90j}[q73v['to']]
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None:
                try:
                    q93z[q73v['column']] = q9z(q77j)
                except (TypeError, ValueError):
                    raise q63j(q73v, 'cannot cast %s to %s' % (json.dumps(q77j), q73v['to']), 'column')
        return q55v

    def q71x(self, q77j):
        if isinstance(q77j, bool):
            raise TypeError
        return int(q77j)

    def q86v(self, q77j):
        if isinstance(q77j, bool):
            raise TypeError
        return float(q77j)

    def q99x(self, q77j):
        return q20z(q77j)

    def q90j(self, q77j):
        if isinstance(q77j, bool):
            return q77j
        if isinstance(q77j, str) and q77j.strip().lower() in ('true', 'false'):
            return q77j.strip().lower() == 'true'
        if q64z(q77j):
            return q77j != 0
        raise ValueError


@q33v
class K82Z(K21V):
    q90x = 'coalesce'
    q12x = (K97Z('as'), K45V('exprs', K91V('exprs entries'), q5v=True))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q79v = None
            for q12z, q5j in enumerate(q73v['exprs']):
                q79v = q47j.q36j(q73v, q5j, q93z, 'exprs', q12z)
                if q79v is not None:
                    break
            q93z[q73v['as']] = q79v
        return q55v


@q33v
class K96V(K21V):
    q90x = 'explode'
    q12x = (K97Z('column'),)

    def q64j(self, q73v, q55v, q47j):
        q5z = []
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if isinstance(q77j, list):
                q5z.extend((dict(q93z, **{q73v['column']: q98x}) for q98x in q77j))
            else:
                q5z.append(q93z)
        return q5z


@q33v
class K9Z(K21V):
    q90x = 'lookup'
    q12x = (K97Z('column'), K97Z('as'), K92Z('table', K68V('table values')), K68V('default', q89x=False))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            q54z = q77j if isinstance(q77j, str) else json.dumps(q77j)
            if q54z in q73v['table']:
                q93z[q73v['as']] = q73v['table'][q54z]
            else:
                q93z[q73v['as']] = q73v['default'] if 'default' in q73v.q13v else None
        return q55v


@q33v
class K26V(K21V):
    q90x = 'set'
    q12x = (K97Z('column'), K68V('value'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q93z[q73v['column']] = q73v['value']
        return q55v


@q33v
class K68Z(K21V):
    q90x = 'ensure'
    q12x = (K45V('columns', K78X('column names'), q5v=True), K68V('value', q89x=False, q4x=None))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            for q21z in q73v['columns']:
                if q21z not in q93z:
                    q93z[q21z] = q73v['value']
        return q55v


@q33v
class K19J(K21V):
    q90x = 'reorder'
    q12x = (K45V('columns', K78X('column names'), q5v=True),)

    def q64j(self, q73v, q55v, q47j):
        q30v = q61z(q73v, q55v)
        return [dict([(q21z, q93z[q21z]) for q21z in q30v] + [(q12z, q77j) for q12z, q77j in q93z.items() if q12z not in q30v]) for q93z in q55v]


@q33v
class K83V(K21V):
    q90x = 'prefix'
    q12x = (K78X('prefix', q5v=True), K45V('columns', K78X('column names'), q89x=False))

    def q64j(self, q73v, q55v, q47j):
        for q12z, q93z in enumerate(q55v):
            q80z = q73v['columns'] if 'columns' in q73v.q13v else list(q93z)
            q55v[q12z] = {q73v['prefix'] + q21z if q21z in q80z else q21z: q77j for q21z, q77j in q93z.items()}
        return q55v


@q33v
class K71J(K21V):
    q90x = 'nest'
    q12x = (K45V('columns', K78X('column names'), q5v=True), K97Z('as'))

    def q64j(self, q73v, q55v, q47j):
        q30v = q61z(q73v, q55v)
        q5z = []
        for q93z in q55v:
            q93v = {q12z: q77j for q12z, q77j in q93z.items() if q12z not in q30v}
            q93v[q73v['as']] = {q21z: q93z[q21z] for q21z in q30v}
            q5z.append(q93v)
        return q5z


@q33v
class K60V(K21V):
    q90x = 'unnest'
    q12x = (K97Z('column'), K78X('prefix', q89x=False, q4x=''))

    def q64j(self, q73v, q55v, q47j):
        q5z = []
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None and (not isinstance(q77j, dict)):
                raise q63j(q73v, 'unnest requires an object', 'column')
            q93v = {q12z: q98x for q12z, q98x in q93z.items() if q12z != q73v['column']}
            for q12z, q98x in (q77j or {}).items():
                q93v[q73v['prefix'] + q12z] = q98x
            q5z.append(q93v)
        return q5z
