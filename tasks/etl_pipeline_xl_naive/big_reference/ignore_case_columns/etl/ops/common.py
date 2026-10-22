"""Helpers shared by ops."""

import json

from etl.errors import EtlError
from etl.options import match

def column_values(step, rows, key='columns'):
    """Check every listed column exists in every row (MISSING_COLUMN at key[j])."""
    cols = step[key]
    for r in rows:
        for j, c in enumerate(cols):
            if match(r, c) not in r:
                raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, step.at(key, j))
    return cols

def column_value(step, row, key='column'):
    """The row's value for the step's single `column`, which must exist."""
    c = match(row, step[key])
    if c not in row:
        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % step[key], step.at(key))
    return row[c]

def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))

def to_text(v):
    return v if isinstance(v, str) else json.dumps(v)
