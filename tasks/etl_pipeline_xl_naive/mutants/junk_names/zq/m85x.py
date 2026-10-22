from zq.m80j import K85X, q57x
from zq.m74z import q48z, q20x
from zq.m43v import K45V, K97Z, q38x


class K36X:
    def __init__(self, q72z, q13v, q85x, q72j):
        self.q72z = q72z
        self.q13v = q13v
        self.q85x = q85x
        self.q72j = q72j

    @staticmethod
    def q50v(q72j, q85x):
        if not isinstance(q72j, dict):
            raise q57x('step must be an object', q85x)
        q90x = K97Z('op').q37j(q72j, q85x).lower()
        if q90x not in K92J:
            raise K85X('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % q90x, q85x + '.op')
        q72z = K92J[q90x]
        return K36X(q72z, q72z.q1x(q72j, q85x), q85x, q72j)

    def __getitem__(self, q54z):
        return self.q13v[q54z]

    def q46x(self, *q19z):
        q19x = self.q85x
        for q98z in q19z:
            q19x += '[%d]' % q98z if isinstance(q98z, int) else '.' + q98z
        return q19x

    def q39x(self):
        q5z = {'op': self.q72z.q90x}
        for q12z in sorted(self.q13v):
            q5z[q12z] = q39x(self.q13v[q12z])
        return q5z


def q39x(q77j):
    if isinstance(q77j, K36X):
        return q77j.q39x()
    if isinstance(q77j, list):
        return [q39x(q98x) for q98x in q77j]
    if isinstance(q77j, dict):
        return {q12z: q39x(q98x) for q12z, q98x in q77j.items()}
    return q77j


class K58J:
    def q64j(self, q96v, q55v):
        for q73v in q96v:
            q55v = q73v.q72z.q64j(q73v, q55v, self)
        return q55v

    def q36j(self, q73v, q5j, q7z, *q19z):
        q85x = q73v.q46x(*q19z)
        return q20x(q48z(q5j, q85x), q7z, q85x)


class K21V:
    q90x = None
    q12x = ()

    def q1x(self, q72j, q85x):
        return q38x(self.q12x, q72j, q85x)

    def q64j(self, q73v, q55v, q47j):
        raise NotImplementedError
K92J = {}


def q33v(q74z):
    K92J[q74z.q90x] = q74z()
    return q74z


class K88Z(K45V):
    def __init__(self, q54z, **q29z):
        super().__init__(q54z, q25x=None, **q29z)

    def q1x(self, q79v, q85x):
        if not isinstance(q79v, list):
            raise q57x("'%s' must be an array" % self.q54z, q85x)
        return [K36X.q50v(q67x, '%s[%d]' % (q85x, q23x)) for q23x, q67x in enumerate(q79v)]
