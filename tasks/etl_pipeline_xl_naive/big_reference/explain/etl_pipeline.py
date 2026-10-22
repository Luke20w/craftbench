"""ETL pipeline CLI: validate, normalize and execute a JSON pipeline over in-memory rows.

The model is four ideas (see etl/):
  * Field:   one key of a step; knows how to validate and normalize its raw value (fields.py).
  * Op:      a step kind; declares its fields and how it transforms rows (ops/).
  * Step:    a parsed step; remembers its op, its normalized values and its own error path (steps.py).
  * Context: runtime state for one execution; runs steps and evaluates their expressions (steps.py).
Nested steps are just a field (StepList), so anything that works at the top level works at any depth.
"""

import argparse
import json
import sys

from etl.errors import EtlError, schema_error
from etl.request import process

def parse_bool(v):
    if v.lower() in ('true', '1', 'yes'):
        return True
    if v.lower() in ('false', '0', 'no'):
        return False
    raise argparse.ArgumentTypeError('expected true or false')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', nargs='?', const=True, default=False, type=parse_bool)
    parser.add_argument('--explain', action='store_true')
    args = parser.parse_args()
    try:
        try:
            req = json.loads(sys.stdin.read())
        except ValueError:
            raise schema_error('invalid JSON input', '')
        result = process(req, run=args.execute, explain=args.explain)
        code = 0
    except EtlError as e:
        result = {'status': 'error', 'error_code': e.code, 'message': str(e), 'path': e.path}
        code = 1
    sys.stdout.write(json.dumps(result))
    sys.stdout.write('\n')
    sys.exit(code)

if __name__ == '__main__':
    main()
