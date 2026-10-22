import json
import re
from zq.m43v import K97Z, K78X, K84X, K34X, K2J, K70Z, K45V
from zq.m85x import K21V, q33v
from zq.m82j.m98j import q61z, q43v, q63j, q20z


@q33v
class K37Z(K21V):
    q90x = 'concat'
    q12x = (K97Z('as'), K45V('columns', K78X('column names'), q5v=True), K78X('sep', q89x=False, q4x=''))

    def q64j(self, q73v, q55v, q47j):
        q30v = q61z(q73v, q55v)
        for q93z in q55v:
            q93z[q73v['as']] = q73v['sep'].join(('' if q93z[q21z] is None else q20z(q93z[q21z]) for q21z in q30v))
        return q55v


@q33v
class K63Z(K21V):
    q90x = 'split'
    q12x = (K97Z('column'), K78X('sep', q5v=True), K45V('into', K78X('column names'), q5v=True))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None and (not isinstance(q77j, str)):
                raise q63j(q73v, 'split requires a string', 'column')
            q19z = q77j.split(q73v['sep']) if q77j is not None else []
            for q23x, q90x in enumerate(q73v['into']):
                q93z[q90x] = q19z[q23x] if q23x < len(q19z) else None
        return q55v


@q33v
class K83X(K21V):
    q90x = 'text'
    q12x = (K45V('columns', K78X('column names')), K84X('fn', ('upper', 'lower', 'trim')))

    def q64j(self, q73v, q55v, q47j):
        q30v = q61z(q73v, q55v)
        q56v = {'upper': str.upper, 'lower': str.lower, 'trim': str.strip}[q73v['fn']]
        for q93z in q55v:
            for q55z, q21z in enumerate(q30v):
                if q93z[q21z] is None:
                    continue
                if not isinstance(q93z[q21z], str):
                    raise q63j(q73v, 'text requires a string', 'columns', q55z)
                q93z[q21z] = q56v(q93z[q21z])
        return q55v


@q33v
class K98Z(K21V):
    q90x = 'replace'
    q12x = (K97Z('column'), K78X('find', q5v=True), K78X('with'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            if not isinstance(q77j, str):
                raise q63j(q73v, 'replace requires a string', 'column')
            q93z[q73v['column']] = q77j.replace(q73v['find'], q73v['with'])
        return q55v


@q33v
class K29J(K21V):
    q90x = 'regex_extract'
    q12x = (K97Z('column'), K70Z('pattern'), K97Z('as'), K2J('group', q89x=False, q4x=0))

    def q64j(self, q73v, q55v, q47j):
        q22v = re.compile(q73v['pattern'])
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None and (not isinstance(q77j, str)):
                raise q63j(q73v, 'regex_extract requires a string', 'column')
            q14j = q22v.search(q77j) if q77j is not None else None
            if q14j is not None and q73v['group'] > q22v.groups:
                raise q63j(q73v, 'pattern has no group %d' % q73v['group'], 'group')
            q93z[q73v['as']] = q14j.group(q73v['group']) if q14j else None
        return q55v


@q33v
class K57V(K21V):
    q90x = 'regex_filter'
    q12x = (K97Z('column'), K70Z('pattern'), K34X('invert', q89x=False, q4x=False))

    def q64j(self, q73v, q55v, q47j):
        q22v = re.compile(q73v['pattern'])
        q5z = []
        for q93z in q55v:
            q77j = q93z.get(q73v['column'])
            if (isinstance(q77j, str) and q22v.search(q77j) is not None) != q73v['invert']:
                q5z.append(q93z)
        return q5z


@q33v
class K65X(K21V):
    q90x = 'substr'
    q12x = (K97Z('column'), K97Z('as'), K2J('start'), K2J('length', q89x=False))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None and (not isinstance(q77j, str)):
                raise q63j(q73v, 'substr requires a string', 'column')
            if q77j is None:
                q93z[q73v['as']] = None
            elif 'length' in q73v.q13v:
                q93z[q73v['as']] = q77j[q73v['start']:q73v['start'] + q73v['length']]
            else:
                q93z[q73v['as']] = q77j[q73v['start']:]
        return q55v


@q33v
class K80J(K21V):
    q90x = 'pad'
    q12x = (K97Z('column'), K2J('width'), K78X('fill', q5v=True, q89x=False, q4x=' '), K84X('side', ('left', 'right'), q89x=False, q4x='left'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            q67x = q20z(q77j)
            q89v = max(0, q73v['width'] - len(q67x))
            q26j = (q73v['fill'] * q89v)[:q89v]
            q93z[q73v['column']] = q26j + q67x if q73v['side'] == 'left' else q67x + q26j
        return q55v


@q33v
class K95Z(K21V):
    q90x = 'length'
    q12x = (K97Z('column'), K97Z('as'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None and (not isinstance(q77j, (str, list, dict))):
                raise q63j(q73v, 'length requires a string, array or object', 'column')
            q93z[q73v['as']] = None if q77j is None else len(q77j)
        return q55v


@q33v
class K25V(K21V):
    q90x = 'json_parse'
    q12x = (K97Z('column'),)

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                continue
            if not isinstance(q77j, str):
                raise q63j(q73v, 'json_parse requires a string', 'column')
            try:
                q93z[q73v['column']] = json.loads(q77j)
            except ValueError:
                raise q63j(q73v, 'invalid JSON text', 'column')
        return q55v


@q33v
class K41X(K21V):
    q90x = 'json_dump'
    q12x = (K97Z('column'),)

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is not None:
                q93z[q73v['column']] = json.dumps(q77j, sort_keys=True)
        return q55v


@q33v
class K71X(K21V):
    q90x = 'date_part'
    q12x = (K97Z('column'), K84X('part', ('year', 'month', 'day')), K97Z('as'))

    def q64j(self, q73v, q55v, q47j):
        for q93z in q55v:
            q77j = q43v(q73v, q93z)
            if q77j is None:
                q93z[q73v['as']] = None
                continue
            q14j = re.match('^(\\d{4})-(\\d{2})-(\\d{2})', q77j) if isinstance(q77j, str) else None
            if q14j is None:
                raise q63j(q73v, 'expected a YYYY-MM-DD date', 'column')
            q93z[q73v['as']] = int(q14j.group(('year', 'month', 'day').index(q73v['part']) + 1))
        return q55v
