"""Request handling: validate the request, then normalize or execute the pipeline."""

from etl.errors import EtlError, schema_error
from etl import validation
from etl.validation import collect
from etl.steps import OPS, Context, StepList, to_json
import etl.ops  # noqa: F401  (registers the ops)

def process(req, run=False, all_errors=False, strict=False):
    """Validate the request, then normalize or execute it. Validation errors carry `problems`."""
    validation.STRICT = strict
    try:
        parsed = collect(validate, req) if all_errors else validate(req)
    except EtlError as e:
        if e.problems is None:
            e.problems = [e]
        raise
    finally:
        validation.STRICT = False
    if not run:
        return {'status': 'ok', 'normalized': {'steps': to_json(parsed)}}
    data = Context().run(parsed, [dict(r) for r in req['dataset']])
    return {'status': 'ok', 'data': data, 'metrics': {'rows_in': len(req['dataset']), 'rows_out': len(data)}}

def validate(req):
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
    return StepList('steps').normalize(steps, 'pipeline.steps')

def list_ops():
    """Every op and the field names its steps accept."""
    return {'status': 'ok', 'ops': {name: sorted(op.keys()) for name, op in sorted(OPS.items())}}
