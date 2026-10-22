import re
from zq.m80j import q57x
from zq.m74z import q48z, q64z
K46J = object()


class K4V:
    def __init__(self, q54z, q89x=True, q4x=K46J):
        self.q54z = q54z
        self.q89x = q89x
        self.q4x = q4x

    def q37j(self, q72j, q85x):
        q19x = '%s.%s' % (q85x, self.q54z)
        if self.q54z not in q72j:
            if self.q89x:
                raise q57x("missing required field '%s'" % self.q54z, q19x)
            return self.q4x
        return self.q1x(q72j[self.q54z], q19x)

    def q1x(self, q79v, q85x):
        return q79v


class K97Z(K4V):
    def q1x(self, q79v, q85x):
        if not isinstance(q79v, str):
            raise q57x("'%s' must be a string" % self.q54z, q85x)
        q79v = q79v.strip()
        if not q79v:
            raise q57x("'%s' must not be empty" % self.q54z, q85x)
        return q79v


class K78X(K4V):
    def __init__(self, q54z, q5v=False, **q29z):
        super().__init__(q54z, **q29z)
        self.q5v = q5v

    def q1x(self, q79v, q85x):
        if not isinstance(q79v, str):
            raise q57x("'%s' must be a string" % self.q54z, q85x)
        if self.q5v and (not q79v):
            raise q57x("'%s' must not be empty" % self.q54z, q85x)
        return q79v


class K84X(K97Z):
    def __init__(self, q54z, q21v, **q29z):
        super().__init__(q54z, **q29z)
        self.q21v = q21v

    def q1x(self, q79v, q85x):
        q79v = super().q1x(q79v, q85x).lower()
        if q79v not in self.q21v:
            raise q57x("'%s' must be one of %s" % (self.q54z, ', '.join(self.q21v)), q85x)
        return q79v


class K34X(K4V):
    def q1x(self, q79v, q85x):
        if not isinstance(q79v, bool):
            raise q57x("'%s' must be a boolean" % self.q54z, q85x)
        return q79v


class K91V(K97Z):
    def __init__(self, q54z, q55j=(), q74j=True, **q29z):
        super().__init__(q54z, **q29z)
        self.q55j = q55j
        self.q74j = q74j

    def q1x(self, q79v, q85x):
        if self.q74j:
            q79v = super().q1x(q79v, q85x)
        elif not isinstance(q79v, str):
            raise q57x("'%s' must be a string" % self.q54z, q85x)
        if q79v not in self.q55j:
            q48z(q79v, q85x)
        return q79v


class K2J(K4V):
    def __init__(self, q54z, q75j=0, **q29z):
        super().__init__(q54z, **q29z)
        self.q75j = q75j

    def q1x(self, q79v, q85x):
        if isinstance(q79v, bool) or not isinstance(q79v, int):
            raise q57x("'%s' must be an integer" % self.q54z, q85x)
        if q79v < self.q75j:
            raise q57x("'%s' must be >= %d" % (self.q54z, self.q75j), q85x)
        return q79v


class K8Z(K4V):
    def q1x(self, q79v, q85x):
        if isinstance(q79v, bool) or not isinstance(q79v, int):
            raise q57x("'%s' must be an integer" % self.q54z, q85x)
        return q79v


class K21Z(K4V):
    def q1x(self, q79v, q85x):
        if not q64z(q79v):
            raise q57x("'%s' must be a number" % self.q54z, q85x)
        return q79v


class K68V(K4V):
    def q1x(self, q79v, q85x):
        if not (q79v is None or isinstance(q79v, (bool, int, float, str))):
            raise q57x("'%s' must be a JSON scalar" % self.q54z, q85x)
        return q79v


class K70Z(K78X):
    def __init__(self, q54z, **q29z):
        super().__init__(q54z, q5v=True, **q29z)

    def q1x(self, q79v, q85x):
        q79v = super().q1x(q79v, q85x)
        try:
            re.compile(q79v)
        except re.error:
            raise q57x("'%s' must be a valid regular expression" % self.q54z, q85x)
        return q79v


class K51Z(K4V):
    def q1x(self, q79v, q85x):
        if not isinstance(q79v, list):
            raise q57x("'%s' must be an array" % self.q54z, q85x)
        for q23x, q77j in enumerate(q79v):
            if not isinstance(q77j, dict):
                raise q57x("'%s' entries must be objects" % self.q54z, '%s[%d]' % (q85x, q23x))
        return [dict(q77j) for q77j in q79v]


class K45V(K4V):
    def __init__(self, q54z, q25x, q5v=False, **q29z):
        super().__init__(q54z, **q29z)
        self.q25x = q25x
        self.q5v = q5v

    def q1x(self, q79v, q85x):
        if not isinstance(q79v, list):
            raise q57x("'%s' must be an array" % self.q54z, q85x)
        if self.q5v and (not q79v):
            raise q57x("'%s' must be non-empty" % self.q54z, q85x)
        self.q14x(q79v, q85x)
        return [self.q25x.q1x(q77j, '%s[%d]' % (q85x, q23x)) for q23x, q77j in enumerate(q79v)]

    def q14x(self, q79v, q85x):
        pass


class K92Z(K4V):
    def __init__(self, q54z, q79v, **q29z):
        super().__init__(q54z, **q29z)
        self.q79v = q79v

    def q1x(self, q79v, q85x):
        if not isinstance(q79v, dict):
            raise q57x("'%s' must be an object" % self.q54z, q85x)
        return {q12z: self.q79v.q1x(q77j, '%s.%s' % (q85x, q12z)) for q12z, q77j in q79v.items()}


class K52J(K4V):
    def __init__(self, q54z, q12x, **q29z):
        super().__init__(q54z, **q29z)
        self.q12x = q12x

    def q1x(self, q79v, q85x):
        if not isinstance(q79v, dict):
            raise q57x('%s must be an object' % self.q54z, q85x)
        return q38x(self.q12x, q79v, q85x)


def q38x(q12x, q72j, q85x):
    q5z = {}
    for q2x in q12x:
        q77j = q2x.q37j(q72j, q85x)
        if q77j is not K46J:
            q5z[q2x.q54z] = q77j
    return q5z
