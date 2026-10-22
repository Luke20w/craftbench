import json
from zq.m74z import q64z, q77v
from zq.m43v import K97Z, K78X, K84X, K45V, K52J
from zq.m85x import K21V, q33v
from zq.m82j.m98j import q63j


@q33v
class K91Z(K21V):
    q90x = 'group_count'
    q12x = (K45V('by', K78X('column names'), q5v=True), K97Z('as'))

    def q64j(self, q73v, q55v, q47j):
        q51v = {}
        for q93z in q55v:
            q54z = json.dumps([q93z.get(q21z) for q21z in q73v['by']])
            if q54z not in q51v:
                q51v[q54z] = {q21z: q93z.get(q21z) for q21z in q73v['by']}
                q51v[q54z][q73v['as']] = 0
            q51v[q54z][q73v['as']] += 1
        return list(q51v.values())


@q33v
class K38X(K21V):
    q90x = 'summarize'
    q12x = (K45V('by', K78X('column names'), q89x=False, q4x=[]), K45V('metrics', K52J('metrics entry', (K97Z('as'), K84X('fn', ('sum', 'min', 'max', 'avg', 'count')), K78X('column', q89x=False))), q5v=True))

    def q64j(self, q73v, q55v, q47j):
        q51v = {}
        for q93z in q55v:
            q51v.setdefault(json.dumps([q93z.get(q21z) for q21z in q73v['by']]), []).append(q93z)
        q5z = []
        for q91v in q51v.values():
            q7z = {q21z: q91v[0].get(q21z) for q21z in q73v['by']}
            for q55z, q14j in enumerate(q73v['metrics']):
                q13v = [q98x.get(q14j['column']) for q98x in q91v] if 'column' in q14j else q91v
                q13v = [q77j for q77j in q13v if q77j is not None]
                if q14j['fn'] == 'count':
                    q7z[q14j['as']] = len(q13v)
                    continue
                if any((not q64z(q77j) for q77j in q13v)):
                    raise q63j(q73v, '%s requires numbers' % q14j['fn'], 'metrics', q55z, 'column')
                if not q13v:
                    q7z[q14j['as']] = None
                elif q14j['fn'] == 'sum':
                    q7z[q14j['as']] = q77v(sum(q13v))
                elif q14j['fn'] == 'min':
                    q7z[q14j['as']] = min(q13v)
                elif q14j['fn'] == 'max':
                    q7z[q14j['as']] = max(q13v)
                else:
                    q7z[q14j['as']] = q77v(sum(q13v) / len(q13v))
            q5z.append(q7z)
        return q5z
