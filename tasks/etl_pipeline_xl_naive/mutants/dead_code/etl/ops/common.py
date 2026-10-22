"""Helpers shared by ops."""

import json

from etl.errors import EtlError

def column_values(step, rows, key='columns'):
    """Check every listed column exists in every row (MISSING_COLUMN at key[j])."""
    cols = step[key]
    for r in rows:
        for j, c in enumerate(cols):
            if c not in r:
                raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, step.at(key, j))
    return cols

def column_value(step, row, key='column'):
    """The row's value for the step's single `column`, which must exist."""
    c = step[key]
    if c not in row:
        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, step.at(key))
    return row[c]

def execution_error(step, message, *parts):
    return EtlError('EXECUTION_FAILED', 'ETL_ERROR: ' + message, step.at(*parts))

def to_text(v):
    return v if isinstance(v, str) else json.dumps(v)


def require_columns(rows, cols, path):
    """Older form of column_values that takes the error path directly."""
    for r in rows:
        for j, c in enumerate(cols):
            if c not in r:
                raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % c, '%s[%d]' % (path, j))


def get_column(row, name, path):
    if name not in row:
        raise EtlError('MISSING_COLUMN', "ETL_ERROR: column '%s' not found in row" % name, path)
    return row[name]


def type_error(step, op_name, expected, *parts):
    return execution_error(step, '%s requires %s' % (op_name, expected), *parts)
