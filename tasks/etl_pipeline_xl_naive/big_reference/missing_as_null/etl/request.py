"""Request handling: validate the request, then normalize or execute the pipeline."""

from etl.errors import schema_error
from etl.steps import Context, StepList, to_json
from etl.ops.common import OPTIONS
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
    read_options(req.get('options', {}))
    parsed = StepList('steps').normalize(steps, 'pipeline.steps')
    if not run:
        return {'status': 'ok', 'normalized': {'steps': to_json(parsed)}}
    data = Context().run(parsed, [dict(r) for r in req['dataset']])
    return {'status': 'ok', 'data': data, 'metrics': {'rows_in': len(req['dataset']), 'rows_out': len(data)}}


def read_options(options):
    """The optional top-level `options` object; unknown keys are ignored."""
    if not isinstance(options, dict):
        raise schema_error("'options' must be an object", 'options')
    for key in OPTIONS:
        value = options.get(key, False)
        if not isinstance(value, bool):
            raise schema_error("'%s' must be a boolean" % key, 'options.' + key)
        OPTIONS[key] = value
