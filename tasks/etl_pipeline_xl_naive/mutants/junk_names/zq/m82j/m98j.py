import json
from zq.m80j import K85X


def q61z(q73v, q55v, q54z='columns'):
    q30v = q73v[q54z]
    for q93z in q55v:
        for q55z, q21z in enumerate(q30v):
            if q21z not in q93z:
                raise K85X('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % q21z, q73v.q46x(q54z, q55z))
    return q30v


def q43v(q73v, q7z, q54z='column'):
    q21z = q73v[q54z]
    if q21z not in q7z:
        raise K85X('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % q21z, q73v.q46x(q54z))
    return q7z[q21z]


def q63j(q73v, q4j, *q19z):
    return K85X('EXECUTION_FAILED', 'ETL_ERROR: ' + q4j, q73v.q46x(*q19z))


def q20z(q77j):
    return q77j if isinstance(q77j, str) else json.dumps(q77j)
