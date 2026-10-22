from zq.m80j import q57x
from zq.m85x import K58J, K88Z, q39x
import zq.m82j


def q92z(q42j, q64j=False):
    if not isinstance(q42j, dict):
        raise q57x('request must be an object', '')
    q40z = q42j.get('pipeline')
    if not isinstance(q40z, dict):
        raise q57x("'pipeline' must be an object", 'pipeline')
    q96v = q40z.get('steps')
    if not isinstance(q96v, list):
        raise q57x("'steps' must be an array", 'pipeline.steps')
    if 'dataset' not in q42j or not isinstance(q42j['dataset'], list):
        raise q57x("'dataset' must be an array", 'dataset')
    for q23x, q7z in enumerate(q42j['dataset']):
        if not isinstance(q7z, dict):
            raise q57x('dataset rows must be objects', 'dataset[%d]' % q23x)
    q35x = K88Z('steps').q1x(q96v, 'pipeline.steps')
    if not q64j:
        return {'status': 'ok', 'normalized': {'steps': q39x(q35x)}}
    q75v = K58J().q64j(q35x, [dict(q93z) for q93z in q42j['dataset']])
    return {'status': 'ok', 'data': q75v, 'metrics': {'rows_in': len(q42j['dataset']), 'rows_out': len(q75v)}}
