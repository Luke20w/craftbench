"""Helpers shared by ops."""

import json

from etl.errors import EtlError

# Request options that change how every op behaves; set once per request (see etl/request.py).
OPTIONS = {'missing_as_null': False}


def require_column(row, c, path):
    """A row must have column `c`: MISSING_COLUMN at `path`, or, with missing_as_null, the row gets it as null."""
    if c in row:
        return
    if OPTIONS['missing_as_null']:
        row[c] = None
        return
    raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, path)

def column_values(step, rows, key='columns'):
    """Check every listed column exists in every row (MISSING_COLUMN at key[j])."""
    cols = step[key]
    for r in rows:
        for j, c in enumerate(cols):
            require_column(r, c, step.at(key, j))
    return cols

def column_value(step, row, key='column'):
    """The row's value for the step's single `column`, which must exist."""
    require_column(row, step[key], step.at(key))
    return row[step[key]]

def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))

def to_text(v):
    return v if isinstance(v, str) else json.dumps(v)
