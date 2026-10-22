import json
import math
from zq.m74z import q64z, q77v
from zq.m43v import K97Z, K84X, K2J, K21Z, K45V
from zq.m85x import K21V, q33v
from zq.m82j.m98j import q43v, q63j


@q33v
class K59X(K21V):
    q90x = 'round'
    q12x = (K97Z('column'), K2J('digits', q89x=False, q4x=0))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            if not q64z(q77j):
                raise q63j(q73v, 'round requires a number', 'column')
            q93z[q73v['column']] = q77v(round(q77j, q73v['digits']))
        return q55v


@q33v
class K87X(K21V):
    q90x = 'clip'
    q12x = (K97Z('column'), K21Z('min', q89x=False), K21Z('max', q89x=False))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            if not q64z(q77j):
                raise q63j(q73v, 'clip requires a number', 'column')
            if 'min' in q73v.q13v and q77j < q73v['min']:
                q77j = q73v['min']
            if 'max' in q73v.q13v and q77j > q73v['max']:
                q77j = q73v['max']
            q93z[q73v['column']] = q77j
        return q55v


@q33v
class K18X(K21V):
    q90x = 'scale'
    q12x = (K97Z('column'), K21Z('factor'), K21Z('offset', q89x=False, q4x=0))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            if not q64z(q77j):
                raise q63j(q73v, 'scale requires a number', 'column')
            q93z[q73v['column']] = q77v(q77j * q73v['factor'] + q73v['offset'])
        return q55v


@q33v
class K26X(K21V):
    q90x = 'bucket'
    q12x = (K97Z('column'), K97Z('as'), K45V('edges', K21Z('edges entries'), q5v=True))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None and (not q64z(q77j)):
                raise q63j(q73v, 'bucket requires a number', 'column')
            q93z[q73v['as']] = None if q77j is None else sum((1 for q84v in q73v['edges'] if q77j >= q84v))
        return q55v


@q33v
class K62V(K21V):
    q90x = 'math'
    q12x = (K97Z('column'), K84X('fn', ('abs', 'floor', 'ceil', 'sqrt', 'neg')))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            if not q64z(q77j) or (q73v['fn'] == 'sqrt' and q77j < 0):
                raise q63j(q73v, 'cannot apply %s to %s' % (q73v['fn'], json.dumps(q77j)), 'column')
            if q73v['fn'] == 'abs':
                q93z[q73v['column']] = abs(q77j)
            elif q73v['fn'] == 'floor':
                q93z[q73v['column']] = math.floor(q77j)
            elif q73v['fn'] == 'ceil':
                q93z[q73v['column']] = math.ceil(q77j)
            elif q73v['fn'] == 'sqrt':
                q93z[q73v['column']] = q77v(math.sqrt(q77j))
            else:
                q93z[q73v['column']] = q77v(-q77j)
        return q55v


@q33v
class K22J(K21V):
    q90x = 'between'
    q12x = (K97Z('column'), K21Z('low'), K21Z('high'), K97Z('as'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q93z.get(q73v['column'])
            if q77j is not None and (not q64z(q77j)):
                raise q63j(q73v, 'between requires a number', 'column')
            q93z[q73v['as']] = q77j is not None and q73v['low'] <= q77j <= q73v['high']
        return q55v
