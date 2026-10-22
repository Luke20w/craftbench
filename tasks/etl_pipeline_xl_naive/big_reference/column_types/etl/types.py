"""Column types: the request's `schema`, and checking that steps only use declared columns in ways their type
allows. Types follow the columns through the pipeline: a column a step changes loses its known type."""

from etl.errors import EtlError, schema_error

TYPES = ('number', 'string', 'boolean', 'array', 'object')


class Known:
    """A column's known type. Unchanged columns keep the same Known object, so branches can tell."""

    def __init__(self, type):
        self.type = type


def read_schema(schema):
    if not isinstance(schema, dict):
        raise schema_error("'schema' must be an object", 'schema')
    for name, t in schema.items():
        if t not in TYPES:
            raise schema_error('column types must be one of %s' % ', '.join(TYPES), 'schema.' + name)
    return {name: Known(t) for name, t in schema.items()}


def check_types(steps, known):
    """TYPE_MISMATCH at the first field that uses a column of a type it can't handle; returns the types known
    after `steps`."""
    for step in steps:
        for column, allowed, parts in step.op.typed_columns(step):
            if column in known and known[column].type not in allowed:
                raise EtlError('TYPE_MISMATCH', "ETL_ERROR: column '%s' is a %s; expected %s"
                               % (column, known[column].type, ' or '.join(allowed)), step.at(*parts))
        if step.op.name == 'branch':
            after = [check_types(b['steps'], dict(known)) for b in step['branches']]
            known = {c: k for c, k in known.items() if all(a.get(c) is k for a in after)}
        else:
            known = step.op.retype(step, known)
    return known
