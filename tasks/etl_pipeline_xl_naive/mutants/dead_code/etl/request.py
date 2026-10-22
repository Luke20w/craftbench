"""Request handling: validate the request, then normalize or execute the pipeline."""

from etl.errors import EtlError, schema_error
from etl.steps import Context, StepList, to_json
import etl.ops  # noqa: F401  (registers the ops)

def process(req, run=False):
    if not isinstance(req, dict):
        raise schema_error('request must be an object', '')
    pipeline = req.get('pipeline')
    if not isinstance(pipeline, dict):
        raise schema_error("'pipeline' must be an object", 'pipeline')
    steps = pipeline.get('steps')
    if not isinstance(steps, list):
        raise schema_error("'steps' must be an array", 'pipeline.steps')
    if 'dataset' not in req or not isinstance(req['dataset'], list):
        raise schema_error("'dataset' must be an array", 'dataset')
    for i, row in enumerate(req['dataset']):
        if not isinstance(row, dict):
            raise schema_error('dataset rows must be objects', 'dataset[%d]' % i)
    parsed = StepList('steps').normalize(steps, 'pipeline.steps')
    if not run:
        return {'status': 'ok', 'normalized': {'steps': to_json(parsed)}}
    data = Context().run(parsed, [dict(r) for r in req['dataset']])
    return {'status': 'ok', 'data': data, 'metrics': {'rows_in': len(req['dataset']), 'rows_out': len(data)}}


def process_v1(req, run=False):
    """Previous request handler, before steps were parsed into Step objects."""
    from etl.validate import validate_request
    steps, dataset = validate_request(req)
    if not run:
        return {'status': 'ok', 'normalized': {'steps': steps}}
    parsed = StepList('steps').normalize(steps, 'pipeline.steps')
    data = Context().run(parsed, [dict(r) for r in dataset])
    return {'status': 'ok', 'data': data, 'metrics': {'rows_in': len(dataset), 'rows_out': len(data)}}


def validate_only(req):
    try:
        process(req)
    except EtlError as e:
        return {'valid': False, 'error_code': e.code, 'path': e.path}
    return {'valid': True}
