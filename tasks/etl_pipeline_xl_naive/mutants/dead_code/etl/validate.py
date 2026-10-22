"""Request and step validation, one checker per field type.

Each op lists its fields as (key, kind, required) tuples in OP_SCHEMAS; validate_step checks a raw step
against its schema and returns the normalized step as a plain dict.
"""

import re

from etl.errors import EtlError, schema_error
from etl.expr import parse_expr, is_num

OP_SCHEMAS = {
    'select': [('columns', 'str_list', True)],
    'filter': [('where', 'expr', True)],
    'map': [('as', 'str', True), ('expr', 'expr', True)],
    'limit': [('n', 'count', True)],
    'drop': [('columns', 'str_list', True)],
    'fill': [('column', 'str', True), ('value', 'expr', True)],
    'cast': [('column', 'str', True), ('to', ('int', 'float', 'string', 'bool'), True)],
    'concat': [('as', 'str', True), ('columns', 'str_list', True), ('sep', 'label', False)],
    'split': [('column', 'str', True), ('sep', 'label', True), ('into', 'str_list', True)],
    'text': [('columns', 'str_list', True), ('fn', ('upper', 'lower', 'trim'), True)],
    'replace': [('column', 'str', True), ('find', 'label', True), ('with', 'label', True)],
    'round': [('column', 'str', True), ('digits', 'count', False)],
    'clip': [('column', 'str', True), ('min', 'number', False), ('max', 'number', False)],
    'scale': [('column', 'str', True), ('factor', 'number', True), ('offset', 'number', False)],
    'sort': [('by', 'str', True), ('desc', 'bool', False)],
    'offset': [('n', 'count', True)],
    'tail': [('n', 'count', True)],
    'distinct': [('columns', 'str_list', False)],
    'group_count': [('by', 'str_list', True), ('as', 'str', True)],
}

DEFAULTS = {
    'sep': '',
    'digits': 0,
    'offset': 0,
    'desc': False,
}


def check_str(raw, key, path):
    v = raw[key]
    if not isinstance(v, str):
        raise schema_error("'%s' must be a string" % key, path)
    v = v.strip()
    if not v:
        raise schema_error("'%s' must not be empty" % key, path)
    return v


def check_label(raw, key, path):
    v = raw[key]
    if not isinstance(v, str):
        raise schema_error("'%s' must be a string" % key, path)
    return v


def check_expr(raw, key, path):
    v = check_str(raw, key, path)
    parse_expr(v, path)
    return v


def check_count(raw, key, path):
    v = raw[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise schema_error("'%s' must be an integer" % key, path)
    if v < 0:
        raise schema_error("'%s' must be >= 0" % key, path)
    return v


def check_number(raw, key, path):
    v = raw[key]
    if not is_num(v):
        raise schema_error("'%s' must be a number" % key, path)
    return v


def check_bool(raw, key, path):
    v = raw[key]
    if not isinstance(v, bool):
        raise schema_error("'%s' must be a boolean" % key, path)
    return v


def check_str_list(raw, key, path):
    v = raw[key]
    if not isinstance(v, list):
        raise schema_error("'%s' must be an array" % key, path)
    for i, c in enumerate(v):
        if not isinstance(c, str):
            raise schema_error('column names must be strings', '%s[%d]' % (path, i))
    return list(v)


def check_choice(raw, key, path, choices):
    v = check_str(raw, key, path).lower()
    if v not in choices:
        raise schema_error("'%s' must be one of %s" % (key, ', '.join(choices)), path)
    return v


def check_pattern(raw, key, path):
    v = check_label(raw, key, path)
    try:
        re.compile(v)
    except re.error:
        raise schema_error("'%s' must be a valid regular expression" % key, path)
    return v


CHECKERS = {
    'str': check_str,
    'label': check_label,
    'expr': check_expr,
    'count': check_count,
    'number': check_number,
    'bool': check_bool,
    'str_list': check_str_list,
    'pattern': check_pattern,
}


def validate_step(raw, path):
    if not isinstance(raw, dict):
        raise schema_error('step must be an object', path)
    if 'op' not in raw:
        raise schema_error("missing required field 'op'", path + '.op')
    if not isinstance(raw['op'], str):
        raise schema_error("'op' must be a string", path + '.op')
    op = raw['op'].strip().lower()
    if op == 'rename':
        return validate_rename(raw, path)
    if op not in OP_SCHEMAS:
        raise EtlError('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % op, path + '.op')
    out = {'op': op}
    for key, kind, required in OP_SCHEMAS[op]:
        p = '%s.%s' % (path, key)
        if key not in raw:
            if required:
                raise schema_error("missing required field '%s'" % key, p)
            if key in DEFAULTS:
                out[key] = DEFAULTS[key]
            continue
        if isinstance(kind, tuple):
            out[key] = check_choice(raw, key, p, kind)
        else:
            out[key] = CHECKERS[kind](raw, key, p)
    return out


def validate_rename(raw, path):
    if 'mapping' in raw:
        m = raw['mapping']
        if not isinstance(m, dict):
            raise schema_error("'mapping' must be an object", path + '.mapping')
        for k, v in m.items():
            if not isinstance(v, str):
                raise schema_error('mapping values must be strings', '%s.mapping.%s' % (path, k))
        return {'op': 'rename', 'mapping': dict(m)}
    if 'from' in raw or 'to' in raw:
        for key in ('from', 'to'):
            if key not in raw:
                raise schema_error("missing required field '%s'" % key, '%s.%s' % (path, key))
        src = check_str(raw, 'from', path + '.from')
        dst = check_str(raw, 'to', path + '.to')
        return {'op': 'rename', 'mapping': {src: dst}}
    raise schema_error("rename requires 'from' and 'to' or 'mapping'", path)


def validate_steps(steps, path):
    if not isinstance(steps, list):
        raise schema_error("'steps' must be an array", path)
    return [validate_step(s, '%s[%d]' % (path, i)) for i, s in enumerate(steps)]


def validate_request(req):
    if not isinstance(req, dict):
        raise schema_error('request must be an object', '')
    pipeline = req.get('pipeline')
    if not isinstance(pipeline, dict):
        raise schema_error("'pipeline' must be an object", 'pipeline')
    steps = validate_steps(pipeline.get('steps'), 'pipeline.steps')
    dataset = req.get('dataset')
    if not isinstance(dataset, list):
        raise schema_error("'dataset' must be an array", 'dataset')
    for i, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise schema_error('dataset rows must be objects', 'dataset[%d]' % i)
    return steps, dataset
